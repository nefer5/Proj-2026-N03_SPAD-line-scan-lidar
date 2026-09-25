from ..configuration import read_yaml


def build_spatial_flow(budget,audit):
    from .background_bins import bin_scope_note,spectral_domain_note
    definition=read_yaml('photon-flow.yaml')['spatial']
    formulas=read_yaml('formulas.yaml');notes=read_yaml('formula-notes.yaml')
    values={**budget,'final_mixed_records':audit['final_records'],'spad_dead_losses':audit['spad_dead_losses'],
            'tdc_capacity_losses':audit['tdc_dead_losses']+audit['capacity_losses']}
    steps=[]
    for step in definition['steps']:
        fid=step['formula_id']
        steps.append({**step,'latex':formulas[fid],'symbols':notes[fid],
                      'values':[{**v,'value':values[v['key']]} for v in step['values']]})
    return {'title':definition['title'],'intro':definition['intro']+bin_scope_note(budget['reference_time_bin_ps'])+spectral_domain_note(budget),
            'reference_time_bin_ps':budget['reference_time_bin_ps'],
            'background_integration_band_nm':budget['background_integration_band_nm'],'steps':steps}
