import numpy as np
import pytest
from spad_lidar.models import SimulationConfig
from spad_lidar.configuration import Algorithms
from spad_lidar.spectra import spectral_components, solar_normalization
from spad_lidar.simulator import photon_budget
from spad_lidar.constants import H,C


def test_reference_spectrum_and_lux_scaling():
    lux,irradiance=solar_normalization(6)
    assert irradiance==pytest.approx(1000.3706556,rel=1e-7)
    assert 100000<lux<120000
    a=photon_budget(SimulationConfig(solar_illuminance_lux=50000))
    b=photon_budget(SimulationConfig(solar_illuminance_lux=100000))
    assert b.solar_detected_per_gate==pytest.approx(2*a.solar_detected_per_gate)
    assert b.other_light_detected_per_gate==a.other_light_detected_per_gate


def test_switches_and_pde_zero():
    off=photon_budget(SimulationConfig(solar_enabled=False,other_light_enabled=False))
    assert off.background_detected_per_gate==0
    zero=photon_budget(SimulationConfig(pde_mode='constant',pde=0))
    assert zero.signal_detected_per_pulse==0
    assert zero.background_detected_per_gate==0
    assert zero.dark_detected_per_gate>0


def test_constant_limit_matches_known_photon_budget():
    cfg=SimulationConfig(solar_enabled=False,other_light_mode='constant',pde_mode='constant')
    b=photon_budget(cfg)
    power=cfg.background_spectral_radiance*b.aperture_area_m2*b.channel_solid_angle_sr*cfg.rx_efficiency*b.filter_enbw_nm
    expected=power*cfg.gate_width_ns*1e-9/(H*C/(cfg.wavelength_nm*1e-9))*cfg.pde*cfg.fill_factor
    assert b.background_detected_per_gate==pytest.approx(expected)


def test_joint_integral_independent_of_plot_and_quadrature_convergence():
    cfg=SimulationConfig(wavelength_nm=905, pde_mode='constant', pde=0.18)
    a=Algorithms.load()
    first=spectral_components(cfg,a,plot=True)
    second=spectral_components(cfg,a.model_copy(update={'spectral_quadrature_order':8,'spectral_plot_samples':31}),plot=True)
    for key in ('solar_detectable_photons_s_m2_sr','other_detectable_photons_s_m2_sr'):
        assert first[key]==pytest.approx(second[key],rel=1e-12)
    assert len(first['curves']['wavelength_nm'])!=len(second['curves']['wavelength_nm'])
    assert first['pde_at_laser']==pytest.approx(0.18)


def test_background_components_sum_and_reflectivity_only_affects_solar():
    a=photon_budget(SimulationConfig())
    b=photon_budget(SimulationConfig(solar_reflectivity=0))
    assert a.background_detected_per_gate==pytest.approx(a.solar_detected_per_gate+a.other_light_detected_per_gate)
    assert b.solar_detected_per_gate==0
    assert b.other_light_detected_per_gate==a.other_light_detected_per_gate
