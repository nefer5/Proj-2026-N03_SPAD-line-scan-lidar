import json
from pathlib import Path
import numpy as np
x=json.loads(Path('web/prototypes/c-exposure/reference.json').read_text(encoding='utf8'))['high_level']
i=x['inputs'];d=x['derived']
np.testing.assert_allclose(d['frame_period_ns']*i['frame_rate_hz'],1e9)
np.testing.assert_allclose(d['scan_allocatable_ns']+d['non_scan_ns'],d['frame_period_ns'])
np.testing.assert_allclose(d['slot_max_ns']*i['slot_count'],d['scan_allocatable_ns'])
assert d['slot_target_ns']<=d['slot_max_ns']
np.testing.assert_allclose(d['angle_per_slot_mrad']*i['slot_count'],i['hfov_mrad'])
np.testing.assert_allclose(d['required_average_optical_rad_s']*d['scan_allocatable_ns']*1e-9,i['hfov_mrad']*1e-3)
assert len(x['formulas'])==3
print(json.dumps({'status':'passed','inputs':i,'derived':d},ensure_ascii=False,indent=2))