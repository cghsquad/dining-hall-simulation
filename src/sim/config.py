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
    service_time: float = 2.0          # global mean service time (minutes)
    service_dist: str = "exponential"  # "exponential" for M/M/c, "deterministic" for M/D/c
    servers: int = 1                   # default servers per station

    # multi-station
    num_stations: int = 1
    stations_servers: list[int] | None = None       # per-station server counts
    stations_service_time: list[float] | None = None  # per-station mean service times (μ override)

    # routing
    routing_policy: str = "single"     # "single" | "shortest_queue" | "weighted_random"
    routing_weights: list[float] | None = None  # weights for weighted_random policy

    # balking / reneging
    balking_enabled: bool = False
    balking_model: str = "threshold"   # "threshold" | "logistic"
    balk_tau: float = 5.0              # patience threshold τ
    balk_p: float = 0.0               # leave probability (threshold model)
    balk_k: float = 1.0               # logistic steepness k (logistic model only)

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
        if self.service_dist not in ("exponential", "deterministic"):
            raise ValueError("service_dist must be 'exponential' or 'deterministic'")
        if not (0.0 <= self.balk_p <= 1.0):
            raise ValueError("balk_p must be in [0, 1]")
        if self.num_stations < 1:
            raise ValueError("num_stations must be >= 1")
        if self.stations_servers is not None:
            if len(self.stations_servers) != self.num_stations:
                raise ValueError(
                    f"stations_servers length ({len(self.stations_servers)}) "
                    f"must match num_stations ({self.num_stations})"
                )
            if any(s < 1 for s in self.stations_servers):
                raise ValueError("each entry in stations_servers must be >= 1")
        if self.stations_service_time is not None:
            if len(self.stations_service_time) != self.num_stations:
                raise ValueError(
                    f"stations_service_time length ({len(self.stations_service_time)}) "
                    f"must match num_stations ({self.num_stations})"
                )
            if any(t <= 0 for t in self.stations_service_time):
                raise ValueError("each entry in stations_service_time must be > 0")
        if self.routing_policy not in ("single", "shortest_queue", "weighted_random"):
            raise ValueError("routing_policy must be 'single', 'shortest_queue', or 'weighted_random'")
        if self.routing_weights is not None:
            if len(self.routing_weights) != self.num_stations:
                raise ValueError(
                    f"routing_weights length ({len(self.routing_weights)}) "
                    f"must match num_stations ({self.num_stations})"
                )
            if any(w < 0 for w in self.routing_weights):
                raise ValueError("routing_weights entries must be >= 0")
            if sum(self.routing_weights) <= 0:
                raise ValueError("routing_weights must have a positive sum")
        if self.balking_model not in ("threshold", "logistic"):
            raise ValueError("balking_model must be 'threshold' or 'logistic'")


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
