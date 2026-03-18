from dataclasses import dataclass, field
from collections import deque
from typing import Deque


@dataclass
class Student:
    student_id: int
    station_id: int
    arrival_time: float
    service_start_time: float | None = None
    departure_time: float | None = None


@dataclass
class FoodStation:
    station_id: int
    servers: int = 1
    busy_servers: int = 0
    queue: Deque[int] = field(default_factory=deque)  # stores student IDs

    def has_free_server(self) -> bool:
        return self.busy_servers < self.servers

    def queue_length(self) -> int:
        return len(self.queue)
