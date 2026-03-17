from __future__ import annotations

import heapq
import random
import math
from typing import Dict, List

from .event import Event, EventType
from .entities import Student, FoodStation
from .metrics import Metrics
from .config import SimConfig


class SimulationController:
    def __init__(self, cfg: SimConfig) -> None:
        cfg.validate()
        self.cfg = cfg

        self.current_time: float = 0.0
        self.end_time: float = cfg.end_time
        self.fel: List[Event] = []     # heapq priority queue
        self.rng = random.Random(cfg.seed)

        self.metrics = Metrics()
        self.station = FoodStation(station_id=0, servers=cfg.servers)

        self._next_student_id: int = 1
        self.students: Dict[int, Student] = {}

        # arrival params from cfg
        self.lambda_off: float = cfg.lambda_off
        self.lambda_peak: float = cfg.lambda_peak
        self.peak_start: float = cfg.peak_start
        self.peak_end: float = cfg.peak_end

        # service params from cfg
        self.service_time: float = cfg.service_time

    def schedule(self, e: Event) -> None:
        heapq.heappush(self.fel, e)

    def run_simulation(self, end_time: float | None = None) -> None:
        self.end_time = self.cfg.end_time if end_time is None else end_time

        self.schedule(Event(time=0.0, type=EventType.ARRIVAL))
        self.schedule(Event(time=self.end_time, type=EventType.END_SIM))

        print(f"=== START SIM end_time={self.end_time} seed={self.cfg.seed} ===")

        while self.fel:
            e = heapq.heappop(self.fel)
            self.current_time = e.time
            print(f"[POP] t={self.current_time:.2f} type={e.type.name} student={e.student_id}")

            if e.type == EventType.END_SIM:
                print("=== END_SIM event reached ===")
                break

            if e.type == EventType.ARRIVAL:
                self.handle_arrival()
            elif e.type == EventType.SERVICE_END:
                self.handle_service_end(e.student_id)

        print("=== FINAL METRICS ===")
        print(self.metrics.report())

    def lambda_at(self, t: float) -> float:
        """Piecewise-constant arrival rate λ(t) in students/minute."""
        if self.peak_start <= t < self.peak_end:
            return self.lambda_peak
        return self.lambda_off

    def sample_interarrival(self, lam: float) -> float:
        """
        If arrivals are Poisson with rate λ, interarrival times are Exp(λ).
        Sample Exp(λ):  T = -ln(U)/λ
        """
        if lam <= 0:
            # Safety: avoid division by zero; treat as "no arrivals"
            return float("inf")
        u = self.rng.random()
        # u in (0,1); protect against log(0)
        u = max(u, 1e-12)
        return -math.log(u) / lam

    def handle_arrival(self) -> None:
        # Create student
        sid = self._next_student_id
        self._next_student_id += 1

        s = Student(student_id=sid, arrival_time=self.current_time)
        self.students[sid] = s
        self.metrics.record_arrival()

        # Decide: start service or queue
        if self.station.has_free_server():
            self.station.busy_servers += 1
            s.service_start_time = self.current_time
            end_t = self.current_time + self.service_time
            self.schedule(Event(time=end_t, type=EventType.SERVICE_END, student_id=sid))
            print(
                f"  ARRIVAL Student {sid}: start service immediately; "
                f"busy={self.station.busy_servers}/{self.station.servers}; end@{end_t:.2f}"
            )
        else:
            self.station.queue.append(sid)
            print(
                f"  ARRIVAL Student {sid}: queued; queue_len={self.station.queue_length()}; "
                f"busy={self.station.busy_servers}/{self.station.servers}"
            )

        # Schedule next arrival using piecewise λ(t)
        lam = self.lambda_at(self.current_time)
        delta = self.sample_interarrival(lam)
        next_arrival_time = self.current_time + delta

        if next_arrival_time < self.end_time:
            self.schedule(Event(time=next_arrival_time, type=EventType.ARRIVAL))
            print(
                f"  scheduled next ARRIVAL @ t={next_arrival_time:.2f} "
                f"(lambda={lam:.2f}/min, interarrival={delta:.2f})"
            )
        else:
            print(f"  next ARRIVAL would be after endTime (lambda={lam:.2f}/min)")

    def handle_service_end(self, sid: int | None) -> None:
        if sid is None:
            return

        s = self.students[sid]
        s.departure_time = self.current_time
        self.metrics.record_departure(s)

        # Free a server
        self.station.busy_servers = max(0, self.station.busy_servers - 1)

        wq = (s.service_start_time - s.arrival_time) if s.service_start_time is not None else 0.0
        w = s.departure_time - s.arrival_time

        print(
            f"  SERVICE_END Student {sid}: Wq={wq:.2f}, W={w:.2f}; "
            f"busy={self.station.busy_servers}/{self.station.servers}"
        )

        # If someone is waiting, start next service immediately (REAL queue)
        if self.station.queue_length() > 0:
            next_sid = self.station.queue.popleft()
            ns = self.students[next_sid]

            # start service now
            self.station.busy_servers += 1
            ns.service_start_time = self.current_time

            end_t = self.current_time + self.service_time
            self.schedule(Event(time=end_t, type=EventType.SERVICE_END, student_id=next_sid))

            print(
                f"  dequeued -> start service Student {next_sid}; queue_len={self.station.queue_length()}; "
                f"busy={self.station.busy_servers}/{self.station.servers}; end@{end_t:.2f}"
            )
