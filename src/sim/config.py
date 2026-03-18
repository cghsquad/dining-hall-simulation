from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json


@dataclass
class SimConfig:
    # reproducibility / run control
    seed: int = 1
    end_time: float = 20.0

    # arrival model (students per minute)
    lambda_off: float = 0.30
    lambda_peak: float = 1.20
    peak_start: float = 5.0
    peak_end: float = 12.0

    # service model
    service_time: float = 2.0  # mean service time (minutes)
    servers: int = 1           # M/M/c: c servers

    num_stations: int = 1
    stations_servers: list[int] | None = None
    
    # future switches (safe defaults)
    routing_policy: str = "single"   # later: shortest_queue / weighted_random
    balking_enabled: bool = False
    balk_tau: float = 5.0
    balk_p: float = 0.0

    def validate(self) -> None:
        if self.end_time <= 0:
            raise ValueError("end_time must be > 0")
        if self.lambda_off <= 0 or self.lambda_peak <= 0:
            raise ValueError("lambda_off and lambda_peak must be > 0")
        if not (0 <= self.peak_start < self.peak_end <= self.end_time):
            raise ValueError("Require 0 <= peak_start < peak_end <= end_time")
        if self.service_time <= 0:
            raise ValueError("service_time must be > 0")
        if self.servers < 1:
            raise ValueError("servers must be >= 1")
        if not (0.0 <= self.balk_p <= 1.0):
            raise ValueError("balk_p must be in [0, 1]")


def load_config(path: str | Path) -> SimConfig:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    cfg = SimConfig(**data)
    cfg.validate()
    return cfg


def save_config_snapshot(cfg: SimConfig, out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")