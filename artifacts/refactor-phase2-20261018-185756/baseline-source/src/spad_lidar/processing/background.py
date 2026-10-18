"""Pure candidate-rate to hardware-bin expectations; no display or YAML IO."""


def background_bin_values(solar_rate_cps,other_rate_cps,bin_ps):
    factor=bin_ps*1e-12
    return {'solar_mean_candidates_per_time_bin':solar_rate_cps*factor,
            'other_mean_candidates_per_time_bin':other_rate_cps*factor,
            'reference_time_bin_ps':bin_ps}



def spatial_background_bin_values(budget,bin_ps):
    return background_bin_values(budget['solar_candidate_rate_cps'],budget['other_candidate_rate_cps'],bin_ps)

