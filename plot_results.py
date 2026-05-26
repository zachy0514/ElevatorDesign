import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot elevator and passenger simulation results")
    parser.add_argument("--positions", default="output/elevator_positions.csv")
    parser.add_argument("--passengers", default="output/passenger_times.csv")
    parser.add_argument("--output", default="output/simulation_plots.png")
    return parser.parse_args()


def load_positions(path: str | Path) -> tuple[list[int], list[list[int]]]:
    times: list[int] = []
    per_elevator: list[list[int]] = []

    with Path(path).open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        elevator_columns = [name for name in (reader.fieldnames or []) if name.startswith("elevator_")]
        per_elevator = [[] for _ in elevator_columns]

        for row in reader:
            times.append(int(row["time"]))
            for idx, column in enumerate(elevator_columns):
                per_elevator[idx].append(int(row[column]))

    return times, per_elevator


def load_wait_and_total(path: str | Path) -> tuple[list[int], list[int]]:
    waits: list[int] = []
    totals: list[int] = []

    with Path(path).open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            waits.append(int(row["wait_time"]))
            totals.append(int(row["total_time"]))

    return waits, totals


def main() -> None:
    args = parse_args()

    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit(
            "matplotlib is required for plotting. Install with: pip install matplotlib"
        ) from exc

    times, positions = load_positions(args.positions)
    waits, totals = load_wait_and_total(args.passengers)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for idx, series in enumerate(positions):
        axes[0].plot(times, series, label=f"Elevator {idx}")
    axes[0].set_title("Elevator Positions Over Time")
    axes[0].set_xlabel("Time")
    axes[0].set_ylabel("Floor")
    axes[0].legend(loc="best")

    axes[1].hist(waits, bins=min(10, max(3, len(waits))), alpha=0.7, label="Wait time")
    axes[1].hist(totals, bins=min(10, max(3, len(totals))), alpha=0.7, label="Total time")
    axes[1].set_title("Passenger Time Distributions")
    axes[1].set_xlabel("Time units")
    axes[1].set_ylabel("Count")
    axes[1].legend(loc="best")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out, dpi=150)
    print(f"Wrote: {out}")


if __name__ == "__main__":
    main()
