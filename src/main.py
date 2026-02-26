from sim.simulation_controller import SimulationController


def main() -> None:
    sim = SimulationController(seed=1)
    sim.run_simulation(end_time=20.0)


if __name__ == "__main__":
    main()
