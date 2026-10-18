"""Protect shared ownership, compatibility and deterministic iteration boundaries."""
import ast
from pathlib import Path
import pytest
from spad_lidar.acquisition.trials import TrialPlan
from spad_lidar.acquisition.executor import execute_trials

ROOT=Path(__file__).resolve().parents[1]/'src/spad_lidar'


@pytest.mark.parametrize('directory',['domains','optics'])
def test_shared_domains_and_optics_do_not_depend_on_experiment_or_display(directory):
    forbidden={'experiments','reporting','runtime','webapi','api','models'}
    for path in (ROOT/directory).rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf8'))):
            if isinstance(node,ast.ImportFrom) and node.module:
                assert not (set(node.module.split('.'))&forbidden),(path,node.module)
            elif isinstance(node,ast.Import):
                assert all(not (set(alias.name.split('.'))&forbidden) for alias in node.names)


def test_old_import_paths_export_the_same_shared_objects():
    from spad_lidar.domains.optical import OpticalConfig
    from spad_lidar.domains.acquisition import TimingConfig
    from spad_lidar.domains.system import TxConfig,AcquisitionConfig
    from spad_lidar.optics import project_illumination,optical_dataset
    from spad_lidar.acquisition.adapters.periodic import acquire_candidates
    from spad_lidar.experiments import spatial,configuration,system_config,lab
    assert spatial.OpticalConfig is OpticalConfig
    assert configuration.TimingConfig is TimingConfig
    assert system_config.TxConfig is TxConfig
    assert system_config.AcquisitionConfig is AcquisitionConfig
    assert spatial.project_illumination is project_illumination
    assert spatial.optical_dataset is optical_dataset
    assert lab.acquire_candidates is acquire_candidates


@pytest.mark.parametrize('batches',[
    (('repeat',-1),),(('repeat',True),),(('repeat',1.0),),
    (('repeat',1),('repeat',2)),(('unknown',1),),
    (['repeat',1],),[('repeat',1)],
])
def test_trial_plan_rejects_ambiguous_or_mutable_counts(batches):
    with pytest.raises(ValueError):TrialPlan(batches)


def test_zero_trials_and_unconfigured_roles_do_not_silently_acquire():
    plan=TrialPlan((('repeat',0),))
    assert list(execute_trials(plan,'repeat',lambda _:pytest.fail('must not acquire')))==[]
    with pytest.raises(ValueError,match='explicitly configured'):
        list(execute_trials(plan,'noise',lambda _:None))


def test_executor_does_not_prefetch_rng_or_advance_after_failure():
    calls=[]
    def acquire(index):
        calls.append(index)
        if index==1:raise InterruptedError('adapter cancellation')
        return {'observation':index}
    runs=execute_trials(TrialPlan((('repeat',3),)),'repeat',acquire)
    assert calls==[]
    assert next(runs)=={'observation':0} and calls==[0]
    with pytest.raises(InterruptedError,match='adapter cancellation'):next(runs)
    assert calls==[0,1]


def test_numerical_background_helpers_keep_compatibility_exports():
    from spad_lidar.processing import background
    from spad_lidar.reporting import background_bins
    assert background_bins.background_bin_values is background.background_bin_values
    assert background_bins.spatial_background_bin_values is background.spatial_background_bin_values
