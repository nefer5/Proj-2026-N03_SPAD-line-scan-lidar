import numpy as np


class DeviceState:
    def __init__(self, pixel_count):
        self.ready_ns = np.full(pixel_count, -np.inf)

    def avalanche(self, t, pixel, dead_time_ns):
        if t < self.ready_ns[pixel]:
            return False
        self.ready_ns[pixel] = t + dead_time_ns
        return True
