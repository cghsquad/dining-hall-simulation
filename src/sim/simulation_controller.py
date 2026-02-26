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
        self.interarrival: float = 1.0   # minutes
        self.service_time: float = 2.0   # minutes

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

