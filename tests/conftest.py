"""Keep numerical regression experiments fixed when user-facing defaults change.

Configuration/reload tests and shared-default smoke tests use the live YAML.
Only the explicitly listed numerical/integration suites use this versioned
reference scenario; algorithms and implementation remain current.
"""
from pathlib import Path
import pytest
from spad_lidar.configuration import frozen_yaml, yaml_snapshot, parse_yaml

REFERENCE_MODULES = {
 'test_b_acquisition_views','test_b_platform','test_binning',
 'test_budget_detector_view','test_budget_electrical_reference','test_budget_pipeline',
 'test_budget_schematic','test_budget_windows','test_c_workspace','test_column_scan',
 'test_columns_api','test_detection','test_filter_leakage','test_hardware_budget',
 'test_histogram_preview','test_histogram_ranges','test_lab_api','test_line_budget',
 'test_filter_interpolation','test_noise_reference','test_performance_sweep','test_photon_flow','test_readout_modes',
 'test_scanning','test_scene_energy_domain','test_simulator','test_spatial_optics',
 'test_spatial_profiles','test_spectral_background','test_system_planning','test_tx_rx_domains'
}

@pytest.fixture(scope='module',autouse=True)
def fixed_numerical_reference(request):
    if request.module.__name__.split('.')[-1] not in REFERENCE_MODULES:
        yield
        return
    snapshot=yaml_snapshot()
    snapshot['defaults.yaml']=parse_yaml((Path(__file__).parent/'fixtures/numerical-reference-defaults.yaml').read_text(encoding='utf-8'))
    with frozen_yaml(snapshot):
        yield
