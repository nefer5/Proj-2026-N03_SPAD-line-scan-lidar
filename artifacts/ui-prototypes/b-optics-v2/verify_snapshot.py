"""Acceptance checks for revision 02 frozen UI data, not new simulation tests."""
import importlib.util
import json
from pathlib import Path
import numpy as np

root = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('exporter', root/'tools/build_b_ui_preview.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
data = json.loads((root/'web/prototypes/b-optics/snapshot.json').read_text(encoding='utf-8'))
ui = data['preview']['interface_configuration']
a = module.SimulationConfig().model_dump()
for group in ('device', 'readout'):
    for key, value in ui[group].items():
        assert value == a[key], (group, key)
for key, value in ui['optics'].items():
    if key in a:
        assert value == a[key], key
assert ui['timing']['laser_shots'] == a['laser_shots']
assert ui['timing']['period_ns'] == 1e9/a['laser_prf_hz']
assert ui['timing']['gate_start_ns'] == a['gate_start_ns']
assert ui['timing']['gate_width_ns'] == a['gate_width_ns']
assert ui['spectral_inputs'] == a['spectral_inputs']
assert ui['optics']['total_pulse_energy_nj'] == a['pulse_energy_nj']
assert 'focal_length_mm' not in ui['optics']

o = data['optics']; p = np.asarray(data['angle_psfs'])
assert np.all(p >= 0) and np.all(p.sum(axis=(1,2)) <= 1+1e-10)
assert np.allclose(p.sum(axis=(1,2)), np.asarray(o['psf_capture_fraction']).ravel())
x = (np.asarray(data['x_edges_um'])[:-1]+np.asarray(data['x_edges_um'])[1:])/2
y = (np.asarray(data['y_edges_um'])[:-1]+np.asarray(data['y_edges_um'])[1:])/2
h, v = np.asarray(o['angular_h_centers_mrad']), np.asarray(o['angular_v_centers_mrad'])
centroid_x = (p.sum(axis=1)@x)/p.sum(axis=(1,2))
centroid_y = (p.sum(axis=2)@y)/p.sum(axis=(1,2))
assert np.all(centroid_x[h>1e-10]<0) and np.all(centroid_x[h<-1e-10]>0)
assert np.all(centroid_y[v>1e-10]<0) and np.all(centroid_y[v<-1e-10]>0)

ratios = module.channel_db_tables([[1, .1, .01, 0]])['matrix_db'][0]
assert ratios[1][0] == -10 and ratios[2][0] == -20
assert ratios[0][1] == 10 and ratios[0][0] == 0
assert ratios[3][0] == '-inf' and ratios[3][3] is None
for matrix in data['crosstalk']['matrix_db']:
    for j,row in enumerate(matrix):
        for r,value in enumerate(row):
            if isinstance(value,(int,float)):
                assert np.isclose(value, -matrix[r][j])
                if j == r: assert value == 0

figures = data['parameter_figures']
assert len(figures) == 10
env = figures['environment']['series']
assert np.allclose(np.array(env[0]['y'])+np.array(env[1]['y']),env[2]['y'])
pde = figures['pde']['series']
assert np.allclose(np.asarray(pde[0]['y'])*ui['device']['fill_factor'],pde[1]['y'])
first = np.asarray(data['histogram']['counts'])
assert np.all(np.asarray(data['statistics']['lower']) <= first)
assert np.all(first <= np.asarray(data['statistics']['upper']))
report = {'inherited_defaults':True,'inverted_centroids_all_angles':True,
          'energy_conservation':True,'db_coefficient_and_zero_cases':True,
          'spectral_units_and_composition':True,'first_observation_in_sample_range':True,
          'parameter_figures':list(figures),'records':int(first.sum())}
Path(__file__).with_name('numeric-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
