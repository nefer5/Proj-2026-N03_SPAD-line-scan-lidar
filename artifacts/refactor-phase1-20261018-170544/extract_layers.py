"""One-shot, checked extraction from the preserved working-tree baseline."""
from pathlib import Path
import ast,hashlib,json
ROOT=Path(__file__).resolve().parents[2]
MANIFEST=json.loads((Path(__file__).parent/'before-manifest.json').read_text(encoding='utf8'))['files']
def read(name):
    p=ROOT/'src/spad_lidar'/name
    assert hashlib.sha256(p.read_bytes()).hexdigest()==MANIFEST[p.relative_to(ROOT).as_posix()],f'Changed since checkpoint: {p}'
    return p.read_text(encoding='utf8')
def write(name,text):
    p=ROOT/'src/spad_lidar'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8',newline='\n')
def segment(text,name):
    n=next(n for n in ast.parse(text).body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name==name)
    lines=text.splitlines(keepends=True);start=min([n.lineno]+[d.lineno for d in n.decorator_list])-1
    return ''.join(lines[start:n.end_lineno])
spatial=read('experiments/spatial.py');config=read('experiments/configuration.py');system=read('experiments/system_config.py');lab=read('experiments/lab.py');background=read('reporting/background_bins.py')
optical=segment(spatial,'OpticalConfig');timing=segment(config,'TimingConfig')
write('domains/__init__.py','"""Shared strict domain definitions; defaults remain in YAML."""\n')
write('domains/optical.py','"""Shared optical field definitions and validated flat compatibility view."""\nfrom typing import Literal\nfrom pydantic import Field, model_validator\nfrom ..spad.config import StrictConfig\n\n\n'+optical+'\n')
write('domains/acquisition.py','"""Periodic acquisition fields, independent of experiment composition."""\nfrom pydantic import Field, model_validator\nfrom ..spad.config import StrictConfig\n\n\n'+timing+'\n')
fields=system[system.index('OPTICAL_GROUPS ='):system.index('LEGACY_PATHS =')]
write('domains/system.py','"""Canonical optical/device domain types; no experiment or YAML dependency."""\nfrom copy import deepcopy\nfrom pydantic import Field, create_model\nfrom ..spad.config import StrictConfig, DeviceConfig\nfrom .acquisition import TimingConfig\nfrom .optical import OpticalConfig\n\n\n'+fields)
config=config.replace(timing,'from ..domains.acquisition import TimingConfig  # Compatibility export.\n')
write('experiments/configuration.py',config)
system=system.replace('from .configuration import TimingConfig','from ..domains.acquisition import TimingConfig').replace('from .spatial import OpticalConfig','from ..domains.optical import OpticalConfig')
system=system.replace(fields,'from ..domains.system import (OPTICAL_GROUPS, optical_fields, TxConfig, SceneConfig,\n    RxConfig, SpadArrayConfig, BackgroundConfig, AcquisitionConfig)\n\n\n')
write('experiments/system_config.py',system)

header='''"""Shared spatial optical projection, separate from experiment execution."""
from types import SimpleNamespace
from hashlib import sha256
import json
import numpy as np
from ..curves import Curve
from ..constants import C, H
from ..contracts import SensorIllumination
from ..tx import angular_profile, transmit, normalize_angular_weights
from ..scene import lambertian_return
from ..rx.budget import aperture_area
from ..rx.spatial import synthetic_receiver
from ..rx.response import ReceiverResponse
from ..rx.projection import project_return
from ..adapters.optical_data import validate_dataset, RxTable
from ..spectra import spectral_components, background_spectral_domain
from ..contracts.spectral_product import SpectralProduct, export_spectral
from ..spad.device import effective_pde


'''
functions='\n\n'.join(segment(spatial,name) for name in ('optical_dataset','project_illumination'))
functions=functions.replace('from ..reporting.background_bins import spatial_background_bin_values','from ..processing.background import spatial_background_bin_values')
write('optics/service.py',header+functions+'\n')
write('optics/__init__.py','"""Public shared optical composition entry points."""\nfrom .service import optical_dataset, project_illumination\n\n__all__ = ["optical_dataset", "project_illumination"]\n')
for name in ('optical_dataset','project_illumination'):spatial=spatial.replace(segment(spatial,name),'')
spatial=spatial.replace(optical,'from ..domains.optical import OpticalConfig  # Compatibility export.\nfrom ..optics import optical_dataset, project_illumination\n')
# Keep experiment-only imports out of the optical service and trim old physical imports.
for line in spatial.splitlines(keepends=True)[:24]:
    if any(line.startswith(prefix) for prefix in ('from types ','from hashlib ','import json','import numpy ','from ..constants ','from ..contracts ','from ..tx ','from ..scene ','from ..rx.','from ..adapters.','from ..spectra ','from ..contracts.spectral_product ','from ..spad.device ')):
        spatial=spatial.replace(line,'',1)
write('experiments/spatial.py',spatial)

write('processing/background.py','"""Pure candidate-rate to hardware-bin expectations; no display or YAML IO."""\n\n\n'+segment(background,'background_bin_values')+'\n\n\n'+segment(background,'spatial_background_bin_values')+'\n')
for name in ('background_bin_values','spatial_background_bin_values'):background=background.replace(segment(background,name),'')
background=background.replace('from ..configuration import read_yaml','from ..configuration import read_yaml\nfrom ..processing.background import background_bin_values, spatial_background_bin_values')
write('reporting/background_bins.py',background)

write('acquisition/__init__.py','"""Shared experiment orchestration above the SPAD state engine."""\n')
write('acquisition/adapters/__init__.py','"""Record adapters retain their experiment-specific clock and gate semantics."""\n')
adapter='''"""Periodic record quantization, shared by direct SPAD, B and legacy C."""
import numpy as np
from ...spad.device import apply_jitter
from ...processing.records import histogram_records


'''+segment(lab,'acquire_candidates').replace('from ..spad.acquisition import evolve_program','from ...spad.acquisition import evolve_program')+'\n'
write('acquisition/adapters/periodic.py',adapter)
lab=lab.replace(segment(lab,'acquire_candidates'),'from ..acquisition.adapters.periodic import acquire_candidates  # Compatibility export.\n')
write('experiments/lab.py',lab)

# Redirect actual runtime users. The old modules still export identical objects.
for p in (ROOT/'src/spad_lidar').rglob('*.py'):
    if p.name=='spatial.py' and p.parent.name=='experiments':continue
    text=p.read_text(encoding='utf8');changed=text
    changed=changed.replace('from .experiments.spatial import project_illumination','from .optics import project_illumination')
    changed=changed.replace('from ..experiments.spatial import project_illumination','from ..optics import project_illumination').replace('from ..experiments.spatial import optical_dataset','from ..optics import optical_dataset')
    if p.parent.name=='experiments':
        changed=changed.replace('from .spatial import project_illumination, finish_system, system_program','from ..optics import project_illumination\nfrom .spatial import finish_system, system_program').replace('from .spatial import project_illumination','from ..optics import project_illumination')
    changed=changed.replace('from .reporting.background_bins import background_bin_values','from .processing.background import background_bin_values')
    if changed!=text:p.write_text(changed,encoding='utf8',newline='\n')
print('Extracted shared domains, optical service, periodic record adapter and background numerics.')
