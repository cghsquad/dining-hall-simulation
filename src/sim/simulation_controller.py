from __future__ import annotations

import heapq
import random

from .arrival_model import PiecewisePoissonArrivalModel
from .balking_model import BalkingModel, ThresholdBalkingModel, LogisticBalkingModel
from .config import SimConfig
from .entities import FoodStation, Staff, Student
from .event import Event, EventType
from .metrics import Metrics
from .routing_policy import (
    RoutingPolicy,
    ShortestQueuePolicy,
    WeightedRandomPolicy,
)


class SimulationController:
    """
    Banks-style Discrete-Event Simulation kernel.

    Owns the Future Event List (FEL), simulation clock, and dispatches
    events to handlers.  Delegates domain logic to:
      - ArrivalModel        (interarrival sampling)
      - RoutingPolicy       (station selection)
      - BalkingModel        (leave decisions)
      - FoodStation / Staff  (service start/end)
      - Metrics             (data collection)
    """

    # ------------------------------------------------------------------
    #  Initialisation
    # ------------------------------------------------------------------

    def __init__(self, cfg: SimConfig) -> None:
        cfg.validate()
        self.cfg = cfg

        self.current_time: float = 0.0
        self.end_time: float = cfg.end_time
        self.fel: list[Event] = []          # heapq priority queue
        self.rng = random.Random(cfg.seed)

        self.metrics = Metrics()

        # --- arrival model ---
        self.arrival_model = PiecewisePoissonArrivalModel(
            lambda_off=cfg.lambda_off,
            lambda_peak=cfg.lambda_peak,
            peak_start=cfg.peak_start,
            peak_end=cfg.peak_end,
        )

        # --- station registry ---
        servers_list = (
            cfg.stations_servers
            if cfg.stations_servers is not None
            else [cfg.servers] * cfg.num_stations
        )
        service_times = (
            cfg.stations_service_time
            if cfg.stations_service_time is not None
            else [cfg.service_time] * cfg.num_stations
        )

        self.stations: dict[int, FoodStation] = {}
        for i in range(cfg.num_stations):
            st = FoodStation(
                station_id=i,
                servers=servers_list[i],
                service_rate_mu=1.0 / service_times[i],
            )
            # populate Staff objects
            for j in range(servers_list[i]):
                st.staff.append(Staff(staff_id=j, station=st))
            self.stations[i] = st

        # --- routing policy ---
        self.routing: RoutingPolicy | None = None
        if cfg.routing_policy == "shortest_queue":
            self.routing = ShortestQueuePolicy()
        elif cfg.routing_policy == "weighted_random":
            if cfg.routing_weights is not None:
                w_map = {i: w for i, w in enumerate(cfg.routing_weights)}
            else:
                w_map = {i: 1.0 for i in range(cfg.num_stations)}
            self.routing = WeightedRandomPolicy(w_map)
        elif cfg.num_stations > 1 and cfg.routing_policy == "single":
            print("[WARN] num_stations > 1 but routing_policy='single'; all students go to station 0")

        # --- balking model ---
        self.balking_model: BalkingModel | None = None
        if cfg.balking_enabled:
            if cfg.balking_model == "logistic":
                self.balking_model = LogisticBalkingModel(k=cfg.balk_k)
            else:
                self.balking_model = ThresholdBalkingModel(p_leave=cfg.balk_p)

        # --- student bookkeeping ---
        self._next_student_id: int = 1
        self.students: dict[int, Student] = {}

        # --- global service params (fallback) ---
        self.service_time: float = cfg.service_time

    # ------------------------------------------------------------------
    #  FEL helpers
    # ------------------------------------------------------------------

    def schedule(self, e: Event) -> None:
        heapq.heappush(self.fel, e)

    def process_next_event(self) -> Event | None:
        """Pop the next event, advance clock, accumulate busy time."""
        if not self.fel:
            return None
        e = heapq.heappop(self.fel)
        prev_time = self.current_time
        self.current_time = e.time
        dt = self.current_time - prev_time
        self.metrics.accumulate_busy_time(self.stations, dt)
        return e

    @staticmethod
    def is_termination_condition_met(e: Event) -> bool:
        return e.type == EventType.END_SIM

    # ------------------------------------------------------------------
    #  Main run loop
    # ------------------------------------------------------------------

    def run_simulation(self, end_time: float | None = None) -> None:
        self.end_time = self.cfg.end_time if end_time is None else end_time

        self.schedule(Event(time=0.0, type=EventType.ARRIVAL))
        self.schedule(Event(time=self.end_time, type=EventType.END_SIM))

        print(f"=== START SIM end_time={self.end_time} seed={self.cfg.seed} ===")

        while self.fel:
            e = self.process_next_event()
            if e is None:
                break

            print(f"[POP] t={self.current_time:.2f} type={e.type.name} student={e.student_id}")

            if self.is_termination_condition_met(e):
                print("=== END_SIM event reached ===")
                break

            # dispatch
            if e.type == EventType.ARRIVAL:
                self.handle_arrival(e)
            elif e.type == EventType.SERVICE_START:
                self.handle_service_start(e)
            elif e.type == EventType.SERVICE_END:
                self.handle_service_end(e)
            elif e.type == EventType.BALK_CHECK:
                self.handle_balk_check(e)

        self.collect_metrics()

    def collect_metrics(self) -> None:
        """Print final metrics summary."""
        print("=== FINAL METRICS ===")
        print(self.metrics.report(sim_duration=self.end_time, stations=self.stations))

    # ------------------------------------------------------------------
    #  Service-time sampling
    # ------------------------------------------------------------------

    def _sample_service_time(self, station: FoodStation) -> float:
        """
        Sample a service duration for the given station.
        Uses per-station μ if available, else global mean.
        """
        mean = (1.0 / station.service_rate_mu) if station.service_rate_mu else self.service_time
        if self.cfg.service_dist == "exponential":
            return self.rng.expovariate(1.0 / mean)
        return mean

    # ------------------------------------------------------------------
    #  Station selection
    # ------------------------------------------------------------------

    def _select_station(self, student: Student) -> FoodStation:
        """Pick a station using the routing policy, or default to station 0."""
        if self.routing is not None:
            return self.routing.select_station(student, self.stations, self.rng)
        return self.stations[0]

    # ------------------------------------------------------------------
    #  Wait estimation (for instant-balk decision)
    # ------------------------------------------------------------------

    def _estimated_wait(self, st: FoodStation) -> float:
        """
        Wait estimate for balking decision (M/M/c approximation):
        Wq_est ≈ ((queue_len + 1) / servers) * mean_service_time
        """
        if st.has_free_server():
            return 0.0
        q = st.queue_length()
        c = max(1, st.servers)
        mean = (1.0 / st.service_rate_mu) if st.service_rate_mu else self.service_time
        return ((q + 1) / c) * mean

    # ------------------------------------------------------------------
    #  ARRIVAL handler
    # ------------------------------------------------------------------

    def handle_arrival(self, _e: Event | None = None) -> None:
        sid = self._next_student_id
        self._next_student_id += 1

        # Create student with per-student wait tolerance
        s = Student(
            student_id=sid,
            station_id=0,                  # placeholder; set after routing
            arrival_time=self.current_time,
            wait_tolerance=self.cfg.balk_tau,
        )

        # Route to station
        st = self._select_station(s)
        s.station_id = st.station_id
        s.station = st

        self.students[sid] = s
        self.metrics.record_arrival()

        queue_lens = [self.stations[i].queue_length() for i in sorted(self.stations)]
        busy = [
            f"{self.stations[i].busy_servers}/{self.stations[i].servers}"
            for i in sorted(self.stations)
        ]
        print(f"  ROUTE Student {sid} -> Station {st.station_id} (queue_lens={queue_lens}, busy={busy})")

        # ---- server free → start service immediately ----
        if st.has_free_server():
            staff_obj = st.start_service(s, self.current_time)
            self.metrics.record_service_start()
            svc_dur = self._sample_service_time(st)
            end_t = self.current_time + svc_dur
            self.schedule(Event(
                time=end_t, type=EventType.SERVICE_END,
                student_id=sid, station_id=st.station_id, staff=staff_obj,
            ))
            print(
                f"  ARRIVAL Student {sid} -> Station {st.station_id}: start service immediately; "
                f"busy={st.busy_servers}/{st.servers}; end@{end_t:.2f}"
            )
        else:
            # ---- instant balk check ----
            if self.balking_model is not None:
                wq_est = self._estimated_wait(st)
                if s.should_leave(wq_est, self.balking_model, self.rng):
                    s.leave_dining_hall()
                    self.metrics.record_instant_balk()
                    del self.students[sid]
                    print(
                        f"  INSTANT_BALK Student {sid} @ Station {st.station_id}: "
                        f"estWq={wq_est:.2f} > tau={self.cfg.balk_tau:.2f} "
                        f"(p={self.cfg.balk_p:.2f}) -> leaves"
                    )
                    self._schedule_next_arrival()
                    return

            # ---- enqueue ----
            s.join_queue(st)
            print(
                f"  ARRIVAL Student {sid} -> Station {st.station_id}: queued; "
                f"queue_len={st.queue_length()}; "
                f"busy={st.busy_servers}/{st.servers}"
            )

            # ---- schedule reneging check ----
            if self.balking_model is not None:
                check_t = self.current_time + self.cfg.balk_tau
                if check_t < self.end_time:
                    self.schedule(Event(
                        time=check_t,
                        type=EventType.BALK_CHECK,
                        student_id=sid,
                        station_id=st.station_id,
                    ))
                    print(f"  scheduled BALK_CHECK for Student {sid} @ Station {st.station_id} at t={check_t:.2f}")

        self._schedule_next_arrival()

    # ------------------------------------------------------------------
    #  SERVICE_START handler (informational)
    # ------------------------------------------------------------------

    def handle_service_start(self, e: Event) -> None:
        """Handle a SERVICE_START event (informational logging)."""
        if e.student_id is None:
            return
        if e.student_id in self.students:
            s = self.students[e.student_id]
            if s.service_start_time is not None:
                print(
                    f"  SERVICE_START Student {e.student_id} @ Station {e.station_id}: "
                    f"service_start_time={s.service_start_time:.2f}"
                )

    # ------------------------------------------------------------------
    #  SERVICE_END handler
    # ------------------------------------------------------------------

    def handle_service_end(self, e: Event) -> None:
        if e.student_id is None or e.station_id is None:
            return
        if e.station_id not in self.stations:
            print(f"  [WARN] SERVICE_END with invalid station_id={e.station_id}")
            return
        if e.student_id not in self.students:
            return

        station = self.stations[e.station_id]
        s = self.students[e.student_id]

        # Record departure
        s.departure_time = self.current_time
        self.metrics.record_departure(s)

        # Free the server
        station.end_service(staff_member=e.staff, end_time=self.current_time)

        wq = (s.service_start_time - s.arrival_time) if s.service_start_time is not None else 0.0
        w = s.departure_time - s.arrival_time
        print(
            f"  SERVICE_END Student {e.student_id} @ Station {e.station_id}: "
            f"Wq={wq:.2f}, W={w:.2f}; "
            f"busy={station.busy_servers}/{station.servers}"
        )

        # Fill ALL free servers from this station's queue (M/M/c)
        while station.has_free_server() and station.queue_length() > 0:
            next_sid = station.dequeue()
            if next_sid is not None and next_sid in self.students:
                self._start_service(next_sid, station)

    # ------------------------------------------------------------------
    #  BALK_CHECK handler (reneging)
    # ------------------------------------------------------------------

    def handle_balk_check(self, e: Event) -> None:
        if e.student_id is None or e.station_id is None:
            return
        if e.station_id not in self.stations:
            return
        if e.student_id not in self.students:
            return

        st = self.stations[e.station_id]
        s = self.students[e.student_id]

        # If already in service or departed → ignore
        if s.service_start_time is not None or s.departure_time is not None:
            return
        if e.student_id not in st.queue:
            return

        waited_so_far = self.current_time - s.arrival_time
        if waited_so_far < self.cfg.balk_tau:
            return

        # Delegate decision to the balking model
        if self.balking_model is not None and self.balking_model.should_leave(waited_so_far, self.cfg.balk_tau, self.rng):
            st.queue.remove(e.student_id)
            s.leave_dining_hall()
            self.metrics.record_renege()
            del self.students[e.student_id]
            print(
                f"  RENEGE Student {e.student_id} @ Station {e.station_id}: "
                f"waited={waited_so_far:.2f} >= tau={self.cfg.balk_tau:.2f} "
                f"(p={self.cfg.balk_p:.2f}) -> leaves"
            )

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------

    def _start_service(self, sid: int, station: FoodStation) -> None:
        """Start service for a student and schedule SERVICE_END."""
        s = self.students[sid]
        staff_obj = station.start_service(s, self.current_time)
        self.metrics.record_service_start()

        svc_dur = self._sample_service_time(station)
        end_t = self.current_time + svc_dur
        self.schedule(Event(
            time=end_t, type=EventType.SERVICE_END,
            student_id=sid, station_id=station.station_id, staff=staff_obj,
        ))
        print(
            f"  start service Student {sid} @ Station {station.station_id}; "
            f"queue_len={station.queue_length()}; "
            f"busy={station.busy_servers}/{station.servers}; end@{end_t:.2f}"
        )

    def _schedule_next_arrival(self) -> None:
        """Schedule the next ARRIVAL event using the arrival model."""
        next_t = self.arrival_model.next_arrival_time(self.current_time, self.rng)
        lam = self.arrival_model.lambda_at(self.current_time)
        delta = next_t - self.current_time

        if next_t < self.end_time:
            self.schedule(Event(time=next_t, type=EventType.ARRIVAL))
            print(
                f"  scheduled next ARRIVAL @ t={next_t:.2f} "
                f"(lambda={lam:.2f}/min, interarrival={delta:.2f})"
            )
        else:
            print(f"  next ARRIVAL would be after endTime (lambda={lam:.2f}/min)")
