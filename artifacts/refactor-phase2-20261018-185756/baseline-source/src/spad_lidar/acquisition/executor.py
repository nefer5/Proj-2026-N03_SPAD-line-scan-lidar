"""Common repetition executor; numerical kernels and cancellation stay in adapters."""
from collections.abc import Callable, Iterator
from typing import TypeVar
from .trials import TrialPlan, TrialRole

T = TypeVar('T')


def execute_trials(plan: TrialPlan, role: TrialRole, acquire: Callable[[int], T]) -> Iterator[T]:
    """Run exactly the explicit role count, in order, without touching any RNG.

    Yield each result before the next call so existing summation order, resource
    checks and cancellation/progress boundaries remain under caller control.
    """
    for index in range(plan.count(role)):
        yield acquire(index)
