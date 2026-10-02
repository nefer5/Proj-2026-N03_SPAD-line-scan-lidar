"""Ideal emitted pulse convolved with independent Gaussian time jitter.

No dead-time, pile-up, coincidence or digital capacity model is duplicated here.
"""
import numpy as np
from scipy.special import ndtr
from scipy.optimize import brentq
from ..constants import FWHM_TO_SIGMA
from .temporal import temporal_cdf,temporal_pdf


class IdealIRF:
    def __init__(self,shape,width_ps,jitter_fwhm_ps):
        self.shape=shape;self.width=width_ps*1e-3
        self.jitter=jitter_fwhm_ps*1e-3/FWHM_TO_SIGMA
        self.sigma=np.hypot(self.width/FWHM_TO_SIGMA,self.jitter) if shape=='gaussian' else self.jitter

    def pdf(self,x):
        x=np.asarray(x,dtype=float)
        if self.shape=='gaussian':return temporal_pdf(x,'gaussian',self.sigma*FWHM_TO_SIGMA*1000)
        if self.jitter==0:return temporal_pdf(x,'rectangular',self.width*1000)
        return (ndtr((x+self.width/2)/self.jitter)-ndtr((x-self.width/2)/self.jitter))/self.width

    def cdf(self,x):
        x=np.asarray(x,dtype=float)
        if self.shape=='gaussian':return temporal_cdf(x,'gaussian',self.sigma*FWHM_TO_SIGMA*1000)
        if self.jitter==0:return temporal_cdf(x,'rectangular',self.width*1000)
        def primitive(v):return v*ndtr(v/self.jitter)+self.jitter*np.exp(-.5*(v/self.jitter)**2)/np.sqrt(2*np.pi)
        return np.clip((primitive(x+self.width/2)-primitive(x-self.width/2))/self.width,0,1)

    def fwhm_ns(self):
        if self.shape=='gaussian':return float(self.sigma*FWHM_TO_SIGMA)
        if self.jitter==0:return self.width
        return 2*brentq(lambda x:float(self.pdf(x)-self.pdf(0)/2),0,self.width/2+10*self.jitter)

    def support_ns(self,sigma_extent):
        return self.sigma*sigma_extent if self.shape=='gaussian' else self.width/2+self.jitter*sigma_extent
