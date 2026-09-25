"""Source-separated stationary candidate expectations per nominal hardware bin."""
from copy import deepcopy
from ..configuration import read_yaml


def background_bin_values(solar_rate_cps,other_rate_cps,bin_ps):
    factor=bin_ps*1e-12
    return {'solar_mean_candidates_per_time_bin':solar_rate_cps*factor,
            'other_mean_candidates_per_time_bin':other_rate_cps*factor,
            'reference_time_bin_ps':bin_ps}


def spatial_background_bin_values(budget,bin_ps):
    return background_bin_values(budget['solar_candidate_rate_cps'],budget['other_candidate_rate_cps'],bin_ps)


def bin_scope_note(bin_ps):
    return f' 每time_bin解析值=全阵列候选计数率（已含PDE/FF）×{bin_ps:g} ps，不含死时间和读出损失。'


def spectral_domain_note(budget):
    domain=budget.get('background_integration_domain')
    if not domain or domain['out_of_band_transmission']==0:return ''
    lo,hi=domain['band_nm']
    text=f' 带外透过率为{domain["out_of_band_transmission"]:g}，背景积分域为{lo:g}–{hi:g} nm。'
    if domain['rx_coverage_limited']:
        req=domain['requested_band_nm']
        text+=f' 源光谱请求范围{req[0]:g}–{req[1]:g} nm受Rx响应表覆盖限制；表外光学响应未建模，不能视为已被完全阻断。'
    return text


def decorate_saved_flow(flow,budget,gate_width_ns,bin_ps,kind):
    """Extend the view of an immutable result; preserve its original stages."""
    if flow is None:return None
    view=deepcopy(flow)
    # Compatibility only: old files stored a rate multiplied by their original
    # reference interval. Recover that analytical rate without using observations.
    rates=dict(budget)
    for source in ('solar','other'):
        key=source+'_candidate_rate_cps'
        if key not in rates:rates[key]=budget[source+'_candidate_avalanches_per_gate']/(gate_width_ns*1e-9)
    values=spatial_background_bin_values(rates,bin_ps)
    rows={v['key']:v for step in read_yaml('photon-flow.yaml')[kind]['steps'] for v in step['values']
          if v['key'].endswith('_mean_candidates_per_time_bin')}
    for step in view['steps']:
        step['values']=[{**row,**rows[row['key']],'value':values[row['key']]} if row['key'] in rows else row for row in step['values']]
        keys={v['key'] for v in step['values']}
        for source in ('solar','other'):
            key=source+'_mean_candidates_per_time_bin'
            anchors={source+'_sensor_incident_photons_per_gate',source+'_sensor_incident_photons_total'}
            if keys&anchors and key not in keys:step['values'].append({**rows[key],'value':values[key]})
    view['reference_time_bin_ps']=bin_ps
    if '每time_bin解析值=' not in view['intro']:view['intro']+=bin_scope_note(bin_ps)
    if '带外透过率为' not in view['intro']:view['intro']+=spectral_domain_note(budget)
    return view
