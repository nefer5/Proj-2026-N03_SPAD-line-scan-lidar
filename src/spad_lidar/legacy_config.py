"""Migration of pre-unified YAML/JSON inputs; new exports contain no old keys."""
from copy import deepcopy
from .curves import merge_config
from pydantic import TypeAdapter, PositiveInt
import numpy as np


def migrate_optical_dataset(document):
    """Preserve physical directions when converting legacy V/y-down data to up."""
    doc=deepcopy(document)
    if doc.get('schema_version')!=1:return doc
    if doc.get('coordinate_convention')!='optical_H_right_V_down__image_x_right_y_down':
        raise ValueError('Legacy optical dataset requires its explicit coordinate convention')
    tx,rx=doc['tx'],doc['rx']
    tx['v_edges_mrad']=(-np.asarray(tx['v_edges_mrad'])[::-1]).tolist()
    tx['energy_fraction']=np.asarray(tx['energy_fraction'])[::-1].tolist()
    rx['v_angle_mrad']=(-np.asarray(rx['v_angle_mrad'])[::-1]).tolist()
    rx['y_edges_um']=(-np.asarray(rx['y_edges_um'])[::-1]).tolist()
    rx['collection_efficiency']=np.asarray(rx['collection_efficiency'])[:,::-1,:].tolist()
    rx['psf_pixel_fraction']=np.asarray(rx['psf_pixel_fraction'])[:,::-1,:,::-1,:].tolist()
    doc['schema_version']=2
    doc['coordinate_convention']='optical_H_right_V_up__image_x_right_y_up'
    doc['provenance']={**doc['provenance'],'coordinate_migration':'v1 V/y-down → v2 V/y-up: reversed and negated V and y axes; array axes reindexed, no energy renormalization.'}
    return doc


def migrate_experiment_overrides(kind,values):
    """Migrate legacy B/C groups through one explicit domain conversion."""
    values=deepcopy(values)
    if kind=='system':
        return migrate_b_domains(values)
    if kind=='scan':
        extra={key:values.pop(key) for key in ('scan','scene_motion') if key in values}
        return {**migrate_b_domains(values),**extra}
    return values


def migrate_focal_lengths(optical):
    if 'focal_length_mm' in optical:
        if any(k in optical for k in ('focal_length_h_mm','focal_length_v_mm')):
            raise ValueError('Do not mix scalar and H/V focal lengths')
        value=optical.pop('focal_length_mm')
        optical['focal_length_h_mm']=value
        optical['focal_length_v_mm']=value
        if 'mapping_mode' not in optical:
            optical['mapping_mode']='legacy_upright'
        # The old scalar schema used V/y positive-down; preserve physical rays.
        for key in ('tx_center_v_mrad','rx_offset_y_um'):
            if key in optical:optical[key]=-optical[key]
        for lo,hi in (('angle_v_min_mrad','angle_v_max_mrad'),('rx_angle_v_min_mrad','rx_angle_v_max_mrad')):
            if lo in optical and hi in optical:
                optical[lo],optical[hi]=-optical[hi],-optical[lo]


