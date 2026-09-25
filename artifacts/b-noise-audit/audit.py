"""Reproducible diagnostic for the user's saved CH04 histogram, not app defaults."""
from pathlib import Path
import sys
import json
import hashlib
import subprocess
from datetime import datetime, timezone
from dataclasses import replace, asdict
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from spad_lidar.configuration import Algorithms, frozen_yaml
from spad_lidar.models import SimulationConfig
from spad_lidar.experiments.system_config import BSystemConfig
from spad_lidar.experiments.spatial import system_program
from spad_lidar.experiments.lab import run_illumination
from spad_lidar.contracts import SensorIllumination
from spad_lidar.curves import Curve
from spad_lidar.constants import C, H
from spad_lidar.spad.device import effective_pde
from spad_lidar.rx.budget import photon_budget
from spad_lidar.spectra import spectral_components

OUT = Path(__file__).parent
B_JOB = '7dbe1e27a144499f80f382d53df86fdc'
A_JOB = 'f96f4cc8c4064d56be797c899e50a633'
CHANNEL = 4  # Channel selected in the user's screenshot.


def read(job, name):
    return json.loads((ROOT / 'artifacts/runs' / job / name).read_text(encoding='utf-8'))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def main():
    b = read(B_JOB, 'result.json')
    old_a = read(A_JOB, 'result.json')
    b_request = read(B_JOB, 'request.json')
    with frozen_yaml(b_request['yaml']):
        cfg = BSystemConfig.model_validate(b['configuration']['experiment'])
        algorithms = Algorithms.model_validate(b['configuration']['algorithms'])
        optics = b['optics']
        spectral = optics['spectral_integration']
        wavelengths = np.asarray(spectral['wavelength_nm'])
        pde = Curve(cfg.spectral_inputs.pde)
        response = effective_pde(pde(wavelengths), cfg.device.fill_factor)
        solar = np.asarray(spectral['solar_sensor_photons_per_second_per_spectral_cell'])
        other = np.asarray(spectral['other_sensor_photons_per_second_per_spectral_cell'])
        groups = np.asarray(optics['pixel_group_ids'])
        selected = groups == CHANNEL
        solar_rate = solar @ response
        other_rate = other @ response
        dark_rate = np.full(groups.shape, cfg.device.dcr_cps_per_spad)
        electronic_rate = np.full(groups.shape, cfg.device.other_noise_cps_per_spad)
        noise_rate = solar_rate + other_rate + dark_rate + electronic_rate
        signal_photons = np.asarray(optics['signal_energy_per_pixel_j']).ravel() / (H*C/(cfg.optics.wavelength_nm*1e-9))
        signal_candidates = signal_photons * effective_pde(pde(cfg.optics.wavelength_nm), cfg.device.fill_factor)
        shots = cfg.timing.laser_shots
        bin_ns = cfg.readout.tdc_bin_ps * 1e-3
        gate_s = cfg.timing.gate_width_ns * 1e-9
        source = b['audit']['source']
        np.testing.assert_allclose(solar_rate + other_rate, source['expected_optical_background_candidates_per_pixel_per_second'])
        np.testing.assert_allclose(signal_candidates, source['expected_signal_candidates_per_pixel_per_pulse'])
        baseline = noise_rate[selected].sum() * shots * bin_ns * 1e-9
        np.testing.assert_allclose(baseline, b['noise_reference']['counts_per_bin'][CHANNEL])
        omega = np.outer(np.diff(optics['tx_v_edges_mrad']), np.diff(optics['tx_h_edges_mrad'])).ravel() * 1e-6
        channel_omega = omega @ np.asarray(optics['angle_to_channel_fraction'])
        assert channel_omega.sum() <= omega.sum() * (1 + np.finfo(float).eps)

        # A shared radiometry calculation with the same measured angular acceptance.
        a_cfg = SimulationConfig.model_validate(old_a['configuration']['simulation'])
        a_spectral = spectral_components(a_cfg, algorithms)
        a_budget = photon_budget(a_cfg, spectral=a_spectral)
        a_equal_values = a_cfg.model_dump()
        a_equal_values['channel_ifov_v_mrad'] = channel_omega[CHANNEL] * 1e6 / a_cfg.channel_ifov_h_mrad
        a_equal_values['H_binning'] = cfg.device.H_binning
        a_equal_values['V_binning'] = cfg.device.V_binning
        a_equal = SimulationConfig.model_validate(a_equal_values)
        a_equal_budget = photon_budget(a_equal, spectral=a_spectral)
        np.testing.assert_allclose(a_budget.background_detected_per_gate, old_a['budget']['background_detected_per_gate'])
        b_optical_per_gate = (solar_rate[selected] + other_rate[selected]).sum() * gate_s
        np.testing.assert_allclose(a_equal_budget.background_detected_per_gate, b_optical_per_gate, rtol=1e-10)

        # Reconstruct the exact saved sensor-plane contract; no optical resampling.
        wl_all = np.r_[cfg.optics.wavelength_nm, wavelengths]
        signals = np.zeros((len(groups), len(wl_all)))
        signals[:, 0] = signal_photons
        light = SensorIllumination(wl_all, signals, np.column_stack((np.zeros(len(groups)), solar + other)),
            cfg.optics.pulse_shape, cfg.optics.pulse_fwhm_ps,
            2 * cfg.optics.range_m / C * 1e9 + cfg.optics.calibration_delay_ns,
            {'kind': 'saved_optical_projection_reconstruction', 'source_job': B_JOB})
        program = system_program(cfg, algorithms)
        diagnostics = {}
        for name, source_light in (
            ('mixed_replay', light),
            ('laser_off', replace(light, signal_photons_per_pulse=np.zeros_like(signals))),
            ('optical_background_off', replace(light, background_photons_per_second=np.zeros_like(light.background_photons_per_second))),
        ):
            print('Running', name, flush=True)
            result = run_illumination(cfg, algorithms, source_light, groups, lambda *_: None, lambda: False, program=program)
            save(name + '.json', result)
            counts = np.asarray(result['histogram']['counts'])[CHANNEL]
            diagnostics[name] = {'records': int(counts.sum()), 'average_counts_per_bin': float(counts.mean()),
                'audit': {key: value for key, value in result['audit'].items() if key not in ('source', 'trace')},
                'seed': cfg.rng_seed, 'note': 'DCR and electronic noise remain active; changes only affect the sensor illumination contract.'}
            if name == 'mixed_replay':
                assert result['histogram'] == b['histogram']
                assert result['records'] == b['records']
                assert result['histogram']['counts'] == b['statistics']['trial_histograms'][0]
        steady_rate = noise_rate / (1 + noise_rate * cfg.device.spad_dead_time_ns * 1e-9)
        parts = {}
        for name, rate in [('solar', solar_rate), ('other_light', other_rate), ('dark', dark_rate), ('other_device', electronic_rate)]:
            parts[name] = {'candidate_rate_per_second': float(rate[selected].sum()),
                'candidates_per_gate': float(rate[selected].sum() * gate_s),
                'candidates_per_slot_bin': float(rate[selected].sum() * shots * bin_ns * 1e-9)}
        report = {
            'utc': datetime.now(timezone.utc).isoformat(),
            'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'B_job': B_JOB, 'A_comparison_job': A_JOB, 'channel': CHANNEL,
            'input_sha256': {f'{job}/{name}': hashlib.sha256((ROOT/'artifacts/runs'/job/name).read_bytes()).hexdigest()
                for job in (B_JOB, A_JOB) for name in ('result.json', 'request.json')},
            'B_configuration': b['configuration'], 'A_configuration': old_a['configuration'],
            'B_provenance': b['provenance'], 'A_provenance': old_a['provenance'],
            'B_channel': {'effective_solid_angle_sr': float(channel_omega[CHANNEL]),
                'all_channel_solid_angles_sr': channel_omega.tolist(),
                'geometric_channel_ifov_h_mrad': cfg.device.H_binning*cfg.spad.pixel_pitch_um/cfg.rx.focal_length_h_mm,
                'geometric_channel_ifov_v_mrad': cfg.device.V_binning*cfg.spad.pixel_pitch_um/cfg.rx.focal_length_v_mm,
                'nominal_bin_ns': bin_ns, 'shots': shots, 'trials': cfg.acquisition.monte_carlo_trials,
                'signal_candidates_per_pulse': float(signal_candidates[selected].sum()),
                'signal_candidates_per_slot': float(signal_candidates[selected].sum()*shots),
                'noise_parts': parts, 'noise_candidates_per_slot_bin': float(baseline),
                'noise_stationary_nonparalyzable_counts_per_slot_bin': float(steady_rate[selected].sum()*shots*bin_ns*1e-9)},
            'A_budget_recomputed': asdict(a_budget),
            'A_matched_angular_acceptance_and_binning': {'config': a_equal.model_dump(), 'budget': asdict(a_equal_budget),
                'note': 'Radiometry-only comparison: IFOV product equals the integrated B CH04 angular acceptance, not a proposed physical rectangular IFOV.'},
            'background_solid_angle_ratio_B_to_A': float(channel_omega[CHANNEL]/a_budget.channel_solid_angle_sr),
            'diagnostic_runs': diagnostics,
            'checks': {'exact_replay_of_saved_histogram_and_all_records': True,
                'main_histogram_is_first_N_shot_trial_not_M_trials_summed': True,
                'noise_baseline_recomputed_from_separate_sources': True,
                'A_B_background_equal_with_same_angular_acceptance': True,
                'angular_acceptance_does_not_exceed_scene_domain': True},
            'limitations': [
                'B background integrates the configured finite Tx angular grid, not an independently specified full diffuse Rx scene.',
                'A scalar IFOV does not encode B spatial pixel loading; matching total optical counts alone does not guarantee identical deadtime losses.',
                'The stationary deadtime estimate assumes independent Poisson noise and a nonparalyzable detector; acquisition boundaries and signal are excluded.',
                'Laser-off and optical-background-off runs are counterfactual diagnostics, not additive source labels for mixed output records.',
                'No calibrated detection SNR or false-alarm statistic is inferred from raw peak height divided by baseline.',
            ],
        }
        save('audit.json', report)
        print(json.dumps({key: report[key] for key in ('B_channel', 'background_solid_angle_ratio_B_to_A', 'diagnostic_runs', 'checks')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
