from __future__ import annotations
import heapq
import random
from typing import Dict, List

from .event import Event, EventType
from .entities import Student, FoodStation
from .metrics import Metrics


class SimulationController:
    def __init__(self, seed: int = 1) -> None:
        self.current_time: float = 0.0
        self.end_time: float = 0.0
        self.fel: List[Event] = []  # heapq priority queue
        self.rng = random.Random(seed)

        self.metrics = Metrics()
        self.station = FoodStation(station_id=0, servers=1)

        self._next_student_id: int = 1
        self.students: Dict[int, Student] = {}

        # Step 2 constants (we’ll upgrade to λ(t) in Step 3)
        self.interarrival: float = 1.0  # minutes
        self.service_time: float = 2.0  # minutes

    def schedule(self, e: Event) -> None:
        heapq.heappush(self.fel, e)

    def run_simulation(self, end_time: float) -> None:
        self.end_time = end_time

        # Initial events
        self.schedule(Event(time=0.0, type=EventType.ARRIVAL))
        self.schedule(Event(time=end_time, type=EventType.END_SIM))

        print(f"=== START SIM end_time={end_time} ===")

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
            self.station.waiting_count += 1
            print(
                f"  ARRIVAL Student {sid}: queued; queue_len={self.station.waiting_count}; "
                f"busy={self.station.busy_servers}/{self.station.servers}"
            )

        # Schedule next arrival (if still before end_time)
        next_arrival_time = self.current_time + self.interarrival
        if next_arrival_time < self.end_time:
            self.schedule(Event(time=next_arrival_time, type=EventType.ARRIVAL))
            print(f"  scheduled next ARRIVAL @ t={next_arrival_time:.2f}")

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

        # If someone is waiting, start next service immediately (placeholder behavior)
        if self.station.waiting_count > 0:
            self.station.waiting_count -= 1

            # Create a “next” student placeholder: in Step 3 we will store actual queued students.
            next_sid = self._next_student_id
            self._next_student_id += 1
            ns = Student(student_id=next_sid, arrival_time=self.current_time)  # placeholder
            ns.service_start_time = self.current_time
            self.students[next_sid] = ns

            self.station.busy_servers += 1
            end_t = self.current_time + self.service_time
            self.schedule(Event(time=end_t, type=EventType.SERVICE_END, student_id=next_sid))

            print(
                f"  dequeued -> start service Student {next_sid}; queue_len={self.station.waiting_count}; "
                f"busy={self.station.busy_servers}/{self.station.servers}; end@{end_t:.2f}"
            )
