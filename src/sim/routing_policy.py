# src/sim/routing_policy.py
from __future__ import annotations
from typing import Dict, List
import random
from .entities import FoodStation

class ShortestQueuePolicy:
    def select_station_id(self, stations: Dict[int, FoodStation], rng: random.Random) -> int:
        # Find min queue length
        min_len = min(st.queue_length() for st in stations.values())
        candidates: List[int] = [sid for sid, st in stations.items() if st.queue_length() == min_len]
        return rng.choice(candidates)