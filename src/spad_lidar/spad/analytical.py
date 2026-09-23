"""Extracted A implementation; public compatibility exports remain at the old path."""
import numpy as np


def _first_photon_probabilities(mu):
    before = np.r_[0.0, np.cumsum(mu[:-1])]
    return np.exp(-before) * (-np.expm1(-mu))


def _sample_histogram(rng, expected, opportunities):
    p = np.maximum(expected / opportunities, 0)
    # Numerical guard at floating point saturation, not a configuration fallback.
    p = np.r_[p, max(0.0, 1-float(p.sum()))]
    p /= p.sum()
    return rng.multinomial(opportunities, p)[:-1].astype(float)

