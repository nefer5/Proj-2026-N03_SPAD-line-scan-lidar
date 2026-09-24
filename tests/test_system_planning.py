import copy
import pytest
from pydantic import ValidationError
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import yaml_snapshot,frozen_yaml
from spad_lidar.scan.planning import uniform_column_budget


def test_user_system_targets_and_budget():
    targets=SimulationConfig.system_targets({})
    assert targets.model_dump()==dict(frame_rate_hz=10,hfov_deg=120,scan_time_utilization=.667,slot_count=1000)
    b=uniform_column_budget(targets)
    assert b['frame_period_ns']==pytest.approx(100e6)
    assert b['scan_allocatable_ns']==pytest.approx(66.7e6)
    assert b['slot_target_ns']==pytest.approx(66700)
    assert b['angle_per_slot_deg']==pytest.approx(.12)
    assert b['slot_target_ns']*targets.slot_count==pytest.approx(b['scan_allocatable_ns'])


@pytest.mark.parametrize('bad',[{'hfov_deg':float('nan')},{'hfov_deg':float('inf')},
    {'slot_count':1.5},{'slot_count':True},{'scan_time_utilization':0},
    {'scan_time_utilization':1.1},{'hfov_mrad':120},{'frame_rate_hz':0}])
def test_targets_reject_invalid_and_unknown(bad):
    with pytest.raises(ValidationError):SimulationConfig.system_targets(bad)


def test_missing_default_cannot_be_hidden_by_user_override():
    snapshot=copy.deepcopy(yaml_snapshot())
    snapshot['defaults.yaml']['experiments']['system_targets'].pop('hfov_deg')
    with frozen_yaml(snapshot),pytest.raises(ValidationError):
        SimulationConfig.system_targets({'hfov_deg':120})


def test_budget_tradeoffs_and_legacy_independence():
    base=uniform_column_budget(SimulationConfig.system_targets({}))
    faster=uniform_column_budget(SimulationConfig.system_targets({'frame_rate_hz':20}))
    narrower=uniform_column_budget(SimulationConfig.system_targets({'hfov_deg':60}))
    denser=uniform_column_budget(SimulationConfig.system_targets({'slot_count':2000}))
    assert faster['slot_target_ns']==base['slot_target_ns']/2
    assert narrower['slot_target_ns']==base['slot_target_ns']
    assert narrower['required_average_optical_rad_s']==base['required_average_optical_rad_s']/2
    assert denser['slot_target_ns']==base['slot_target_ns']/2
    assert SimulationConfig.for_experiment('scan',{}).scan.frame_rate_hz!=10
