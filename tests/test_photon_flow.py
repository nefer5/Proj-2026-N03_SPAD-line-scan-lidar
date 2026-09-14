from pathlib import Path
import runpy
import pytest
from spad_lidar.models import SimulationConfig
from spad_lidar.simulator import photon_budget,derived_quantities,simulate
from spad_lidar.configuration import read_yaml,default_values


def test_echo_stage_factors_and_photon_planes():
    cfg=SimulationConfig()
    b=photon_budget(cfg)
    assert b.tx_output_energy_j==pytest.approx(cfg.pulse_energy_nj*1e-9*cfg.tx_efficiency)
    assert b.target_incident_energy_j==pytest.approx(b.tx_output_energy_j*cfg.atmospheric_one_way_transmission)
    assert b.target_reflected_energy_j==pytest.approx(b.target_incident_energy_j*cfg.target_reflectivity)
    assert b.rx_incident_energy_j==pytest.approx(b.target_reflected_energy_j*b.geometric_collection*cfg.atmospheric_one_way_transmission*cfg.overlap_factor)
    assert b.signal_rx_incident_photons_per_pulse==pytest.approx(b.rx_incident_energy_j/b.photon_energy_j)
    assert b.signal_sensor_incident_photons_per_pulse==pytest.approx(b.signal_rx_incident_photons_per_pulse*cfg.rx_efficiency*b.filter_transmission_at_laser)
    assert b.signal_detected_per_pulse==pytest.approx(b.signal_sensor_incident_photons_per_pulse*b.pde_at_laser*cfg.fill_factor)


def test_background_photon_stages_are_ordered_and_zero_safe():
    b=photon_budget(SimulationConfig())
    assert b.solar_rx_incident_photons_per_gate>=b.solar_sensor_incident_photons_per_gate>=b.solar_detected_per_gate
    assert b.other_rx_incident_photons_per_gate>=b.other_sensor_incident_photons_per_gate>=b.other_light_detected_per_gate
    no_rx=photon_budget(SimulationConfig(rx_efficiency=0))
    assert no_rx.signal_rx_incident_photons_per_pulse>0
    assert no_rx.other_rx_incident_photons_per_gate>0
    assert no_rx.signal_sensor_incident_photons_per_pulse==0
    assert no_rx.other_light_detected_per_gate==0
    no_filter=photon_budget(SimulationConfig(spectral_inputs={'filter':{'mode':'basic','basic':{'amplitude':0}}}))
    assert no_filter.solar_rx_incident_photons_per_gate>0
    assert no_filter.solar_sensor_incident_photons_per_gate==0


def test_photon_flow_is_shared_and_does_not_invent_final_source_counts():
    cfg=SimulationConfig(monte_carlo_trials=0,laser_shots=10)
    derived=derived_quantities(cfg)
    result=simulate(cfg,debug=True)
    flow=derived['photon_flow']
    assert flow==result['derived']['photon_flow']
    assert [chain['id'] for chain in flow['chains']]==['echo','solar','other']
    assert flow['values']['echo_candidates_pulse']==result['budget']['signal_detected_per_pulse']
    assert flow['values']['other_candidates_gate']==result['budget']['other_light_detected_per_gate']
    formulas=read_yaml('formulas.yaml');notes=read_yaml('formula-notes.yaml')
    steps=flow['common']+flow['readout']+[step for chain in flow['chains'] for step in chain['steps']]
    for step in steps:
        assert step['latex']==formulas[step['formula_id']]
        assert step['symbols']==notes[step['formula_id']]
        assert step['logic']
        assert all('unit' in value and 'value' in value for value in step['values'])
    assert not any('recorded' in key for key in flow['values'])


def test_generated_document_matches_shared_definitions():
    root=Path(__file__).resolve().parents[1]
    render=runpy.run_path(str(root/'scripts/render-photon-budget-doc.py'))['render']
    assert render()==(root/'docs/photon-budget.md').read_text(encoding='utf-8')


def test_nominal_wavelengths_are_905_without_collapsing_sample_axes():
    cfg=default_values()
    assert cfg['wavelength_nm']==905
    for spec in cfg['spectral_inputs'].values():
        assert spec['basic']['center_nm']==905
    points=cfg['spectral_inputs']['pde']['manual_points']
    assert len(set(p['wavelength_nm'] for p in points))==len(points)>2
