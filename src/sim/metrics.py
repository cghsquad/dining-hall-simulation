from __future__ import annotations

from dataclasses import dataclass, field

from .entities import FoodStation, Student


@dataclass
class Metrics:
    total_arrivals: int = 0
    total_departures: int = 0
    total_service_starts: int = 0
    instant_balks: int = 0
    reneges: int = 0
    sum_wq: float = 0.0
    sum_w: float = 0.0

    # per-station busy time accumulation
    busy_time: dict[int, float] = field(default_factory=dict)

    # ---- recording methods ------------------------------------------------

    def record_arrival(self) -> None:
        self.total_arrivals += 1

    def record_service_start(self) -> None:
        """Track service-start events."""
        self.total_service_starts += 1

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

    # ---- continuous-time accumulation -------------------------------------

    def accumulate_busy_time(self, stations: dict[int, FoodStation], dt: float) -> None:
        """Called on every time-jump in the DES loop: Δt × busy_servers."""
        if dt <= 0:
            return
        for st_id, st in stations.items():
            self.busy_time[st_id] = self.busy_time.get(st_id, 0.0) + (st.busy_servers * dt)

    # ---- standalone metric methods (match UML) ----------------------------

    def compute_throughput(self, current_time: float) -> float:
        """Throughput = departures / elapsed time."""
        return (self.total_departures / current_time) if current_time > 0 else 0.0

    def estimate_utilization(self, stations: dict[int, FoodStation], current_time: float) -> dict[int, float]:
        """Per-station utilization ρ_i = busy_time_i / (c_i × T)."""
        result: dict[int, float] = {}
        for st_id, st in stations.items():
            bt = self.busy_time.get(st_id, 0.0)
            denom = (st.servers * current_time) if current_time > 0 else 0.0
            result[st_id] = (bt / denom) if denom > 0 else 0.0
        return result

    # ---- report -----------------------------------------------------------

    def report(self, sim_duration: float, stations: dict[int, FoodStation]) -> str:
        avg_wq = self.sum_wq / self.total_departures if self.total_departures else 0.0
        avg_w = self.sum_w / self.total_departures if self.total_departures else 0.0

        throughput = self.compute_throughput(sim_duration)
        utilization = self.estimate_utilization(stations, sim_duration)

        util_parts = [f"rho[{sid}]={rho:.3f}" for sid, rho in utilization.items()]

        return (
            f"arrivals={self.total_arrivals}, departures={self.total_departures}, "
            f"instant_balks={self.instant_balks}, reneges={self.reneges}, "
            f"total_balks={self.instant_balks + self.reneges}, "
            f"avgWq={avg_wq:.2f}, avgW={avg_w:.2f}, "
            f"throughput={throughput:.3f}/min, "
            + ", ".join(util_parts)
        )
