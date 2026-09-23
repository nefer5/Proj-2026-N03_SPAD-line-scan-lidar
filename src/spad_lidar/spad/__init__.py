"""Public detector core; no dependency on scene, Tx, Rx, web or YAML IO."""
from .acquisition import AcquisitionSession
from .config import DeviceConfig, ReadoutConfig
