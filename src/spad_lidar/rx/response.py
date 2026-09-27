"""Explicit Rx acceptance domain, distinct from response-table data coverage."""
import numpy as np
from ..adapters.optical_data import RxTable


class ReceiverResponse:
    def __init__(self, data, optics, algorithms):
        self.table=RxTable(data)
        self.legacy=algorithms.background_angular_domain=='legacy_tx'
        self.bounds=(optics.rx_angle_h_min_mrad,optics.rx_angle_h_max_mrad,
                     optics.rx_angle_v_min_mrad,optics.rx_angle_v_max_mrad)
        self.shape=(len(data.y_edges_um)-1,len(data.x_edges_um)-1)
        if not self.legacy:
            if max(abs(v) for v in self.bounds)>algorithms.max_spatial_angle_mrad:
                raise ValueError('Rx angular domain exceeds configured optical model range')
            h0,h1,v0,v1=self.bounds
            if h0<data.h_angle_mrad[0] or h1>data.h_angle_mrad[-1] or v0<data.v_angle_mrad[0] or v1>data.v_angle_mrad[-1]:
                raise ValueError('Rx database does not cover the full configured acceptance domain; extrapolation is disabled')

    def evaluate(self,wavelength_nm,h_mrad,v_mrad):
        if self.legacy:return self.table.evaluate(wavelength_nm,h_mrad,v_mrad)
        h,v=np.broadcast_arrays(np.asarray(h_mrad),np.asarray(v_mrad))
        h,v=h.ravel(),v.ravel()
        h0,h1,v0,v1=self.bounds
        keep=(h>=h0)&(h<=h1)&(v>=v0)&(v<=v1)
        eff=np.zeros(len(h));psf=np.zeros((len(h),*self.shape))
        if keep.any():eff[keep],psf[keep]=self.table.evaluate(wavelength_nm,h[keep],v[keep])
        return eff,psf
