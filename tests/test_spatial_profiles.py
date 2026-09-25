from copy import deepcopy
import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import ndtr
from fastapi.testclient import TestClient
from spad_lidar.api import app
from spad_lidar.configuration import Algorithms
from spad_lidar.models import SimulationConfig
from spad_lidar.numerics.spatial_profiles import scale_from_sigma,scale_from_fwhm,profile_density,profile_bin_mass
from spad_lidar.experiments.spatial import project_illumination,optical_dataset
from spad_lidar.reporting.spatial_view import optical_view


@pytest.mark.parametrize('order',[1,2,4,16,32])
def test_density_energy_variance_and_fwhm(order):
    sigma=3.;scale=scale_from_sigma(sigma,order)
    norm=2*quad(lambda x:profile_density(x,scale,order),0,np.inf,epsabs=1e-10)[0]
    variance=2*quad(lambda x:x*x*profile_density(x,scale,order),0,np.inf,epsabs=1e-9)[0]
    assert norm==pytest.approx(1,rel=1e-9)
    assert variance==pytest.approx(sigma**2,rel=1e-9)
    width=7.;scale=scale_from_fwhm(width,order)
    assert profile_density(width/2,scale,order)/profile_density(0,scale,order)==pytest.approx(.5)
    bins=profile_bin_mass(np.array([-np.inf,-2.,0.,2.,np.inf]),scale,order)
    assert np.all(bins>=0) and bins.sum()==pytest.approx(1)
    np.testing.assert_allclose(bins,bins[::-1])


def test_order_one_is_gaussian_and_tail_integral_is_nonnegative():
    sigma=2.;edges=np.linspace(-8,8,31)
    actual=profile_bin_mass(edges,scale_from_sigma(sigma,1),1)
    np.testing.assert_allclose(actual,np.diff(ndtr(edges/sigma)),rtol=1e-10)
    for order in (1,2,8):
        mass=profile_bin_mass(np.linspace(2,8,31),scale_from_sigma(sigma,order),order)
        assert np.all(mass>=0)


def test_legacy_sigma_axes_and_unknown_mixed_input_validation():
    for group in ('rx','optics'):
        cfg=SimulationConfig.for_experiment('system',{group:{'psf_sigma_um':3.5}})
        assert cfg.rx.psf_sigma_h_um==cfg.rx.psf_sigma_v_um==3.5
        assert 'psf_sigma_um' not in cfg.rx.model_dump()
        with pytest.raises(ValueError,match='mix'):
            SimulationConfig.for_experiment('system',{group:{'psf_sigma_um':3.5,'psf_sigma_h_um':2}})
    cfg=SimulationConfig.for_experiment('columns',{'rx':{'psf_sigma_um':5}})
    assert cfg.rx.psf_sigma_h_um==cfg.rx.psf_sigma_v_um==5


def test_super_gaussian_order_one_preserves_gaussian_photons():
    a=Algorithms.load();base=SimulationConfig.for_experiment('system',{})
    super_cfg=SimulationConfig.for_experiment('system',{'tx':{'tx_model':'super_gaussian','tx_order_h':1,'tx_order_v':1},
        'rx':{'rx_model':'super_gaussian_psf','psf_order_h':1,'psf_order_v':1}})
    left=project_illumination(base,a,lambda *_:None,lambda:False)
    right=project_illumination(super_cfg,a,lambda *_:None,lambda:False)
    np.testing.assert_allclose(left[0].signal_photons_per_pulse,right[0].signal_photons_per_pulse,rtol=1e-12,atol=0)
    np.testing.assert_array_equal(left[0].background_photons_per_second,right[0].background_photons_per_second)


def test_anisotropic_psf_and_independent_preview_keep_physical_losses():
    a=Algorithms.load();cfg=SimulationConfig.for_experiment('system',{'tx':{'tx_model':'super_gaussian','tx_order_h':2,'tx_order_v':4},
        'rx':{'rx_model':'super_gaussian_psf','psf_sigma_h_um':4,'psf_sigma_v_um':12,'psf_order_h':2,'psf_order_v':3}})
    light,groups,info=project_illumination(cfg,a,lambda *_:None,lambda:False)
    assert np.sum(info['tx_energy_fraction'])==pytest.approx(1)
    assert info['budget']['target_incident_j']==pytest.approx(cfg.tx.total_pulse_energy_nj*1e-9*cfg.tx.tx_efficiency*cfg.scene.atmospheric_one_way_transmission)
    view=optical_view(cfg,a,info);f=view['parameter_figures']['psf'];m=f['psf_map']
    assert len(m['values'])==a.psf_preview_samples and len(m['values'][0])==a.psf_preview_samples
    assert m['x_edges_um'][-1]==pytest.approx(a.psf_preview_extent_sigma*4)
    assert m['y_edges_um'][-1]==pytest.approx(a.psf_preview_extent_sigma*12)
    assert {s['marker'] for s in f['series']}=={'circle','diamond'}
    assert all(s['dash'] for s in f['series'])
    assert info['budget']['psf_edge_loss_j']>=0
    small=SimulationConfig.for_experiment('system',{'spad':{'channels_h':1,'channels_v':1},'rx':{'rx_model':'super_gaussian_psf','psf_sigma_h_um':100,'psf_sigma_v_um':100}})
    data=optical_dataset(small,a)
    assert np.asarray(data.rx.psf_pixel_fraction).sum(axis=(-2,-1)).max()<1


def test_super_gaussian_form_enum_and_order_limit():
    client=TestClient(app);a=Algorithms.load()
    response=client.post('/api/experiments/system/preview',json={'tx':{'tx_model':'super_gaussian'},'rx':{'rx_model':'super_gaussian_psf'}})
    assert response.status_code==200
    result=response.json()
    assert result['form_configuration']['optics']['tx_model']=='super_gaussian'
    assert result['parameter_figures']['psf']['psf_map']['color_label']=='μm⁻²'
    for values in ({'rx':{'psf_sigma_h_um':0}},{'rx':{'psf_order_v':float('nan')}},
                   {'tx':{'tx_model':'super_gaussian','tx_order_h':a.max_super_gaussian_order+1}}):
        with pytest.raises(ValueError):SimulationConfig.for_experiment('system',values)
