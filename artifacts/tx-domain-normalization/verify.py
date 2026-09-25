"""Compare immutable before/after acquisitions of the user's identical config."""
from pathlib import Path
from datetime import datetime, timezone
from hashlib import sha256
import json
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent
OLD='c46990d61353402682982a8487c13734'
NEW='fdc0aa78c65d41dd99cd337721234826'
paths=[ROOT/'artifacts/runs'/job/'result.json' for job in (OLD,NEW)]
before,after=[json.loads(p.read_text(encoding='utf-8')) for p in paths]
assert before['configuration']['experiment']==after['configuration']['experiment']
assert before['configuration']['algorithms']==after['configuration']['algorithms']
a=before['optics']['budget'];b=after['optics']['budget']
scale=1/a['tx_angular_coverage_fraction']
np.testing.assert_allclose(after['optics']['tx_energy_fraction'],np.asarray(before['optics']['tx_energy_fraction'])*scale,rtol=1e-12)
np.testing.assert_allclose(after['illumination']['signal_photons_per_pixel_per_pulse'],
    np.asarray(before['illumination']['signal_photons_per_pixel_per_pulse'])*scale,rtol=1e-12)
np.testing.assert_array_equal(before['illumination']['background_photons_per_pixel_per_second'],after['illumination']['background_photons_per_pixel_per_second'])
assert b['tx_angular_truncation_j']==0
assert b['tx_angular_coverage_fraction']==1
assert b['tx_domain_output_j']==b['tx_output_j']
np.testing.assert_allclose(b['target_incident_j'],b['tx_output_j']*after['configuration']['experiment']['scene']['atmospheric_one_way_transmission'],rtol=1e-12)
report={'utc':datetime.now(timezone.utc).isoformat(),'before_job':OLD,'after_job':NEW,
        'result_sha256':{job:sha256(path.read_bytes()).hexdigest() for job,path in zip((OLD,NEW),paths)},
        'before_provenance':before['provenance'],'after_provenance':after['provenance'],
        'configuration':after['configuration'],'before_budget':a,'after_budget':b,
        'normalization':after['optics']['tx_energy_normalization'],'signal_scale':scale,
        'checks':{'same_user_config_and_algorithms':True,'all_tx_fractions_normalized':True,
            'signal_scales_at_every_physical_pixel':True,'background_identical':True,
            'tx_domain_energy_conserved':True,'new_job_has_no_angular_truncation_loss':True}}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
print(json.dumps({'scale':scale,'checks':report['checks']},indent=2))
