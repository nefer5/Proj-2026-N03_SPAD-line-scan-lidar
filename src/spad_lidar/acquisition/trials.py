"""Explicit counts for existing experiment roles; no sampling/default policy."""
from dataclasses import dataclass
from typing import Literal

TrialRole = Literal['observation', 'repeat', 'signal_mean', 'noise']
_ROLES = frozenset(('observation', 'repeat', 'signal_mean', 'noise'))


@dataclass(frozen=True)
class TrialPlan:
    """Resolved role counts. Callers retain their own seed and reset protocols."""
    batches: tuple[tuple[TrialRole, int], ...]

    def __post_init__(self):
        if not isinstance(self.batches, tuple):
            raise ValueError('Trial batches must be an immutable tuple')
        seen = set()
        for batch in self.batches:
            if not isinstance(batch, tuple) or len(batch) != 2:
                raise ValueError('Trial batches must contain immutable role/count pairs')
            role, count = batch
            if role not in _ROLES or role in seen:
                raise ValueError(f'Unknown or duplicate trial role: {role}')
            if type(count) is not int or count < 0:
                raise ValueError(f'Invalid trial count for {role}')
            seen.add(role)

    def count(self, role: TrialRole) -> int:
        for name, count in self.batches:
            if name == role:
                return count
        raise ValueError(f'Trial role was not explicitly configured: {role}')

    @property
    def total(self) -> int:
        return sum(count for _, count in self.batches)
