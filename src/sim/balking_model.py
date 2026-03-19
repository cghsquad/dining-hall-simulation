from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod


class BalkingModel(ABC):
    """Abstract base for balking/reneging decision models."""

    @abstractmethod
    def should_leave(self, estimated_wait: float, tau: float, rng: random.Random) -> bool:
        """Return True if the student decides to leave."""
        ...

    @abstractmethod
    def leave_probability(self, estimated_wait: float, tau: float) -> float:
        """Return the probability of leaving (for reporting / logging)."""
        ...


class ThresholdBalkingModel(BalkingModel):
    """
    Fixed-probability threshold model:
      if Wq_est > tau  →  leave with probability p_leave
      else             →  stay
    """

    def __init__(self, p_leave: float) -> None:
        self.p_leave = p_leave

    def leave_probability(self, estimated_wait: float, tau: float) -> float:
        if estimated_wait > tau:
            return self.p_leave
        return 0.0

    def should_leave(self, estimated_wait: float, tau: float, rng: random.Random) -> bool:
        return estimated_wait > tau and rng.random() < self.p_leave


class LogisticBalkingModel(BalkingModel):
    """
    Logistic (smooth) balking model:
      P(leave) = 1 / (1 + exp(-k * (Wq - tau)))

    - tau is the midpoint (50 % leave probability)
    - k  controls steepness  (k → ∞  approaches threshold model)
    """

    def __init__(self, k: float) -> None:
        self.k = k

    def leave_probability(self, estimated_wait: float, tau: float) -> float:
        return 1.0 / (1.0 + math.exp(-self.k * (estimated_wait - tau)))

    def should_leave(self, estimated_wait: float, tau: float, rng: random.Random) -> bool:
        p = self.leave_probability(estimated_wait, tau)
        return rng.random() < p
