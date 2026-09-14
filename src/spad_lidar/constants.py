"""SI definitions and mathematical identities; not scenario settings."""
from math import log, sqrt
C = 299_792_458.0  # m/s, exact SI definition
H = 6.626_070_15e-34  # J s, exact SI definition
FWHM_TO_SIGMA = 2 * sqrt(2 * log(2))
K_PHOTOPIC = 683.0  # lm/W, conventional photopic maximum luminous efficacy