def migrate_b_domains(values):
    from .experiments.system_config import LEGACY_PATHS
    values=deepcopy(values)
    if not any(k in values for k in ('optics','device','timing','rng_seed')):
        if isinstance(values.get('rx'),dict) and values['rx'].get('dataset') is not None:
            values['rx']['dataset']=migrate_optical_dataset(values['rx']['dataset'])
        return values
    if any(k in values for k in ('tx','scene','rx','spad','background','acquisition')):
        raise ValueError('Do not mix legacy and modular B configuration groups')
    if isinstance(values.get('optics'),dict):
        o=values['optics'];migrate_focal_lengths(o)
        keys=('angle_h_min_mrad','angle_h_max_mrad','angle_v_min_mrad','angle_v_max_mrad')
        if all(k in o for k in keys) and not any('rx_'+k in o for k in keys):
            for k in keys:o['rx_'+k]=o[k]
    result={}
    for group,section in values.items():
        if group in ('readout','spectral_inputs'):
            result[group]=section;continue
        items=[(group,section)] if group=='rng_seed' else [(group+'.'+k,v) for k,v in section.items()] if isinstance(section,dict) else []
        if not items and group not in ('optics','device','timing'):
            raise ValueError(f'Unknown configuration group: {group}')
        if not isinstance(section,dict) and group!='rng_seed':
            raise ValueError(f'{group} must be a mapping')
        for path,value in items:
            if path not in LEGACY_PATHS:raise ValueError(f'Unknown configuration key: {path}')
            target,key=LEGACY_PATHS[path].split('.')
            result.setdefault(target,{})[key]=value
    if isinstance(result.get('rx'),dict) and result['rx'].get('dataset') is not None:
        result['rx']['dataset']=migrate_optical_dataset(result['rx']['dataset'])
    return result


def migrate(values, defaults):
    values=deepcopy(values)
    if 'spads_per_channel' in values:
        if 'H_binning' in values or 'V_binning' in values:
            raise ValueError('Do not mix spads_per_channel with H_binning/V_binning')
        count=TypeAdapter(PositiveInt).validate_python(values.pop('spads_per_channel'), strict=True)
        # A legacy total cannot determine the original 2D shape; use one row.
        values['H_binning']=count
        values['V_binning']=1
    groups={
        "filter":("filter_curve","filter_interpolation","filter_bandwidth_nm","filter_peak_transmission"),
        "other":("other_light_spectrum","other_light_interpolation","other_light_mode","background_spectral_radiance"),
        "pde":("pde_spectrum","pde_interpolation","pde_mode","pde"),
    }
    spectra=deepcopy(values.get("spectral_inputs",{}))
    for name,keys in groups.items():
        if not any(key in values for key in keys):continue
        if name in spectra:
            raise ValueError(f"Do not mix legacy {name} fields with spectral_inputs.{name}")
        spec=deepcopy(defaults["spectral_inputs"][name])
        points_key,method_key=keys[:2]
        if method_key in values:spec["interpolation"]=values[method_key]
        points=values.get(points_key)
        if name=="filter":
            if points_key in values and points is not None:
                spec["mode"]="manual"
            elif points_key in values or any(k in values for k in keys[2:]):
                spec["mode"]="basic";spec["basic"]["shape"]="rectangle"
                b=spec["basic"]
                b["center_nm"]=values.get("wavelength_nm",defaults["wavelength_nm"])
                b["width_nm"]=values.get("filter_bandwidth_nm",b["width_nm"])
                b["amplitude"]=values.get("filter_peak_transmission",b["amplitude"])
                b["min_nm"]=b["center_nm"]-b["width_nm"]/2
                b["max_nm"]=b["center_nm"]+b["width_nm"]/2
            value_key="transmission"
        else:
            mode=values.get(keys[2])
            if mode not in (None,"constant","spectrum"):
                raise ValueError(f"Invalid legacy {keys[2]}")
            if mode=="constant" or mode is None and keys[3] in values and points_key not in values:
                spec["mode"]="basic";spec["basic"]["shape"]="constant"
            elif mode=="spectrum" or points_key in values:spec["mode"]="manual"
            if keys[3] in values:spec["basic"]["amplitude"]=values[keys[3]]
            value_key="radiance" if name=="other" else "pde"
        if points is not None:
            converted=[]
            for p in points:
                p=p.model_dump() if hasattr(p,"model_dump") else p
                if set(p)!={"wavelength_nm",value_key}:raise ValueError("Unknown legacy spectrum point fields")
                converted.append({"wavelength_nm":p["wavelength_nm"],"value":p[value_key]})
            spec["manual_points"]=converted
        for key in keys:values.pop(key,None)
        spectra[name]=spec
    if spectra:values["spectral_inputs"]=spectra
    return merge_config(defaults,values)
