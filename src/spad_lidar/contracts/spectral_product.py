"""Exact nonnegative rank-one [pixel, spectral cell] measures, before PDE/FF."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class SpectralProduct:
    pixel: np.ndarray
    spectral: np.ndarray

    def __post_init__(self):
        for key in ('pixel','spectral'):
            value=np.asarray(getattr(self,key),dtype=float)
            if value.ndim!=1 or not len(value) or not np.all(np.isfinite(value)) or np.any(value<0):
                raise ValueError('Spectral factors must be finite nonnegative vectors')
            object.__setattr__(self,key,value)

    @property
    def shape(self):return (len(self.pixel),len(self.spectral))

    @property
    def ndim(self):return 2

    def __matmul__(self,response):return self.pixel*(self.spectral@response)

    def sum(self,axis=None):
        if axis is None:return self.pixel.sum()*self.spectral.sum()
        if axis==1:return self.pixel*self.spectral.sum()
        if axis==0:return self.pixel.sum()*self.spectral
        raise ValueError('SpectralProduct has only pixel and spectral axes')

    def dense(self):return np.outer(self.pixel,self.spectral)

    def export(self):return {'representation':'outer_product','shape':list(self.shape),
        'pixel_factor':self.pixel.tolist(),'spectral_factor':self.spectral.tolist(),
        'reconstruction':'matrix[pixel, wavelength] = pixel_factor[pixel] * spectral_factor[wavelength]'}


def zero_spectral(values):
    return SpectralProduct(np.zeros_like(values.pixel),values.spectral) if isinstance(values,SpectralProduct) else np.zeros_like(values)


def export_spectral(values):return values.export() if isinstance(values,SpectralProduct) else values.tolist()
