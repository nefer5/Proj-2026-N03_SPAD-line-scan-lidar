"""Migration of pre-unified YAML/JSON inputs; new exports contain no old keys."""
from copy import deepcopy
from .curves import merge_config
from pydantic import TypeAdapter, PositiveInt
import numpy as np


def migrate_pulse_energy(values):
    """Old full-domain energy becomes equivalent power; do not change saved energy."""
    values=deepcopy(values)
    from .experiments.configuration import experiment_defaults
    for group in ('tx','optics'):
        section=values.get(group)
        if not isinstance(section,dict) or 'total_pulse_energy_nj' not in section:continue
        if 'pulse_average_power_w' in section:
            raise ValueError('Do not mix legacy pulse energy and equivalent average power')
        width=section.get('pulse_fwhm_ps',experiment_defaults('system')['tx']['pulse_fwhm_ps'])
        energy=section.pop('total_pulse_energy_nj')
        if not np.isfinite(width) or width<=0 or not np.isfinite(energy) or energy<0:
            raise ValueError('Legacy pulse energy and duration must be finite and nonnegative/positive')
        section['pulse_average_power_w']=energy/(width*1e-3)
    return values


def migrate_budget(values):
    """Budget v1 had explicit Tx edges; retain its energy and angular domain."""
    from math import degrees
    values=deepcopy(values)
    system=values.get('system',{})
    tx=system.get('tx',{})
    if 'geometry' not in values:
        if not all(k in tx for k in ('angle_h_min_mrad','angle_h_max_mrad','angle_v_min_mrad','angle_v_max_mrad')):
            raise ValueError('旧预算缺少完整Tx角域，不能猜测VFOV')
        values['geometry']={'tx_h_width_mrad':tx['angle_h_max_mrad']-tx['angle_h_min_mrad'],
                            'vfov_deg':degrees((tx['angle_v_max_mrad']-tx['angle_v_min_mrad'])*1e-3)}
    values['system']=migrate_pulse_energy(system)
    return values


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
    values=migrate_filter_leakage(values)
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
    values=migrate_pulse_energy(migrate_psf_axes(values))
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


def migrate_psf_axes(values):
    """A scalar historical PSF sigma explicitly meant equal H/V widths."""
    values=migrate_filter_leakage(values)
    for name in ('optics','rx'):
        section=values.get(name)
        if isinstance(section,dict) and 'psf_sigma_um' in section:
            if 'psf_sigma_h_um' in section or 'psf_sigma_v_um' in section:
                raise ValueError('Do not mix scalar and H/V PSF standard deviations')
            sigma=section.pop('psf_sigma_um')
            section['psf_sigma_h_um']=sigma;section['psf_sigma_v_um']=sigma
    return values


def migrate(values, defaults):
    values=migrate_filter_leakage(values)
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


def migrate_filter_curve(spec):
    """A complete old basic schema explicitly implied zero out-of-band light."""
    from .numerics.curves import BasicCurve
    spec=deepcopy(spec)
    basic=spec.get('basic') if isinstance(spec,dict) else None
    if isinstance(basic,dict) and 'out_of_band_transmission' not in basic and set(BasicCurve.model_fields)<=set(basic):
        basic['out_of_band_transmission']=0  # Historical model semantics, not a new default.
    return spec


def migrate_filter_leakage(values):
    values=deepcopy(values)
    spectra=values.get('spectral_inputs')
    if isinstance(spectra,dict) and isinstance(spectra.get('filter'),dict):
        spectra['filter']=migrate_filter_curve(spectra['filter'])
    return values
