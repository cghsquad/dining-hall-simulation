from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .entities import FoodStation
    from .metrics import Metrics


#  EventRecord – one row in the events CSV

@dataclass
class EventRecord:
    sim_time: float
    wall_timestamp: float
    event_type: str
    student_id: int | None
    station_id: int | None
    queue_lengths: str
    busy_servers: str
    details: str = ""


#  TimeSeriesRecord – one row in the timeseries CSV

@dataclass
class TimeSeriesRecord:
    sim_time: float
    station_id: int
    queue_length: int
    busy_servers: int
    total_servers: int
    utilization: float
    total_arrivals: int
    total_departures: int
    total_balks: int


#  DataCollector – buffers event + timeseries rows, writes files at end

class DataCollector:
    """
    Buffers per-event and periodic time-series data during a simulation run,
    then writes structured output files (events CSV, timeseries CSV,
    summary JSON) alongside the existing config snapshot.
    """

    def __init__(self, outdir: str, run_id: str, seed: int, snapshot_interval: float = 0.5) -> None:
        self.outdir = Path(outdir)
        self.run_id = run_id
        self.seed = seed
        self.snapshot_interval = snapshot_interval

        self._events: list[EventRecord] = []
        self._timeseries: list[TimeSeriesRecord] = []

        # wall-clock timing
        self._wall_start: float = 0.0
        self._wall_end: float = 0.0

        # next scheduled snapshot time
        self._next_snapshot: float = snapshot_interval

    @property
    def _prefix(self) -> str:
        """Filename prefix: run_XXX_seedN"""
        return f"run_{self.run_id}_seed{self.seed}"

    # ------------------------------------------------------------------
    #  Timing
    # ------------------------------------------------------------------

    def start_timer(self) -> None:
        self._wall_start = time.perf_counter()

    def stop_timer(self) -> None:
        self._wall_end = time.perf_counter()

    @property
    def execution_time(self) -> float:
        """Wall-clock seconds elapsed."""
        return self._wall_end - self._wall_start

    # ------------------------------------------------------------------
    #  Event logging
    # ------------------------------------------------------------------

    def log_event(
        self,
        sim_time: float,
        event_type: str,
        stations: dict[int, FoodStation],
        student_id: int | None = None,
        station_id: int | None = None,
        details: str = "",
    ) -> None:
        sorted_ids = sorted(stations)
        q_lens = ",".join(str(stations[i].queue_length()) for i in sorted_ids)
        busy = ",".join(
            f"{stations[i].busy_servers}/{stations[i].servers}" for i in sorted_ids
        )
        self._events.append(EventRecord(
            sim_time=round(sim_time, 4),
            wall_timestamp=round(time.perf_counter() - self._wall_start, 6),
            event_type=event_type,
            student_id=student_id,
            station_id=station_id,
            queue_lengths=q_lens,
            busy_servers=busy,
            details=details,
        ))

    #  Time-series snapshots

    def maybe_snapshot(
        self,
        sim_time: float,
        stations: dict[int, FoodStation],
        metrics: Metrics,
        busy_time: dict[int, float],
    ) -> None:
        """Called on every time advance; emits a row when the interval elapses."""
        while sim_time >= self._next_snapshot:
            t = self._next_snapshot
            for sid in sorted(stations):
                st = stations[sid]
                bt = busy_time.get(sid, 0.0)
                denom = st.servers * t if t > 0 else 0.0
                util = min(bt / denom, 1.0) if denom > 0 else 0.0
                self._timeseries.append(TimeSeriesRecord(
                    sim_time=round(t, 4),
                    station_id=sid,
                    queue_length=st.queue_length(),
                    busy_servers=st.busy_servers,
                    total_servers=st.servers,
                    utilization=round(util, 4),
                    total_arrivals=metrics.total_arrivals,
                    total_departures=metrics.total_departures,
                    total_balks=metrics.instant_balks + metrics.reneges,
                ))
            self._next_snapshot += self.snapshot_interval

    #  File writers

    def write_events_csv(self) -> Path:
        path = self.outdir / f"{self._prefix}_events.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "sim_time", "wall_timestamp", "event_type",
            "student_id", "station_id",
            "queue_lengths", "busy_servers", "details",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for rec in self._events:
                writer.writerow([
                    rec.sim_time, rec.wall_timestamp, rec.event_type,
                    rec.student_id if rec.student_id is not None else "",
                    rec.station_id if rec.station_id is not None else "",
                    rec.queue_lengths, rec.busy_servers, rec.details,
                ])
        return path

    def write_timeseries_csv(self) -> Path:
        path = self.outdir / f"{self._prefix}_timeseries.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "sim_time", "station_id", "queue_length",
            "busy_servers", "total_servers", "utilization",
            "total_arrivals", "total_departures", "total_balks",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for rec in self._timeseries:
                writer.writerow([
                    rec.sim_time, rec.station_id, rec.queue_length,
                    rec.busy_servers, rec.total_servers, rec.utilization,
                    rec.total_arrivals, rec.total_departures, rec.total_balks,
                ])
        return path

    def write_summary_json(
        self,
        metrics: Metrics,
        stations: dict[int, FoodStation],
        sim_duration: float,
        seed: int,
    ) -> Path:
        path = self.outdir / f"{self._prefix}_summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        utilization = metrics.estimate_utilization(stations, sim_duration)
        throughput = metrics.compute_throughput(sim_duration)

        avg_wq = metrics.sum_wq / metrics.total_departures if metrics.total_departures else 0.0
        avg_w = metrics.sum_w / metrics.total_departures if metrics.total_departures else 0.0

        summary = {
            "run_id": self.run_id,
            "seed": seed,
            "sim_duration": sim_duration,
            "execution_time_seconds": round(self.execution_time, 4),
            "counts": {
                "total_arrivals": metrics.total_arrivals,
                "total_departures": metrics.total_departures,
                "total_service_starts": metrics.total_service_starts,
                "instant_balks": metrics.instant_balks,
                "reneges": metrics.reneges,
                "total_balks": metrics.instant_balks + metrics.reneges,
            },
            "wait_times": {
                "avg_Wq": round(avg_wq, 4),
                "min_Wq": round(metrics.min_wq, 4),
                "max_Wq": round(metrics.max_wq, 4),
                "avg_W": round(avg_w, 4),
                "min_W": round(metrics.min_w, 4),
                "max_W": round(metrics.max_w, 4),
            },
            "throughput_per_min": round(throughput, 4),
            "utilization": {
                f"station_{sid}": round(rho, 4)
                for sid, rho in utilization.items()
            },
            "per_station_avg_Wq": {
                f"station_{sid}": round(wq, 4)
                for sid, wq in metrics.per_station_avg_wq().items()
            },
            "queue_depth": {
                "max_queue_length": metrics.max_queue_depth,
            },
            "total_events_logged": len(self._events),
            "total_timeseries_snapshots": len(self._timeseries),
        }

        path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    #  Data integrity validation
    # ------------------------------------------------------------------

    def validate_integrity(self, metrics: Metrics, sim_duration: float) -> list[str]:
        """
        Run sanity checks on collected data. Returns a list of warnings
        (empty list = all checks passed).
        """
        warnings: list[str] = []

        # departures should never exceed arrivals
        if metrics.total_departures > metrics.total_arrivals:
            warnings.append(
                f"FAIL: departures ({metrics.total_departures}) > arrivals ({metrics.total_arrivals})"
            )

        # balks + departures + in-system should equal arrivals
        total_balks = metrics.instant_balks + metrics.reneges
        in_system = metrics.total_arrivals - metrics.total_departures - total_balks
        if in_system < 0:
            warnings.append(
                f"FAIL: negative in-system count ({in_system}): "
                f"arrivals={metrics.total_arrivals}, departures={metrics.total_departures}, balks={total_balks}"
            )

        # service starts should not exceed arrivals minus instant balks
        if metrics.total_service_starts > metrics.total_arrivals - metrics.instant_balks:
            warnings.append(
                f"FAIL: service_starts ({metrics.total_service_starts}) > "
                f"arrivals - instant_balks ({metrics.total_arrivals - metrics.instant_balks})"
            )

        # no negative wait times
        if metrics.total_departures > 0:
            min_wq = metrics.min_wq if metrics.min_wq != float("inf") else 0.0
            min_w = metrics.min_w if metrics.min_w != float("inf") else 0.0
            if min_wq < 0:
                warnings.append(f"FAIL: negative min_Wq ({min_wq:.4f})")
            if min_w < 0:
                warnings.append(f"FAIL: negative min_W ({min_w:.4f})")
            if metrics.max_wq < 0:
                warnings.append(f"FAIL: negative max_Wq ({metrics.max_wq:.4f})")

        # utilization should be in [0, 1] (with small tolerance for rounding)
        for rec in self._timeseries:
            if rec.utilization < -0.001 or rec.utilization > 1.5:
                warnings.append(
                    f"WARN: utilization out of range at t={rec.sim_time}, "
                    f"station={rec.station_id}: {rec.utilization}"
                )
                break  # only report once

        # event timestamps should be non-decreasing
        for i in range(1, len(self._events)):
            if self._events[i].sim_time < self._events[i - 1].sim_time:
                warnings.append(
                    f"FAIL: events out of order at index {i}: "
                    f"t={self._events[i].sim_time} < t={self._events[i - 1].sim_time}"
                )
                break

        # sim duration should be positive
        if sim_duration <= 0:
            warnings.append(f"FAIL: sim_duration is non-positive ({sim_duration})")

        return warnings

    # ------------------------------------------------------------------
    #  Master index
    # ------------------------------------------------------------------

    def update_run_index(
        self,
        metrics: Metrics,
        sim_duration: float,
        config_path: str,
        validation_passed: bool,
    ) -> Path:
        """Append this run's entry to the master run_index.json file."""
        index_path = self.outdir / "run_index.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)

        # load existing index or start fresh
        if index_path.exists():
            existing = json.loads(index_path.read_text(encoding="utf-8"))
        else:
            existing = []

        avg_wq = metrics.sum_wq / metrics.total_departures if metrics.total_departures else 0.0

        entry = {
            "run_id": self.run_id,
            "seed": self.seed,
            "config_file": config_path,
            "sim_duration": sim_duration,
            "execution_time_seconds": round(self.execution_time, 4),
            "total_arrivals": metrics.total_arrivals,
            "total_departures": metrics.total_departures,
            "total_balks": metrics.instant_balks + metrics.reneges,
            "avg_Wq": round(avg_wq, 4),
            "throughput_per_min": round(
                metrics.compute_throughput(sim_duration), 4
            ),
            "validation_passed": validation_passed,
            "output_files": {
                "events": f"{self._prefix}_events.csv",
                "timeseries": f"{self._prefix}_timeseries.csv",
                "summary": f"{self._prefix}_summary.json",
                "config": f"{self._prefix}_config.json",
            },
        }

        existing.append(entry)
        index_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        return index_path

    # ------------------------------------------------------------------
    #  Write all outputs
    # ------------------------------------------------------------------

    def write_all(
        self,
        metrics: Metrics,
        stations: dict[int, FoodStation],
        sim_duration: float,
        seed: int,
        config_path: str = "",
    ) -> dict[str, Path]:
        """Write all output files, validate data, and update master index."""
        paths = {
            "events": self.write_events_csv(),
            "timeseries": self.write_timeseries_csv(),
            "summary": self.write_summary_json(metrics, stations, sim_duration, seed),
        }

        # data integrity validation
        warnings = self.validate_integrity(metrics, sim_duration)
        if warnings:
            print("  === DATA VALIDATION WARNINGS ===")
            for w in warnings:
                print(f"    {w}")
        else:
            print("  data validation: ALL CHECKS PASSED")

        # update master index
        index_path = self.update_run_index(
            metrics, sim_duration, config_path, validation_passed=len(warnings) == 0,
        )
        paths["index"] = index_path

        return paths
