"""System budget page and stateless, auditable calculator API."""
from pathlib import Path
from hashlib import sha256
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import HTMLResponse
from ..configuration import Algorithms, read_yaml, parse_yaml, frozen_yaml, yaml_snapshot
from ..models import SimulationConfig
from ..system_budget import calculate_budget

router=APIRouter()
WEB=Path(__file__).resolve().parents[3]/'web'

# Form layout only; values and constraints come from the canonical models/YAML.
GROUPS=[
    ('系统目标','targets',['frame_rate_hz','hfov_deg','scan_time_utilization','slot_count']),
    ('Tx发光归一化角域','geometry',['vfov_deg','tx_h_width_mrad']),
    ('多发与接收门','system.acquisition',['laser_shots','period_ns','gate_start_ns','gate_width_ns','calibration_delay_ns']),
    ('VCSEL与场景','system.tx',['pulse_average_power_w','wavelength_nm','pulse_shape','pulse_fwhm_ps','tx_efficiency','tx_fwhm_h_mrad','tx_fwhm_v_mrad']),
    ('目标与传播','system.scene',['range_m','target_reflectivity','atmospheric_one_way_transmission','overlap_factor']),
    ('Rx光学','system.rx',['rx_aperture_shape','rx_aperture_mm','rx_aperture_width_mm','rx_aperture_height_mm','rx_efficiency','focal_length_h_mm','focal_length_v_mm','psf_sigma_h_um','psf_sigma_v_um']),
    ('Rx独立收光角域','system.rx',['rx_angle_h_min_mrad','rx_angle_h_max_mrad','rx_angle_v_min_mrad','rx_angle_v_max_mrad']),
    ('SPAD与读出','system.spad',['channels_h','channels_v','H_binning','V_binning','pixel_pitch_um','fill_factor','spad_dead_time_ns']),
    ('时间量化','system.readout',['tdc_bin_ps','readout_mode','tdc_dead_time_ns']),
    ('环境光','system.background',['solar_enabled','solar_illuminance_lux','solar_reflectivity','other_light_enabled','other_light_scale']),
    ('复位、电热与限额','assumptions',['reset_time_ns','wall_plug_efficiency','max_average_optical_power_w','max_peak_optical_power_w']),
    ('直方图输出预算','transport',['histogram_count_bits','column_header_bytes','mipi_net_mbps']),
    ('PRBS候选方案 · 独立预算','assumptions',['prbs_enabled','prbs_chip_count','prbs_chip_ns','prbs_on_count'])]


@router.get('/system/budget')
def page():
    html=(WEB/'budget.html').read_text(encoding='utf8')
    for name in ('shared/theme.css', 'shared/theme.js', 'budget.css','budget.js','curve-editor.js','vendor/katex/katex.min.js','vendor/katex/katex.min.css'):
        html=html.replace(f'/static/{name}"',f'/static/{name}?v={sha256((WEB/name).read_bytes()).hexdigest()}"')
    return HTMLResponse(html)


@router.get('/api/system-budget')
def catalog():
    with frozen_yaml(yaml_snapshot()):
        a=Algorithms.load();cfg=SimulationConfig.for_experiment('budget',{},a)
        curves=read_yaml('curve-inputs.yaml')
        curves.update(formulas=read_yaml('formulas.yaml'),formula_notes=read_yaml('formula-notes.yaml'))
        return dict(defaults=cfg.model_dump(),schema=type(cfg).model_json_schema(),groups=GROUPS,
                    help=read_yaml('parameter-help.yaml'),curves=curves,algorithms=a.model_dump(),schema_version=2)


@router.post('/api/system-budget/calculate')
def calculate(values:dict):
    try:
        with frozen_yaml(yaml_snapshot()):
            a=Algorithms.load();cfg=SimulationConfig.for_experiment('budget',values,a)
            return calculate_budget(cfg,a)
    except (ValueError,KeyError,OverflowError) as exc:
        raise HTTPException(422,str(exc)) from exc


@router.post('/api/system-budget/import')
def import_budget(document:str=Body(media_type='text/plain')):
    try:
        import yaml
        with frozen_yaml(yaml_snapshot()):
            doc=parse_yaml(document)
            if set(doc)!={'schema_version','kind','experiment'} or doc['schema_version'] not in (1,2) or doc['kind']!='hardware-budget':
                raise ValueError('需要 schema_version: 1或2、kind: hardware-budget、experiment；旧缓存已保留，未静默迁移。')
            if doc['schema_version']==1:
                from ..legacy_config import migrate_budget
                doc['experiment']=migrate_budget(doc['experiment'])
            return SimulationConfig.for_experiment('budget',doc['experiment']).model_dump()
    except (ValueError,KeyError,yaml.YAMLError) as exc:
        raise HTTPException(422,str(exc)) from exc
