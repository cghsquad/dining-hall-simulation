from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto


class EventType(Enum):
    ARRIVAL = auto()
    SERVICE_END = auto()
    BALK_CHECK = auto()
    END_SIM = auto()


@dataclass
class Event:
    time: float
    type: EventType = field(compare=False)
    student_id: int | None = field(default=None, compare=False)
    station_id: int | None = field(default=None, compare=False)


    def __lt__(self, other: Event) -> bool:
        return self.time < other.time

    def __le__(self, other: Event) -> bool:
        return self.time <= other.time

    def __gt__(self, other: Event) -> bool:
        return self.time > other.time

    def __ge__(self, other: Event) -> bool:
        return self.time >= other.time
