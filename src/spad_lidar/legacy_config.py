"""Migration of pre-unified YAML/JSON inputs; new exports contain no old keys."""
from copy import deepcopy
from .curves import merge_config
from pydantic import TypeAdapter, PositiveInt


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
