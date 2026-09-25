"""Separable normalized Gaussian / super-Gaussian spatial intensity profiles.

Order m uses beta=2m in the generalized normal distribution. Width conversions
are exact: Tx specifies FWHM, Rx specifies the actual marginal standard deviation.
"""
import numpy as np
from scipy.special import ndtr, gammainc, gammaincc, gammaln


def scale_from_fwhm(width, order):
    return width / (2*np.log(2)**(1/(2*order)))


def scale_from_sigma(sigma, order):
    beta=2*order
    return sigma*np.exp((gammaln(1/beta)-gammaln(3/beta))/2)


def profile_density(x, scale, order):
    beta=2*order
    with np.errstate(over='ignore'):
        power=(np.abs(np.asarray(x))/scale)**beta
    return np.exp(np.log(beta)-np.log(2*scale)-gammaln(1/beta)-power)


def profile_bin_mass(edges, scale, order):
    x=np.asarray(edges)/scale;low,high=x[:-1],x[1:]
    if order==1:
        low=low*np.sqrt(2);high=high*np.sqrt(2)
        return np.where(low>0,ndtr(-low)-ndtr(-high),ndtr(high)-ndtr(low))
    beta=2*order
    with np.errstate(over='ignore'):
        pl=np.abs(low)**beta;ph=np.abs(high)**beta
    return np.where(low>=0,(gammaincc(1/beta,pl)-gammaincc(1/beta,ph))/2,
        np.where(high<=0,(gammaincc(1/beta,ph)-gammaincc(1/beta,pl))/2,
                 (gammainc(1/beta,pl)+gammainc(1/beta,ph))/2))


def validate_profile_orders(optics, algorithms):
    for model,selected,fields in (
        (optics.tx_model,'super_gaussian',('tx_order_h','tx_order_v')),
        (optics.rx_model,'super_gaussian_psf',('psf_order_h','psf_order_v'))):
        if model==selected and any(getattr(optics,key)>algorithms.max_super_gaussian_order for key in fields):
            raise ValueError('Super-Gaussian order exceeds max_super_gaussian_order')
