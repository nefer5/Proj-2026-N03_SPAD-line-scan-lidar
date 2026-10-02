"""Receiver PSF database synthesis; samples are explicit model-generated data."""
import numpy as np
from scipy.special import ndtr
from ..numerics.spatial_profiles import profile_bin_mass, scale_from_sigma


def psf_axis_mass(edges,sigma,order):
    if order==1:return normal_bin_mass(np.asarray(edges)/sigma)
    return profile_bin_mass(edges,scale_from_sigma(sigma,order),order)


def psf_orders(optics):
    return (optics.psf_order_h,optics.psf_order_v) if optics.rx_model=='super_gaussian_psf' else (1,1)


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
                cx,cy=image_center(optics,theta_h,theta_v)
                mh,mv=psf_orders(optics)
                value=np.outer(psf_axis_mass(y-cy,optics.psf_sigma_v_um,mv),psf_axis_mass(x-cx,optics.psf_sigma_h_um,mh))
            psf[:,iy,ix]=value
    return {'reference_plane':'pupil_to_unbounded_image_before_filter_and_PDE_FF',
            'psf_convention':'fraction_of_unbounded_PSF_in_each_full_pixel_no_edge_renormalization',
            'wavelength_nm':wl.tolist(),'h_angle_mrad':h.tolist(),'v_angle_mrad':v.tolist(),
            'x_edges_um':x.tolist(),'y_edges_um':y.tolist(),
            'collection_efficiency':np.full((len(wl),len(v),len(h)),optics.rx_efficiency).tolist(),
            'psf_pixel_fraction':psf.tolist()}


def image_center(optics,h_mrad,v_mrad):
    """Positive-right/up axes. Legacy orientation must be explicitly selected."""
    sign=-1 if optics.mapping_mode=='inverted' else 1
    return (sign*optics.focal_length_h_mm*1000*np.tan(np.asarray(h_mrad)*1e-3)+optics.rx_offset_x_um,
            sign*optics.focal_length_v_mm*1000*np.tan(np.asarray(v_mrad)*1e-3)+optics.rx_offset_y_um)


def image_angles(optics,x_um,y_um):
    """Inverse of image_center for full-pixel boundaries, before PSF/PDE/FF."""
    sign=-1 if optics.mapping_mode=='inverted' else 1
    return (np.arctan((np.asarray(x_um)-optics.rx_offset_x_um)/(sign*optics.focal_length_h_mm*1000))*1000,
            np.arctan((np.asarray(y_um)-optics.rx_offset_y_um)/(sign*optics.focal_length_v_mm*1000))*1000)


def normal_bin_mass(edges):
    """Integrate Gaussian tails without subtracting two values rounded to one."""
    low,high=np.asarray(edges)[:-1],np.asarray(edges)[1:]
    return np.where(low>0,ndtr(-low)-ndtr(-high),ndtr(high)-ndtr(low))
