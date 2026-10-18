"""Identify literature datasets by values, never by a potentially stale filename."""
import json
from hashlib import sha256
from .configuration import read_yaml

def pde_provenance(cfg):
    spec=cfg.spectral_inputs.pde
    if spec.mode not in ('csv','manual'):
        return None
    active=[(float(p.wavelength_nm),float(p.value)) for p in getattr(spec,spec.mode+'_points')]
    fingerprint=sha256(json.dumps(active,separators=(',',':')).encode()).hexdigest()
    for identifier,metadata in read_yaml('pde-datasets.yaml').items():
        if fingerprint!=metadata['points_sha256']:
            continue
        keys=('title','url','pdf_url','excess_bias_v','wavelength_range_nm','extraction',
              'reported_peak','reported_nir','uncertainty_note','definition_note','fill_factor_note','domain_note',
              'digitized_range_nm','extrapolation')
        return {'id':identifier,'matched_by':'point_values_sha256','points_sha256':fingerprint,**{k:metadata[k] for k in keys}}
    return None
