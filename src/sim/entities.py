from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .balking_model import BalkingModel
    from .routing_policy import RoutingPolicy


# ---------------------------------------------------------------------------
#  QueueDiscipline
# ---------------------------------------------------------------------------

class QueueDiscipline(Enum):
    FIFO = auto()


# ---------------------------------------------------------------------------
#  Student
# ---------------------------------------------------------------------------

@dataclass
class Student:
    student_id: int
    station_id: int
    arrival_time: float
    service_start_time: float | None = None
    departure_time: float | None = None

    # --- NEW fields (UML alignment) ---
    wait_tolerance: float | None = None     # per-student τ (patience threshold)
    balked: bool = False
    station: FoodStation | None = field(default=None, repr=False)

    # --- Student-side helpers (thin wrappers, match UML methods) ---

    def choose_station(
        self,
        stations: dict[int, FoodStation],
        policy: RoutingPolicy,
        rng: random.Random,
    ) -> FoodStation:
        """Delegate to the routing policy. Matches UML chooseStation()."""
        return policy.select_station(self, stations, rng)

    def join_queue(self, station: FoodStation) -> None:
        """Enqueue self at the given station. Matches UML joinQueue()."""
        station.enqueue(self.student_id)
        self.station = station
        self.station_id = station.station_id

    def should_leave(self, estimated_wait: float, model: BalkingModel, rng: random.Random) -> bool:
        """Delegate balking decision to the model. Matches UML shouldLeave()."""
        tau = self.wait_tolerance if self.wait_tolerance is not None else 0.0
        return model.should_leave(estimated_wait, tau, rng)

    def leave_dining_hall(self) -> None:
        """Mark this student as having balked. Matches UML leaveDiningHall()."""
        self.balked = True


# ---------------------------------------------------------------------------
#  Staff
# ---------------------------------------------------------------------------

@dataclass
class Staff:
    staff_id: int
    station: FoodStation | None = field(default=None, repr=False)
    is_busy: bool = False
    current_student: Student | None = field(default=None, repr=False)

    def begin_service(self, student: Student, start_time: float) -> None:
        self.is_busy = True
        self.current_student = student
        student.service_start_time = start_time

    def end_service(self, end_time: float) -> Student | None:
        s = self.current_student
        self.is_busy = False
        self.current_student = None
        if s is not None:
            s.departure_time = end_time
        return s


# ---------------------------------------------------------------------------
#  FoodStation
# ---------------------------------------------------------------------------

@dataclass
class FoodStation:
    station_id: int
    servers: int = 1                # c in M/M/c
    busy_servers: int = 0
    queue: deque[int] = field(default_factory=deque)   # student-ID queue

    # --- NEW fields (UML alignment) ---
    station_type: str = "default"
    service_rate_mu: float | None = None               # μ (customers/min); None → use global
    queue_discipline: QueueDiscipline = QueueDiscipline.FIFO
    staff: list[Staff] = field(default_factory=list)

    # --- existing helpers ---

    def has_free_server(self) -> bool:
        if self.staff:
            return any(not s.is_busy for s in self.staff)
        return self.busy_servers < self.servers

    def can_start_service(self) -> bool:
        """UML alias for has_free_server."""
        return self.has_free_server()

    def queue_length(self) -> int:
        return len(self.queue)

    # --- NEW queue helpers (UML enqueue / dequeue) ---

    def enqueue(self, student_id: int) -> None:
        self.queue.append(student_id)

    def dequeue(self) -> int | None:
        if self.queue:
            return self.queue.popleft()
        return None

    # --- NEW service helpers (UML startService / endService) ---

    def _sync_busy_count(self) -> None:
        """Keep busy_servers counter in sync with Staff state."""
        if self.staff:
            self.busy_servers = sum(1 for s in self.staff if s.is_busy)

    def start_service(self, student: Student, start_time: float) -> Staff | None:
        """
        Find a free Staff member and begin service.
        Returns the Staff object, or None if using legacy busy_servers counter.
        """
        for s in self.staff:
            if not s.is_busy:
                s.begin_service(student, start_time)
                self._sync_busy_count()
                return s
        # legacy fallback (no staff objects populated)
        if not self.staff and self.busy_servers < self.servers:
            self.busy_servers += 1
            student.service_start_time = start_time
        return None

    def end_service(self, staff_member: Staff | None = None, end_time: float = 0.0) -> None:
        """Free a server after service completes."""
        if staff_member is not None:
            staff_member.end_service(end_time)
            self._sync_busy_count()
        else:
            self.busy_servers = max(0, self.busy_servers - 1)
