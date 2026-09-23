"""Receiver PSF database synthesis; samples are explicit model-generated data."""
import numpy as np
from scipy.special import ndtr


def synthetic_receiver(optics, device, wavelength_nm, algorithms):
    nx=optics.channels_h*device.H_binning; ny=optics.channels_v*device.V_binning
    size=len(np.unique(wavelength_nm))*algorithms.rx_angle_samples_h*algorithms.rx_angle_samples_v*nx*ny
    if size>algorithms.max_optical_cells:
        raise ValueError('Synthetic PSF database exceeds max_optical_cells before allocation')
    x=(np.arange(nx+1)-nx/2)*optics.pixel_pitch_um
    y=(np.arange(ny+1)-ny/2)*optics.pixel_pitch_um
    h=np.linspace(optics.rx_angle_h_min_mrad,optics.rx_angle_h_max_mrad,algorithms.rx_angle_samples_h)
    v=np.linspace(optics.rx_angle_v_min_mrad,optics.rx_angle_v_max_mrad,algorithms.rx_angle_samples_v)
    wl=np.unique(wavelength_nm)
    psf=np.empty((len(wl),len(v),len(h),ny,nx))
    for iy,theta_v in enumerate(v):
        for ix,theta_h in enumerate(h):
            if optics.rx_model=='uniform_pixel':
                value=np.full((ny,nx),1/(ny*nx))
            else:
                cx=optics.focal_length_mm*1000*np.tan(theta_h*1e-3)+optics.rx_offset_x_um
                cy=optics.focal_length_mm*1000*np.tan(theta_v*1e-3)+optics.rx_offset_y_um
                value=np.outer(np.diff(ndtr((y-cy)/optics.psf_sigma_um)),np.diff(ndtr((x-cx)/optics.psf_sigma_um)))
            psf[:,iy,ix]=value
    return {'reference_plane':'pupil_to_unbounded_image_before_filter_and_PDE_FF',
            'psf_convention':'fraction_of_unbounded_PSF_in_each_full_pixel_no_edge_renormalization',
            'wavelength_nm':wl.tolist(),'h_angle_mrad':h.tolist(),'v_angle_mrad':v.tolist(),
            'x_edges_um':x.tolist(),'y_edges_um':y.tolist(),
            'collection_efficiency':np.full((len(wl),len(v),len(h)),optics.rx_efficiency).tolist(),
            'psf_pixel_fraction':psf.tolist()}
