from sim.simulation_controller import SimulationController


def main() -> None:
    sim = SimulationController(seed=1)

    # Configurable parameters
    sim.lambda_off = 0.30  # off-peak arrivals per minute
    sim.lambda_peak = 1.20  # peak arrivals per minute
    sim.peak_start = 5.0  # minutes
    sim.peak_end = 12.0  # minutes
    sim.service_time = 2.0  # mean service time (minutes)
    end_time = 20.0  # simulation length (minutes)

    sim.run_simulation(end_time=end_time)


if __name__ == "__main__":
    main()
