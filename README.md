# Dining Hall Simulation (CS 4632)

Discrete-event simulation (DES) prototype of a dining hall queueing system. The simulator uses an event-scheduling approach (Future Event List / priority queue) to model student arrivals, queueing, service completion, and termination, while collecting basic performance metrics.

---

## Project Status

### What’s implemented so far
- **Core DES framework:** Future Event List (FEL) using a priority queue; events processed in timestamp order.
- **Event types + dispatcher:** `ARRIVAL`, `SERVICE_END`, `END_SIM` with handler-based dispatch.
- **Time-dependent arrivals:** piecewise arrival-rate function **λ(t)** (off-peak vs peak window) with **exponential interarrival sampling**.
- **Persistent queueing:** deque-based queue stores student IDs; preserves arrival timestamps for correct waiting-time calculations.
- **Initial metrics:** total arrivals/departures, average waiting time in queue **avgWq**, and average time in system **avgW** printed at termination.
- **Configuration started:** parameters (seed, end time, λ values, peak window, service time) can be set in `src/main.py`.

### What’s still to come
- **RoutingPolicy:** station selection logic (e.g., shortest queue / weighted random) and support for multiple stations.
- **FoodStation M/M/c expansion:** validate multi-server behavior (`c > 1`) and (later) multiple stations with different parameters.
- **BalkingModel:** probabilistic leaving based on tolerance/wait or queue length.
- **Expanded metrics:** utilization (ρ), throughput, and richer reporting/plots for validation and analysis (M3–M4).

### Changes from the original proposal
- **Formalized arrival model:** implemented a piecewise **λ(t)** arrival-rate function and validated peak/off-peak behavior in console output.
- **Queue representation improved:** replaced placeholder waiting-count logic with a **persistent deque queue**, enabling correct **Wq** and **W** calculations.
- **Configuration approach:** parameters are currently configured in `main.py` (simple and transparent for M2).

---

## Installation Instructions

### Dependencies and versions
- **Python:** 3.10+ 
- **Packages:** see `requirements.txt`

### Using GitHub (clone the repo)
1. Copy the repository URL from GitHub (green **Code** button).
2. Clone and enter the project folder:
   ```bash
   git clone <YOUR_GITHUB_REPO_URL>
   cd <YOUR_REPO_FOLDER>

### Step-by-step setup
1. Clone the repo and enter the project folder:
   ```bash
   git clone <YOUR_REPO_URL>
   cd <YOUR_REPO_FOLDER>
   
### How to Run
1. ### How to run the simulation
From the project root:

1.
```bash 
python -m src.main
```

2. 
```bash
   python src/main.py
   ```

3. Open src/main.py and click Run (PyCharm/IntelliJ/VS Code), or right-click the file and select Run 'main'.
