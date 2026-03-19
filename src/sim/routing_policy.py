# src/sim/routing_policy.py
from __future__ import annotations

import random
from abc import ABC, abstractmethod

from .entities import FoodStation, Student


class RoutingPolicy(ABC):
    """Abstract base for station-selection policies."""

    @abstractmethod
    def select_station(
        self, student: Student, stations: dict[int, FoodStation], rng: random.Random,
    ) -> FoodStation:
        """Choose a station for the arriving student."""
        ...


class ShortestQueuePolicy(RoutingPolicy):
    """Route to the station with the shortest queue (random tie-break)."""

    def select_station(
        self, student: Student, stations: dict[int, FoodStation], rng: random.Random,
    ) -> FoodStation:
        min_len = min(st.queue_length() for st in stations.values())
        candidates: list[int] = [
            sid for sid, st in stations.items() if st.queue_length() == min_len
        ]
        return stations[rng.choice(candidates)]


class WeightedRandomPolicy(RoutingPolicy):
    """
    Route to stations using weighted-random selection.

    weights maps station_id → relative weight (need not sum to 1).
    """

    def __init__(self, weights: dict[int, float]) -> None:
        self.weights = weights

    def select_station(
        self, student: Student, stations: dict[int, FoodStation], rng: random.Random,
    ) -> FoodStation:
        ids = list(stations.keys())
        w = [self.weights.get(sid, 1.0) for sid in ids]
        chosen = rng.choices(ids, weights=w, k=1)[0]
        return stations[chosen]
