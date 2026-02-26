from dataclasses import dataclass


@dataclass
class Student:
    student_id: int
    arrival_time: float
    service_start_time: float | None = None
    departure_time: float | None = None


@dataclass
class FoodStation:
    station_id: int
    servers: int = 1
    busy_servers: int = 0
    waiting_count: int = 0

    def has_free_server(self) -> bool:
        return self.busy_servers < self.servers