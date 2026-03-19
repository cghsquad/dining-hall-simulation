from __future__ import annotations

import heapq
import random
import math
from typing import Dict, List

from .event import Event, EventType
from .entities import Student, FoodStation
from .metrics import Metrics
from .config import SimConfig
from .routing_policy import ShortestQueuePolicy


class SimulationController:
    def __init__(self, cfg: SimConfig) -> None:
        cfg.validate()
        self.cfg = cfg

        self.current_time: float = 0.0
        self.end_time: float = cfg.end_time
        self.fel: List[Event] = []  # heapq priority queue
        self.rng = random.Random(cfg.seed)

        self.metrics = Metrics()

        # --- station registry ---
        if cfg.stations_servers is not None:
            servers_list = cfg.stations_servers
        else:
            servers_list = [cfg.servers] * cfg.num_stations
        self.stations: Dict[int, FoodStation] = {
            i: FoodStation(station_id=i, servers=servers_list[i])
            for i in range(cfg.num_stations)
        }

        # routing policy
        self.routing: ShortestQueuePolicy | None = None
        if cfg.routing_policy == "shortest_queue":
            self.routing = ShortestQueuePolicy()

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

            prev_time = self.current_time
            self.current_time = e.time
            dt = self.current_time - prev_time

            # Step 4: accumulate busy time over the time jump
            self.metrics.accumulate_busy_time(self.stations, dt)

            print(f"[POP] t={self.current_time:.2f} type={e.type.name} student={e.student_id}")

            if e.type == EventType.END_SIM:
                print("=== END_SIM event reached ===")
                break

            if e.type == EventType.ARRIVAL:
                self.handle_arrival()
            elif e.type == EventType.SERVICE_END:
                self.handle_service_end(e.student_id, e.station_id)

        print("=== FINAL METRICS ===")
        print(self.metrics.report(sim_duration=self.end_time, stations=self.stations))

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

    def _select_station(self) -> FoodStation:
        """Pick a station using the routing policy, or default to station 0."""
        if self.routing is not None:
            sid = self.routing.select_station_id(self.stations, self.rng)
            return self.stations[sid]
        return self.stations[0]

    def _estimated_wait(self, st: FoodStation) -> float:
        """
        Simple wait estimate for balking:
        - if a server is free, estimated wait is 0
        - else approximate wait ~ (queue_len / servers) * mean_service_time
        """
        if st.has_free_server():
            return 0.0
        q = st.queue_length()
        servers = max(1, st.servers)
        return (q / servers) * self.service_time

    def handle_arrival(self) -> None:
        # Create student
        sid = self._next_student_id
        self._next_student_id += 1

        # Select station via routing policy
        st = self._select_station()

        queue_lens = [self.stations[i].queue_length() for i in sorted(self.stations)]
        busy = [f"{self.stations[i].busy_servers}/{self.stations[i].servers}" for i in sorted(self.stations)]
        print(f"  ROUTE Student {sid} -> Station {st.station_id} (queue_lens={queue_lens}, busy={busy})")

        s = Student(student_id=sid, station_id=st.station_id, arrival_time=self.current_time)
        self.students[sid] = s
        self.metrics.record_arrival()

        # Decide: start service or queue
        if st.has_free_server():
            st.busy_servers += 1
            s.service_start_time = self.current_time
            end_t = self.current_time + self.service_time
            self.schedule(Event(
                time=end_t, type=EventType.SERVICE_END,
                student_id=sid, station_id=st.station_id,
            ))
            print(
                f"  ARRIVAL Student {sid} -> Station {st.station_id}: start service immediately; "
                f"busy={st.busy_servers}/{st.servers}; end@{end_t:.2f}"
            )
        else:
            # --- Step 4: BalkingModel (optional via config) ---
            balked = False
            if self.cfg.balking_enabled:
                wq_est = self._estimated_wait(st)
                if wq_est > self.cfg.balk_tau and self.rng.random() < self.cfg.balk_p:
                    self.metrics.record_balk()
                    # Optional cleanup so self.students doesn't grow forever
                    del self.students[sid]
                    print(
                        f"  BALK Student {sid} @ Station {st.station_id}: "
                        f"estWq={wq_est:.2f} > tau={self.cfg.balk_tau:.2f} "
                        f"(p={self.cfg.balk_p:.2f}) -> leaves"
                    )
                    balked = True

            if not balked:
                st.queue.append(sid)
                print(
                    f"  ARRIVAL Student {sid} -> Station {st.station_id}: queued; "
                    f"queue_len={st.queue_length()}; "
                    f"busy={st.busy_servers}/{st.servers}"
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

    def _start_service(self, sid: int, station: FoodStation) -> None:
        """Start service for sid immediately at current_time and schedule SERVICE_END."""
        s = self.students[sid]
        station.busy_servers += 1
        s.service_start_time = self.current_time

        end_t = self.current_time + self.service_time
        self.schedule(Event(
            time=end_t, type=EventType.SERVICE_END,
            student_id=sid, station_id=station.station_id,
        ))

        print(
            f"  start service Student {sid} @ Station {station.station_id}; "
            f"queue_len={station.queue_length()}; "
            f"busy={station.busy_servers}/{station.servers}; end@{end_t:.2f}"
        )

    def handle_service_end(self, sid: int | None, station_id: int | None) -> None:
        if sid is None or station_id is None:
            return

        # Safety: ensure station_id is valid
        if station_id not in self.stations:
            print(f"  [WARN] SERVICE_END with invalid station_id={station_id} for sid={sid}")
            return

        station = self.stations[station_id]
        s = self.students[sid]

        # Record departure + metrics
        s.departure_time = self.current_time
        self.metrics.record_departure(s)

        # Free ONE server on the station that completed service
        station.busy_servers = max(0, station.busy_servers - 1)

        # Compute Wq/W from the student's timestamps
        wq = (s.service_start_time - s.arrival_time) if s.service_start_time is not None else 0.0
        w = s.departure_time - s.arrival_time

        print(
            f"  SERVICE_END Student {sid} @ Station {station_id}: Wq={wq:.2f}, W={w:.2f}; "
            f"busy={station.busy_servers}/{station.servers}"
        )

        # Fill ALL available servers from THIS station's queue (M/M/c)
        while station.has_free_server() and station.queue_length() > 0:
            next_sid = station.queue.popleft()
            self._start_service(next_sid, station)