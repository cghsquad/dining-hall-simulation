# Dining Hall Simulation (CS 4632)

Discrete-event simulation (DES) of a university dining hall queueing system. Uses a Banks-style event-scheduling approach with a Future Event List (heapq) to model student arrivals, multi-station routing, service, balking/reneging, and data collection.

---

## Features

- **NHPP Arrivals** -- piecewise-constant Non-Homogeneous Poisson Process with configurable off-peak/peak rates
- **Multi-Station Routing** -- shortest-queue and weighted-random policies across N food stations
- **M/M/c & M/D/c Service** -- exponential or deterministic service times, per-station server counts and service rates
- **Two-Channel Balking** -- instant balk at arrival + reneging (BALK_CHECK) via threshold or logistic probability models
- **Staff Objects** -- individual server tracking with begin/end service lifecycle
- **Data Collection** -- per-event CSV, periodic time-series CSV, summary JSON, config snapshot, and master run index
- **Data Validation** -- automated post-run integrity checks (7 sanity checks)
- **Configuration System** -- JSON config files with CLI overrides, validation, and 10 preset scenarios

---

## Installation

### Prerequisites
- Python 3.10+
- Git

### Using GitHub (clone the repo)
1. Go to the repository page and click the green **Code** button.
2. Copy the HTTPS or SSH URL.
3. Open a terminal and clone:
   ```bash
   git clone https://github.com/CGHSquad/Dining-Hall-Simulation.git
   ```
4. Navigate into the project folder:
   ```bash
   cd Dining-Hall-Simulation
   ```

### Using a ZIP download
1. On the repository page, click **Code** > **Download ZIP**.
2. Extract the ZIP file to your desired location.
3. Open a terminal and navigate to the extracted folder:
   ```bash
   cd Dining-Hall-Simulation
   ```

### Install dependencies
No external packages required — the project uses only the Python standard library. Just verify your Python version:
```bash
python3 --version   # Should be 3.10 or higher
```

### Verify it works
```bash
python3 -m src.main
```

You can also run directly via:
```bash
python3 src/main.py
```

Or open `src/main.py` in PyCharm/VS Code and click Run.

---

## Usage

### Default Run (Recommended)

```bash
python3 -m src.main --config config.json --outdir outputs --run_id 001 --seed 1
```

This runs the simulation with the default config and writes all output files (events CSV, timeseries CSV, summary JSON, config snapshot) to the `outputs/` directory.

### Change Parameters

You can override any parameter directly in `config.json` before running. For example, to test high traffic with logistic balking:

```json
{
  "lambda_peak": 3.00,
  "balking_model": "logistic",
  "balk_k": 2.0,
  "stations_servers": [1, 1]
}
```

Or override just the seed from the command line:

```bash
python3 -m src.main --config config.json --outdir outputs --run_id 001 --seed 42
```

### Run a Preset Scenario

10 preset configs are included in the `configs/` directory:

```bash
python3 -m src.main --config configs/run_009_stress_test.json --run_id 009 --outdir outputs
```

### Run All 10 Presets

```bash
for cfg in configs/run_*.json; do
  run_id=$(basename "$cfg" .json | sed 's/run_//; s/_.*//')
  python3 -m src.main --config "$cfg" --run_id "$run_id" --outdir outputs
done
```

### CLI Flags

| Flag       | Description                     | Default       |
|------------|---------------------------------|---------------|
| `--config` | Path to JSON config file        | `config.json` |
| `--seed`   | Override RNG seed               | from config   |
| `--run_id` | Identifier for output filenames | `001`         |
| `--outdir` | Output directory                | `outputs`     |

---

## Output Files

Each run produces 4 files in the output directory:

| File                           | Format | Contents                                                         |
|--------------------------------|--------|------------------------------------------------------------------|
| `run_XXX_seedN_events.csv`     | CSV    | One row per event (arrival, service, balk, etc.)                 |
| `run_XXX_seedN_timeseries.csv` | CSV    | Periodic state snapshots every 0.5 sim minutes                   |
| `run_XXX_seedN_summary.json`   | JSON   | Aggregate statistics (avg/min/max Wq/W, throughput, utilization) |
| `run_XXX_seedN_config.json`    | JSON   | Parameters used for this run                                     |

A master `run_index.json` is appended after each run, linking all runs to their output files.

---

## Project Structure

```
src/
  main.py                  -- entry point, CLI argument parsing
  sim/
    simulation_controller.py  -- DES kernel (FEL, clock, event dispatch)
    entities.py               -- Student, Staff, FoodStation, QueueDiscipline
    event.py                  -- Event dataclass, EventType enum
    config.py                 -- SimConfig dataclass, validation, JSON loading
    arrival_model.py          -- ArrivalModel ABC, PiecewisePoissonArrivalModel
    balking_model.py          -- BalkingModel ABC, Threshold + Logistic models
    routing_policy.py         -- RoutingPolicy ABC, ShortestQueue + WeightedRandom
    metrics.py                -- Metrics tracking (Wq, W, utilization, throughput)
    data_collector.py         -- Event/timeseries logging, CSV/JSON export, validation
configs/                     -- 10 preset scenario configs
outputs/                     -- generated output files (gitignored)
docs/
  config_reference.txt       -- full parameter documentation
```

---

## Configuration

See `docs/config_reference.txt` for the full parameter reference. Quick overview:

| Parameter                    | Type    | Description                                            |
|------------------------------|---------|--------------------------------------------------------|
| `seed`                       | int     | RNG seed for reproducibility                           |
| `end_time`                   | float   | Simulation duration (minutes)                          |
| `lambda_off` / `lambda_peak` | float   | Arrival rates outside/during peak (students/min)       |
| `peak_start` / `peak_end`    | float   | Peak period window (sim minutes)                       |
| `service_time`               | float   | Mean service time (minutes)                            |
| `service_dist`               | string  | `"exponential"` (M/M/c) or `"deterministic"` (M/D/c)   |
| `num_stations`               | int     | Number of food stations                                |
| `stations_servers`           | [int]   | Server count per station (e.g. `[1, 1, 1]`)            |
| `stations_service_time`      | [float] | Optional per-station service time override             |
| `routing_policy`             | string  | `"shortest_queue"`, `"weighted_random"`, or `"single"` |
| `balking_enabled`            | bool    | Enable/disable balking system                          |
| `balking_model`              | string  | `"threshold"` or `"logistic"`                          |
| `balk_tau`                   | float   | Patience threshold (minutes)                           |
| `balk_p`                     | float   | Leave probability (threshold model, 0.0-1.0)           |
| `balk_k`                     | float   | Logistic steepness (logistic model)                    |

---

## Preset Configs

| Run | File                           | Purpose                   |
|-----|--------------------------------|---------------------------|
| 001 | `run_001_baseline.json`        | Baseline defaults         |
| 002 | `run_002_high_traffic.json`    | High arrival rate         |
| 003 | `run_003_fast_service.json`    | Low service time          |
| 004 | `run_004_deterministic.json`   | M/D/c service model       |
| 005 | `run_005_logistic_balk.json`   | Logistic balking model    |
| 006 | `run_006_weighted_random.json` | Weighted random routing   |
| 007 | `run_007_no_balking.json`      | Balking disabled          |
| 008 | `run_008_single_station.json`  | Single station (M/M/3)    |
| 009 | `run_009_stress_test.json`     | High load, 4 stations     |
| 010 | `run_010_per_station_mu.json`  | Per-station service rates |

---

## Requirements

- Python 3.10+
- Standard library only (no external packages)
