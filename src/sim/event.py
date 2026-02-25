from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto


class EventType(Enum):
    ARRIVAL = auto()
    SERVICE_END = auto()
    END_SIM = auto()


@dataclass(order=True)
class Event:
    time: float
    type: EventType = field(compare=False)
    student_id: int | None = field(default=None, compare=False)
