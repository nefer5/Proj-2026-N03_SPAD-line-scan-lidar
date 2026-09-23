import ast
import json
from pathlib import Path
import numpy as np
import pytest
from spad_lidar.contracts import CandidateEvents
from spad_lidar.spad import AcquisitionSession
from spad_lidar.timing import periodic_program
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms, frozen_yaml, yaml_snapshot
from spad_lidar.experiments.lab import run_lab
from spad_lidar.contracts import AcquisitionProgram, AcquisitionWindow


@pytest.mark.parametrize('mode', ['independent_first','independent_multi','shared_first','shared_multi',
                                  'shared_multitdc','coincidence_fixed','coincidence_sliding'])
def test_chunks_preserve_deadtime_logic_windows_and_tdc(mode):
    c = SimulationConfig.for_experiment('spad', {'readout': {'readout_mode': mode, 'coincidence_window_ns': 4},
                                               'device': {'spad_dead_time_ns': 3}})
    program = periodic_program(30, 0, 30, 0, 3, 3)
    times = np.array([1, 2, 3, 4, 28, 29, 30, 31, 32, 59, 60, 61, 62, 87])
    pixels = np.array([0, 1, 0, 2, 0, 1, 0, 1, 2, 0, 1, 2, 0, 0])
    def acquire(boundaries):
        s = AcquisitionSession(c.device, c.readout, np.zeros(c.device.spads_per_channel,dtype=int), program, 100)
        lo = 0
        for until in boundaries:
            hi = np.searchsorted(times, until, side='left')
            s.advance(CandidateEvents(times[lo:hi], pixels[lo:hi]), until)
            lo = hi
        return s
    one = acquire([90]); chunks = acquire([2, 4, 29, 30, 31, 60, 88, 90])
    assert one.readout.records == chunks.readout.records
    assert one.stats == chunks.stats
    assert one.readout.trace == chunks.readout.trace
    assert np.array_equal(one.device.ready_ns, chunks.device.ready_ns)
    partial=acquire([31])
    restored=AcquisitionSession.restore(json.loads(json.dumps(partial.checkpoint(),allow_nan=False)))
    mask=times>=31
    restored.advance(CandidateEvents(times[mask],pixels[mask]),90)
    assert restored.readout.records==one.readout.records
    assert restored.stats==one.stats


def test_spad_package_does_not_import_system_or_io():
    root = Path(__file__).resolve().parents[1]/'src/spad_lidar/spad'
    forbidden = {'models','configuration','experiments','rx','tx','scene','runtime','webapi','api','simulator','timing'}
    for path in root.rglob('*.py'):
        for item in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(item, ast.ImportFrom) and item.module:
                assert not set(item.module.split('.')) & forbidden, (path,item.module)


def test_device_gate_and_readout_gate_are_distinct():
    cfg=SimulationConfig.for_experiment('spad',{'device':{'spad_dead_time_ns':20}})
    program=AcquisitionProgram([AcquisitionWindow(0,0,200,100,200,True,0,200)])
    s=AcquisitionSession(cfg.device,cfg.readout,np.zeros(cfg.device.spads_per_channel,dtype=int),program,10)
    s.advance(CandidateEvents([95,105],[0,0]),200)
    assert s.stats['outside_gate_avalanches']==1
    assert s.stats['spad_dead_losses']==1
    assert s.readout.records==[]


def test_device_and_readout_can_be_injected_independently():
    from spad_lidar.spad.device import DeviceState
    from spad_lidar.spad.readout import ReadoutEngine
    class AlwaysReadyDevice(DeviceState):
        def avalanche(self,t,pixel,dead_time_ns):
            return True
    cfg=SimulationConfig.for_experiment('spad',{'readout':{'readout_mode':'independent_multi','tdc_dead_time_ns':0}})
    program=periodic_program(100,0,100,0,1,1)
    engine=AlwaysReadyDevice(cfg.device.spads_per_channel)
    s=AcquisitionSession(cfg.device,cfg.readout,np.zeros(cfg.device.spads_per_channel,dtype=int),program,10,
                         device_engine=engine,readout_factory=ReadoutEngine)
    s.advance(CandidateEvents([10,11],[0,0]),100)
    assert s.device is engine
    assert s.stats['recorded']==2
    with pytest.raises(ValueError,match='checkpoint adapter'):
        s.checkpoint()


def test_standalone_config_rejects_system_fields_and_bad_defaults():
    with pytest.raises(ValueError):
        SimulationConfig.for_experiment('spad', {'range_m': 100})
    snap = yaml_snapshot()
    del snap['defaults.yaml']['experiments']['spad']['illumination']['pulse_delay_ns']
    with frozen_yaml(snap), pytest.raises(ValueError):
        SimulationConfig.for_experiment('spad', {'illumination': {'pulse_delay_ns': 500}})


def test_dark_only_and_deterministic_blocking():
    cfg = SimulationConfig.for_experiment('spad', {'illumination': {'signal_photons_per_pulse': 0, 'background_photons_per_second_per_pixel': 0},
                                                'device': {'dcr_cps_per_spad': 0, 'other_noise_cps_per_spad': 0}})
    result = run_lab(cfg, Algorithms.load(), lambda *x:None, lambda:False)
    assert result['records'] == []
    assert result['audit']['source']['sampled_candidates'] == 0
    cfg = SimulationConfig.for_experiment('spad', {'timing': {'laser_shots': 10}})
    a = Algorithms.load()
    b = a.model_copy(update={'acquisition_block_cycles': 1})
    r1 = run_lab(cfg, a, lambda *x:None, lambda:False)
    r2 = run_lab(cfg, b, lambda *x:None, lambda:False)
    assert r1['records'] == r2['records']
    assert r1['audit'] == r2['audit']


def test_pixel_concentration_changes_deadtime_without_changing_photon_total():
    base = {'illumination': {'signal_photons_per_pulse': 1000}, 'device': {'spad_dead_time_ns': 100},
            'readout': {'readout_mode': 'independent_multi'}, 'timing': {'laser_shots': 20}}
    uniform = SimulationConfig.for_experiment('spad', base)
    base['illumination'].update(spatial_mode='weights', pixel_weights=[1]+[0]*(uniform.device.spads_per_channel-1))
    spot = SimulationConfig.for_experiment('spad', base)
    a = Algorithms.load()
    u = run_lab(uniform, a, lambda *x:None, lambda:False)
    s = run_lab(spot, a, lambda *x:None, lambda:False)
    assert sum(u['illumination']['signal_photons_per_pixel_per_pulse']) == sum(s['illumination']['signal_photons_per_pixel_per_pulse'])
    assert u['audit']['final_records'] > s['audit']['final_records']
