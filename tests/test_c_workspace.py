from fastapi.testclient import TestClient
from spad_lidar.api import app
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms,read_yaml
from spad_lidar.experiments.system_config import form_values
from spad_lidar.experiments.scanning import run_scan
from spad_lidar.reporting.spatial_view import optical_view


def test_c_defaults_are_shared_and_demo_is_explicit():
    a=SimulationConfig();c=SimulationConfig.for_experiment('scan',{})
    assert c.background.solar_enabled==a.solar_enabled
    assert c.background.other_light_enabled==a.other_light_enabled
    assert 'acquisition' in c.model_dump() and 'timing' not in c.model_dump()
    assert not hasattr(c.acquisition,'laser_shots')
    demo=SimulationConfig.for_experiment('scan',read_yaml('defaults.yaml')['experiments']['scan_demo'])
    assert not demo.background.solar_enabled and not demo.background.other_light_enabled
    assert SimulationConfig.for_experiment('scan',form_values(demo)).model_dump()==demo.model_dump()


def test_c_preview_reports_real_resource_lower_bound_and_does_not_fake_records():
    client=TestClient(app)
    view=client.post('/api/experiments/scan/workspace-preview',json={})
    assert view.status_code==200
    value=view.json()
    assert value['resource_probe']['blocked']
    assert 'records' not in value
    assert value['scan_preview']['summary']['emitted_reference_slots']==80
    demo=client.get('/api/experiments/scan/demo').json()
    quick=client.post('/api/experiments/scan/workspace-preview',json=demo).json()
    assert not quick['resource_probe']['blocked']
    assert quick['form_configuration']['scan']['frame_count']==1
    assert len(quick['parameter_figures'])==10


def test_c_workspace_reuses_components_and_canonical_transfer():
    client=TestClient(app)
    html=client.get('/system/scan')
    assert html.status_code==200 and 'data-lab="scan"' in html.text
    for name in ('shared/scan-workspace.js','shared/histogram-window.js','shared/optical-panels.js','system.js'):
        assert '/static/'+name+'?v=' in html.text
    catalog=client.get('/api/experiments/scan').json()
    assert catalog['schema_version']==3
    assert catalog['form_paths']['scan.frame_rate_hz']=='scan.frame_rate_hz'
    transfer=client.post('/api/experiments/scan/from-system',json={'scene':{'range_m':120}}).json()
    assert transfer['schema_version']==3 and transfer['experiment']['scene']['range_m']==120
    assert 'laser_shots' not in transfer['experiment']['acquisition']


def test_c_view_uses_emitted_count_without_introducing_independent_shots():
    c=SimulationConfig.for_experiment('scan',read_yaml('defaults.yaml')['experiments']['scan_demo'])
    a=Algorithms.load();result=run_scan(c,a,lambda *args:None,lambda:False)
    count=result['scan']['summary']['emitted_reference_slots']
    view=optical_view(c,a,result['optics'],laser_shots=count)
    assert view['parameter_figures']['timing']['shots']==count
    assert 'laser_shots' not in view['form_configuration']['timing']
