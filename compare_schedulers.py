import argparse
import csv
from pathlib import Path

from elevator_sim.scheduler import create_scheduler
from elevator_sim.simulation import (
    ElevatorSimulation,
    SimulationConfig,
    build_metrics,
    load_requests_from_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare elevator scheduling algorithms")
    parser.add_argument("--input", default="sample_requests.csv", help="Path to input CSV")
    parser.add_argument("--num-elevators", type=int, default=3)
    parser.add_argument("--num-floors", type=int, default=60)
    parser.add_argument("--capacity", type=int, default=8)
    parser.add_argument("--output", default="output/scheduler_comparison.csv")
    return parser.parse_args()


def run_algorithm(
    algorithm: str,
    config: SimulationConfig,
    input_path: str,
) -> dict[str, str | int | float]:
    requests = load_requests_from_csv(input_path)
    simulation = ElevatorSimulation(config, scheduler=create_scheduler(algorithm))
    result = simulation.run(requests)
    metrics = build_metrics(result.passenger_states)

    return {
        "algorithm": algorithm,
        "passengers": int(metrics["passengers"]),
        "finish_time": result.finished_at_time,
        "avg_wait": float(metrics["avg_wait"]),
        "max_wait": int(metrics["max_wait"]),
        "avg_total": float(metrics["avg_total"]),
        "max_total": int(metrics["max_total"]),
    }


def write_results(path: str | Path, rows: list[dict[str, str | int | float]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    headers = [
        "algorithm",
        "passengers",
        "finish_time",
        "avg_wait",
        "max_wait",
        "avg_total",
        "max_total",
    ]

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def print_table(rows: list[dict[str, str | int | float]]) -> None:
    print("Scheduler Comparison")
    print("====================")
    print("algorithm       finish_time   avg_wait   max_wait   avg_total   max_total")
    for row in rows:
        print(
            f"{str(row['algorithm']).ljust(15)}"
            f"{str(row['finish_time']).rjust(12)}"
            f"{float(row['avg_wait']):11.2f}"
            f"{int(row['max_wait']):11d}"
            f"{float(row['avg_total']):12.2f}"
            f"{int(row['max_total']):11d}"
        )


def main() -> None:
    args = parse_args()
    config = SimulationConfig(
        num_elevators=args.num_elevators,
        num_floors=args.num_floors,
        max_passengers_per_elevator=args.capacity,
    )

    algorithms = ["nearest", "strict_nearest", "round_robin"]
    rows = [run_algorithm(algorithm, config, args.input) for algorithm in algorithms]

    write_results(args.output, rows)
    print_table(rows)
    print(f"\nWrote: {args.output}")


if __name__ == "__main__":
    main()
