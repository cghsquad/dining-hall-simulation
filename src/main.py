import argparse
from src.sim.config import load_config, SimConfig, save_config_snapshot
from src.sim.simulation_controller import SimulationController


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default=None, help="Path to config.json")
    parser.add_argument("--outdir", type=str, default="outputs", help="Output directory")

    # NEW: quick overrides (optional)
    parser.add_argument("--seed", type=int, default=None, help="Override RNG seed")
    parser.add_argument("--run_id", type=str, default="001", help="Run identifier (for filenames)")

    args = parser.parse_args()

    cfg = load_config(args.config) if args.config else SimConfig()

    # Apply overrides if provided
    if args.seed is not None:
        cfg.seed = args.seed

    cfg.validate()

    # Save snapshot (unique per run_id + seed)
    save_config_snapshot(cfg, f"{args.outdir}/run_{args.run_id}_seed{cfg.seed}_config.json")

    sim = SimulationController(cfg, outdir=args.outdir, run_id=args.run_id, config_path=args.config or "")
    sim.run_simulation(end_time=cfg.end_time)


if __name__ == "__main__":
    main()
