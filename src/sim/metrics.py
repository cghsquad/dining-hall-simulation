from __future__ import annotations
from dataclasses import dataclass
from .entities import Student


@dataclass
class Metrics:
    total_arrivals: int = 0
    total_departures: int = 0
    sum_wq: float = 0.0
    sum_w: float = 0.0

    def record_arrival(self) -> None:
        self.total_arrivals += 1

    def record_departure(self, s: Student) -> None:
        self.total_departures += 1
        wait_in_queue = (s.service_start_time - s.arrival_time) if s.service_start_time is not None else 0.0
        total_wait = (s.departure_time - s.arrival_time) if s.departure_time is not None else 0.0
        self.sum_wq += wait_in_queue
        self.sum_w += total_wait

    def report(self) -> str:
        avg_wq = self.sum_wq / self.total_departures if self.total_departures else 0.0
        avg_w = self.sum_w / self.total_departures if self.total_departures else 0.0
        return (
            f"arrivals={self.total_arrivals}, departures={self.total_departures}, "
            f"avgWq={avg_wq:.2f}, avgW={avg_w:.2f}"
        )
