from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict
from .entities import FoodStation, Student


@dataclass
class Metrics:
    total_arrivals: int = 0
    total_departures: int = 0
    instant_balks: int = 0
    reneges: int = 0
    sum_wq: float = 0.0
    sum_w: float = 0.0

    # NEW: per-station busy time accumulation
    busy_time: Dict[int, float] = field(default_factory=dict)

    def record_arrival(self) -> None:
        self.total_arrivals += 1

    def record_instant_balk(self) -> None:
        self.instant_balks += 1

    def record_renege(self) -> None:
        self.reneges += 1

    def record_departure(self, s: Student) -> None:
        self.total_departures += 1
        wait_in_queue = (s.service_start_time - s.arrival_time) if s.service_start_time is not None else 0.0
        total_wait = (s.departure_time - s.arrival_time) if s.departure_time is not None else 0.0
        self.sum_wq += wait_in_queue
        self.sum_w += total_wait

    # NEW: called whenever time advances in the DES loop
    def accumulate_busy_time(self, stations: Dict[int, FoodStation], dt: float) -> None:
        if dt <= 0:
            return
        for st_id, st in stations.items():
            self.busy_time[st_id] = self.busy_time.get(st_id, 0.0) + (st.busy_servers * dt)

    # NEW: utilization + throughput in report
    def report(self, sim_duration: float, stations: Dict[int, FoodStation]) -> str:
        avg_wq = self.sum_wq / self.total_departures if self.total_departures else 0.0
        avg_w = self.sum_w / self.total_departures if self.total_departures else 0.0

        throughput = (self.total_departures / sim_duration) if sim_duration > 0 else 0.0

        util_parts = []
        for st_id, st in stations.items():
            bt = self.busy_time.get(st_id, 0.0)
            denom = (st.servers * sim_duration) if sim_duration > 0 else 0.0
            rho = (bt / denom) if denom > 0 else 0.0
            util_parts.append(f"rho[{st_id}]={rho:.3f}")

        return (
                f"arrivals={self.total_arrivals}, departures={self.total_departures}, "
                f"instant_balks={self.instant_balks}, reneges={self.reneges}, "
                f"total_balks={self.instant_balks + self.reneges}, "
                f"avgWq={avg_wq:.2f}, avgW={avg_w:.2f}, "
                f"throughput={throughput:.3f}/min, "
                + ", ".join(util_parts)
        )