import pytest
from spad_lidar.models import SimulationConfig


@pytest.mark.parametrize('kind',['spad','system','scan','columns','budget'])
def test_platforms_inherit_user_confirmed_shared_device_defaults(kind):
    base=SimulationConfig()
    cfg=SimulationConfig.for_experiment(kind,{})
    if kind=='budget':cfg=cfg.system
    device=cfg.device
    for key in ('H_binning','V_binning','dcr_cps_per_spad','spad_dead_time_ns','fill_factor'):
        assert getattr(device,key)==getattr(base,key)
    assert device.dcr_cps_per_spad==4000000
    timing=cfg.timing if hasattr(cfg,'timing') else cfg.acquisition
    assert timing.gate_start_ns==base.gate_start_ns
    assert timing.gate_width_ns==base.gate_width_ns
    assert timing.gate_start_ns+timing.gate_width_ns<=timing.period_ns
