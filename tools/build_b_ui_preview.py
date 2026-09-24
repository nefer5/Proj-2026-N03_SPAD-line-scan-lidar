"""Export an optional frozen prototype fixture from the production B core."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms,read_yaml
from spad_lidar.experiments.spatial_analysis import run_system_analysis
from spad_lidar.reporting.spatial_view import channel_db_tables
OUT=ROOT/'web/prototypes/b-optics'
EVIDENCE=ROOT/'artifacts/ui-prototypes/current'

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf8')

def build_data():
    cfg=SimulationConfig.for_experiment('system',{});a=Algorithms.load()
    result=run_system_analysis(cfg,a,lambda *args:None,lambda:False)
    save(EVIDENCE/'original-result.json',result)
    result['illumination']=np.asarray(result['illumination']['signal_photons_per_pixel_per_pulse']).reshape(result['optics']['array_shape']).tolist()
    result['help']=read_yaml('parameter-help.yaml');result['readout_modes']=read_yaml('readout-modes.yaml')
    result['preview']={'revision':3,'interface_configuration':result['form_configuration'],
                       'note':'Frozen production-core output; prototype edits do not recalculate.',
                       'inherited_default_values':SimulationConfig().model_dump()}
    save(OUT/'snapshot.json',result)

def fingerprint():
    template = (OUT / 'index.template.html').read_text(encoding='utf-8')
    for name in ('preview.css', 'preview.js', 'preview-panels.js', 'snapshot.json'):
        digest = hashlib.sha256((OUT / name).read_bytes()).hexdigest()[:16]
        template = template.replace('{{' + name + '}}', name + '?v=' + digest)
    for token, filename in (('katex.css', 'katex.min.css'), ('katex.js', 'katex.min.js')):
        digest = hashlib.sha256((ROOT / 'web/vendor/katex' / filename).read_bytes()).hexdigest()[:16]
        template = template.replace('{{' + token + '}}', '../../vendor/katex/' + filename + '?v=' + digest)
    digest=hashlib.sha256((ROOT/'web/shared/histogram-window.js').read_bytes()).hexdigest()[:16]
    template=template.replace('{{histogram-window.js}}','../../shared/histogram-window.js?v='+digest)
    (OUT / 'index.html').write_text(template, encoding='utf-8')


if __name__ == '__main__':
    if '--assets-only' not in sys.argv:
        build_data()
    if (OUT / 'index.template.html').exists():
        fingerprint()
