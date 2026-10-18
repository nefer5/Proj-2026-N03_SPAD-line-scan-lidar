"""B: full Tx angular footprint → Rx PSF → physical pixels → shared SPAD engine."""
from pydantic import Field, model_validator
from ..spad.config import StrictConfig, DeviceConfig, ReadoutConfig
from ..curves import SpectralInputs
from .configuration import TimingConfig
from .lab import run_illumination, stamp_result
from ..domains.optical import OpticalConfig  # Compatibility export.
from ..optics import optical_dataset, project_illumination


class SystemConfig(StrictConfig):
    device: DeviceConfig
    readout: ReadoutConfig
    timing: TimingConfig
    optics: OpticalConfig
    spectral_inputs: SpectralInputs
    rng_seed: int = Field(ge=0,strict=True)

    @model_validator(mode='after')
    def valid(self):
        if self.readout.readout_mode=='analytic_reference':
            raise ValueError('Spatial acquisition requires an event readout mode')
        if self.readout.readout_mode.startswith('coincidence') and self.readout.coincidence_threshold>self.device.spads_per_channel:
            raise ValueError('Coincidence threshold exceeds group size')
        if self.optics.pulse_fwhm_ps*1e-3>=self.timing.period_ns:
            raise ValueError('Pulse width must be shorter than period')
        return self


def system_defaults(base):
    return {'optics':{k:base[k] for k in OpticalConfig.model_fields if k in base},
            'spectral_inputs':base['spectral_inputs']}


def system_program(cfg,a):
    from ..timing import periodic_program
    t=cfg.timing
    first=0 if a.b_initial_condition=='fully_recovered' else -a.readout_warmup_cycles
    return periodic_program(t.period_ns,t.gate_start_ns,t.gate_width_ns,first,t.laser_shots,t.laser_shots)


def run_system(cfg,a,progress,cancelled):
    light,groups,optics=project_illumination(cfg,a,progress,cancelled)
    result=run_illumination(cfg,a,light,groups,progress,cancelled,program=system_program(cfg,a))
    return finish_system(cfg,a,result,light,groups,optics)


def finish_system(cfg,a,result,light,groups,optics):
    result['audit']['initialization']={'mode':a.b_initial_condition,
        'warmup_cycles':0 if a.b_initial_condition=='fully_recovered' else a.readout_warmup_cycles,
        'scope':'This independent static acquisition only; not a C inter-column reset implementation.'}
    result['illumination']={'signal_photons_per_pixel_per_pulse':light.signal_photons_per_pulse.sum(axis=1).tolist(),
                            'background_photons_per_pixel_per_second':light.background_photons_per_second.sum(axis=1).tolist(),
                            'shape':optics['array_shape'],'provenance':light.provenance}
    result['optics']=optics
    result['provenance_extra']={'optical_dataset_sha256':optics['dataset_sha256']}
    from ..reporting.spatial_flow import build_spatial_flow
    result['photon_flow']=build_spatial_flow(optics['budget'],result['audit'])
    from ..processing.spatial_ranges import estimate_channels
    result['channel_ranges']=estimate_channels(cfg,a,result['histogram'])
    stamped=stamp_result('B_full_spot_static',cfg,a,result)
    if a.b_initial_condition=='fully_recovered':
        stamped['provenance']['limitations']=[s for s in stamped['provenance']['limitations'] if s!='Finite warmup, step recovery.']
        stamped['provenance']['limitations'].append('Independent B acquisition starts fully recovered, without prehistory; step recovery within the acquisition.')
    return stamped
