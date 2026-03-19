from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod


class ArrivalModel(ABC):
    """Abstract base for arrival-rate models."""

    @abstractmethod
    def lambda_at(self, t: float) -> float:
        """Return the arrival rate λ(t) at time t (students / minute)."""
        ...

    @abstractmethod
    def next_arrival_time(self, current_time: float, rng: random.Random) -> float:
        """Sample the next arrival time given current_time."""
        ...


class PiecewisePoissonArrivalModel(ArrivalModel):
    """
    Non-homogeneous Poisson process with piecewise-constant rate:

        λ(t) = λ_peak   if peak_start ≤ t < peak_end
               λ_off    otherwise

    Interarrival times within a constant-rate region are Exp(λ):
        T = −ln(U) / λ(t)
    """

    def __init__(
        self,
        lambda_off: float,
        lambda_peak: float,
        peak_start: float,
        peak_end: float,
    ) -> None:
        self.lambda_off = lambda_off
        self.lambda_peak = lambda_peak
        self.peak_start = peak_start
        self.peak_end = peak_end

    def lambda_at(self, t: float) -> float:
        if self.peak_start <= t < self.peak_end:
            return self.lambda_peak
        return self.lambda_off

    def _sample_interarrival(self, lam: float, rng: random.Random) -> float:
        """Sample Exp(λ): T = −ln(U) / λ."""
        if lam <= 0:
            return float("inf")
        u = max(rng.random(), 1e-12)
        return -math.log(u) / lam

    def next_arrival_time(self, current_time: float, rng: random.Random) -> float:
        lam = self.lambda_at(current_time)
        delta = self._sample_interarrival(lam, rng)
        return current_time + delta
