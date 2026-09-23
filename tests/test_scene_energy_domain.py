import numpy as np
import pytest
from spad_lidar.scene import lambertian_return


def test_lambertian_rejects_energy_creating_near_field_without_clipping():
    with pytest.raises(ValueError,match='energy-conserving'):
        lambertian_return(1,1,1,1,0.01,1)
    with pytest.raises(ValueError,match='positive range'):
        lambertian_return(1,1,1,1,-1,1)


def test_positive_far_field_keeps_reference_planes_monotone_for_varying_ranges():
    inc,ref,pupil,g=lambertian_return(np.array([1.,2.]),.9,.8,.001,np.array([10.,20.]),1)
    assert np.all(pupil<=ref) and np.all(ref<=inc)
    assert pupil[0]/pupil[1]==pytest.approx(2)
