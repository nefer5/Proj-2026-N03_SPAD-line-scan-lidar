"""System budget page and stateless, auditable calculator API."""
from pathlib import Path
from hashlib import sha256
import json
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import HTMLResponse
from ..configuration import Algorithms, read_yaml, parse_yaml, frozen_yaml, yaml_snapshot
from ..models import SimulationConfig
from ..system_budget import calculate_budget
from .budget_form import FORM_LAYOUT

router=APIRouter()
WEB=Path(__file__).resolve().parents[3]/'web'

# Form layout only; values and constraints come from the canonical models/YAML.
GROUPS=[
 ('系统目标','targets',['frame_rate_hz','hfov_deg','scan_time_utilization','slot_count']),
 ('系统垂直覆盖','geometry',['vfov_deg']),
 ('LiDAR线数','system.spad',['channels_v']),
 ('Tx · 光源与脉冲','system.tx',['pulse_average_power_w','wavelength_nm','pulse_shape','pulse_fwhm_ps','tx_efficiency']),
 ('Tx · 单通道角域','geometry',['tx_h_width_mrad']),
 ('Tx · 列内多发','system.acquisition',['laser_shots','period_ns']),
 ('场景','system.scene',['range_m','target_reflectivity','atmospheric_one_way_transmission','overlap_factor']),
 ('Rx · 单通道收光角域','rx_channel',['h_width_mrad','v_width_deg']),
 ('Rx · 接收光学','system.rx',['rx_aperture_shape','rx_aperture_mm','rx_aperture_width_mm','rx_aperture_height_mm','rx_efficiency','focal_length_h_mm','focal_length_v_mm','psf_sigma_h_um','psf_sigma_v_um']),
 ('Rx · 门控与标定','system.acquisition',['gate_start_ns','gate_width_ns','calibration_delay_ns']),
 ('SPAD · 通道内像素','system.spad',['H_binning','V_binning','pixel_pitch_um','fill_factor','spad_dead_time_ns','spad_jitter_fwhm_ps']),
 ('SPAD · 数字读出','system.readout',['tdc_bin_ps','readout_mode','tdc_dead_time_ns']),
 ('环境光','system.background',['solar_enabled','solar_illuminance_lux','solar_reflectivity','other_light_enabled','other_light_scale']),
 ('高级 · 电热与限额','assumptions',['reset_time_ns','wall_plug_efficiency','max_average_optical_power_w','max_peak_optical_power_w']),
 ('电学 · 输出格式','transport',['payload_format','histogram_count_bits','point_bytes','column_header_bytes','mipi_net_mbps']),
 ('电学 · 芯片与MIPI','electrical',['capacity_mode','channels_per_chip','chips_per_link','data_lanes_per_link','lane_rate_mbps','payload_efficiency','available_links','chip_header_bytes','histogram_mode','ready_delay_us','buffer_architecture','handoff_policy','hist_copy_us','bank_clear_us','dsp_time_us','mipi_pack_us','echo_max_count','echo_max_bins','echo_descriptor_bytes','packet_payload_bytes','line_short_packets','burst_gap_us']),
 ('距离参考 · 理想扫参','range_reference',['enabled','min_range_m','max_range_m','points','area_kind']),
 ('高级 · PRBS预算','assumptions',['prbs_enabled','prbs_chip_count','prbs_chip_ns','prbs_on_count'])]


@router.get('/system/budget')
def page():
    html=(WEB/'budget.html').read_text(encoding='utf8')
    try:
        manifest=json.loads((WEB/'vendor/three/manifest.json').read_text(encoding='utf8'))
    except (OSError,ValueError):
        # Keep the budget usable. The module script displays an explicit load error.
        manifest={'imports':{}}
    html=html.replace('__THREE_IMPORT_MAP__',json.dumps({'imports':manifest['imports']}).replace('<','\\u003c'))
    for name in ('budget-pipeline.js','budget-hardware.js','budget-charts.js','shared/number-format.js','budget-scene.js','budget-scene.css','shared/theme.css', 'shared/theme.js', 'budget.css','budget.js','curve-editor.js','vendor/katex/katex.min.js','vendor/katex/katex.min.css'):
        html=html.replace(f'/static/{name}"',f'/static/{name}?v={sha256((WEB/name).read_bytes()).hexdigest()}"')
    return HTMLResponse(html)


@router.get('/api/system-budget')
def catalog():
    with frozen_yaml(yaml_snapshot()):
        a=Algorithms.load();cfg=SimulationConfig.for_experiment('budget',{},a)
        curves=read_yaml('curve-inputs.yaml')
        curves.update(formulas=read_yaml('formulas.yaml'),formula_notes=read_yaml('formula-notes.yaml'))
        return dict(defaults=cfg.model_dump(),schema=type(cfg).model_json_schema(),groups=GROUPS,form_layout=FORM_LAYOUT,
                    help=read_yaml('parameter-help.yaml'),curves=curves,algorithms=a.model_dump(),schema_version=7)


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
            if set(doc)!={'schema_version','kind','experiment'} or doc['schema_version'] not in (1,2,3,4,5,6,7) or doc['kind']!='hardware-budget':
                raise ValueError('需要 schema_version: 1–7、kind: hardware-budget、experiment；旧缓存已保留，未静默迁移。')
            if doc['schema_version']<3:
                from ..legacy_config import migrate_budget_v3
                doc['experiment']=migrate_budget_v3(doc['experiment'])
            if doc['schema_version']<5:
                from ..legacy_config import migrate_budget_v5
                doc['experiment']=migrate_budget_v5(doc['experiment'])
            if doc['schema_version']<6:
                from ..legacy_config import migrate_budget_v6
                doc['experiment']=migrate_budget_v6(doc['experiment'])
            if doc['schema_version']<7:
                from ..legacy_config import migrate_budget_v7
                doc['experiment']=migrate_budget_v7(doc['experiment'])
            return SimulationConfig.for_experiment('budget',doc['experiment']).model_dump()
    except (ValueError,KeyError,yaml.YAMLError) as exc:
        raise HTTPException(422,str(exc)) from exc


@router.post('/api/system-budget/measurements')
def measurements(document:str=Body(media_type='text/plain')):
    import csv,io
    from ..budget_extensions import RangeMeasurement
    try:
        if not document.strip():return []
        data=csv.DictReader(io.StringIO(document.lstrip('\ufeff')))
        allowed=set(RangeMeasurement.model_fields)
        if not data.fieldnames or 'distance_m' not in data.fieldnames or len(set(data.fieldnames))!=len(data.fieldnames) or set(data.fieldnames)-allowed:
            raise ValueError('CSV需要distance_m；可选area_counts,peak_counts,fwhm_ns,range_std_mm,range_bias_mm，禁止未知或重复表头')
        out=[];limit=Algorithms.load().budget_reference_max_measurements
        for row in data:
            if len(out)>=limit:raise ValueError('Measurement count exceeds algorithm limit')
            if None in row:raise ValueError('CSV行列数不匹配')
            item={key:float(row[key]) if row.get(key) is not None and row[key].strip() else None for key in allowed}
            out.append(RangeMeasurement.model_validate(item).model_dump())
        return out
    except (ValueError,TypeError) as exc:raise HTTPException(422,str(exc)) from exc
