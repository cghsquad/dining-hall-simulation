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

    # min / max observations
    min_wq: float = float("inf")
    max_wq: float = 0.0
    min_w: float = float("inf")
    max_w: float = 0.0
    max_queue_depth: int = 0

    # per-station busy time accumulation
    busy_time: dict[int, float] = field(default_factory=dict)

    # per-station Wq tracking (for routing policy comparison)
    station_sum_wq: dict[int, float] = field(default_factory=dict)
    station_departures: dict[int, int] = field(default_factory=dict)

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
        # min / max tracking
        self.min_wq = min(self.min_wq, wait_in_queue)
        self.max_wq = max(self.max_wq, wait_in_queue)
        self.min_w = min(self.min_w, total_wait)
        self.max_w = max(self.max_w, total_wait)
        # per-station Wq tracking
        sid = s.station_id
        self.station_sum_wq[sid] = self.station_sum_wq.get(sid, 0.0) + wait_in_queue
        self.station_departures[sid] = self.station_departures.get(sid, 0) + 1

    def record_queue_depth(self, stations: dict[int, FoodStation]) -> None:
        """Track the maximum queue depth across all stations."""
        for st in stations.values():
            self.max_queue_depth = max(self.max_queue_depth, st.queue_length())

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

    def per_station_avg_wq(self) -> dict[int, float]:
        """Per-station average Wq for routing policy comparison."""
        result: dict[int, float] = {}
        for sid, total in self.station_sum_wq.items():
            deps = self.station_departures.get(sid, 0)
            result[sid] = (total / deps) if deps > 0 else 0.0
        return result

    # ---- report -----------------------------------------------------------

    def report(self, sim_duration: float, stations: dict[int, FoodStation]) -> str:
        avg_wq = self.sum_wq / self.total_departures if self.total_departures else 0.0
        avg_w = self.sum_w / self.total_departures if self.total_departures else 0.0

        # clamp inf → 0 when no departures recorded
        min_wq = self.min_wq if self.min_wq != float("inf") else 0.0
        min_w = self.min_w if self.min_w != float("inf") else 0.0

        throughput = self.compute_throughput(sim_duration)
        utilization = self.estimate_utilization(stations, sim_duration)

        util_parts = [f"rho[{sid}]={rho:.3f}" for sid, rho in utilization.items()]
        per_wq = self.per_station_avg_wq()
        wq_parts = [f"Wq[{sid}]={wq:.2f}" for sid, wq in per_wq.items()]

        return (
            f"arrivals={self.total_arrivals}, departures={self.total_departures}, "
            f"instant_balks={self.instant_balks}, reneges={self.reneges}, "
            f"total_balks={self.instant_balks + self.reneges}, "
            f"avgWq={avg_wq:.2f}, minWq={min_wq:.2f}, maxWq={self.max_wq:.2f}, "
            f"avgW={avg_w:.2f}, minW={min_w:.2f}, maxW={self.max_w:.2f}, "
            f"maxQueueDepth={self.max_queue_depth}, "
            f"throughput={throughput:.3f}/min, "
            + ", ".join(util_parts) + ", "
            + ", ".join(wq_parts)
        )
