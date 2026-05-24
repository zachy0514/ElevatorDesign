from __future__ import annotations

import argparse

from elevator_sim.scheduler import create_scheduler
from elevator_sim.simulation import (
    ElevatorSimulation,
    SimulationConfig,
    build_summary,
    load_requests_from_csv,
    write_passenger_log,
    write_positions_log,
    write_summary,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Destination-dispatch elevator simulation")
    parser.add_argument("--input", default="sample_requests.csv", help="Path to input CSV")
    parser.add_argument("--num-elevators", type=int, default=3)
    parser.add_argument("--num-floors", type=int, default=60)
    parser.add_argument("--capacity", type=int, default=8)
    parser.add_argument(
        "--scheduler",
        choices=["nearest", "strict_nearest", "round_robin"],
        default="nearest",
        help="Scheduling algorithm",
    )
    parser.add_argument("--positions-log", default="output/elevator_positions.csv")
    parser.add_argument("--passenger-log", default="output/passenger_times.csv")
    parser.add_argument("--summary-log", default="output/summary.txt")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requests = load_requests_from_csv(args.input)

    config = SimulationConfig(
        num_elevators=args.num_elevators,
        num_floors=args.num_floors,
        max_passengers_per_elevator=args.capacity,
    )

    simulation = ElevatorSimulation(config, scheduler=create_scheduler(args.scheduler))
    result = simulation.run(requests)

    write_positions_log(args.positions_log, result.positions_timeline)
    write_passenger_log(args.passenger_log, result.passenger_states)

    summary_text = build_summary(result.passenger_states)
    write_summary(args.summary_log, summary_text)

    print("Simulation complete")
    print(f"Scheduler: {args.scheduler}")
    print(f"Finished at time unit: {result.finished_at_time}")
    print(f"Positions log: {args.positions_log}")
    print(f"Passenger log: {args.passenger_log}")
    print(f"Summary: {args.summary_log}")


if __name__ == "__main__":
    main()
