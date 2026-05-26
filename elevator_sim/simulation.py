import csv
import statistics
from dataclasses import dataclass
from pathlib import Path

from elevator_sim.models import Elevator, PassengerRequest, PassengerState
from elevator_sim.scheduler import ElevatorScheduler, NearestCarScheduler


@dataclass
class SimulationConfig:
    num_elevators: int
    num_floors: int
    max_passengers_per_elevator: int
    start_floor: int = 1

    def __post_init__(self) -> None:
        if self.num_elevators <= 0:
            raise ValueError("num_elevators must be > 0")
        if self.num_floors <= 1:
            raise ValueError("num_floors must be > 1")
        if self.max_passengers_per_elevator <= 0:
            raise ValueError("max_passengers_per_elevator must be > 0")
        if self.start_floor < 1 or self.start_floor > self.num_floors:
            raise ValueError("start_floor out of range")


@dataclass
class SimulationResult:
    finished_at_time: int
    passenger_states: dict[str, PassengerState]
    positions_timeline: list[list[int]]


class ElevatorSimulation:
    def __init__(self, config: SimulationConfig, scheduler: ElevatorScheduler | None = None) -> None:
        self.config = config
        self.scheduler = scheduler or NearestCarScheduler()
        self.elevators = [
            Elevator(
                elevator_id=i,
                current_floor=config.start_floor,
                capacity=config.max_passengers_per_elevator,
            )
            for i in range(config.num_elevators)
        ]

    def run(self, requests: list[PassengerRequest]) -> SimulationResult:
        requests_sorted = sorted(requests, key=lambda req: (req.time, req.passenger_id))
        states = {req.passenger_id: PassengerState(request=req) for req in requests_sorted}

        waiting_by_elevator: dict[int, list[str]] = {e.elevator_id: [] for e in self.elevators}
        next_request_idx = 0
        current_time = 0
        positions_timeline: list[list[int]] = []

        while True:
            positions_timeline.append([e.current_floor for e in self.elevators])

            next_request_idx = self._assign_new_requests(
                current_time,
                next_request_idx,
                requests_sorted,
                states,
                waiting_by_elevator,
            )

            self._process_stops(current_time, states, waiting_by_elevator)

            all_completed = all(state.dropoff_time is not None for state in states.values())
            no_future_requests = next_request_idx >= len(requests_sorted)
            if all_completed and no_future_requests:
                return SimulationResult(
                    finished_at_time=current_time,
                    passenger_states=states,
                    positions_timeline=positions_timeline,
                )

            for elevator in self.elevators:
                elevator.move_one_tick()

            current_time += 1

    def _assign_new_requests(
        self,
        current_time: int,
        next_request_idx: int,
        requests_sorted: list[PassengerRequest],
        states: dict[str, PassengerState],
        waiting_by_elevator: dict[int, list[str]],
    ) -> int:
        while next_request_idx < len(requests_sorted) and requests_sorted[next_request_idx].time == current_time:
            req = requests_sorted[next_request_idx]
            assigned_elevator_id = self.scheduler.choose_elevator(req, self.elevators)

            states[req.passenger_id].assigned_elevator = assigned_elevator_id
            waiting_by_elevator[assigned_elevator_id].append(req.passenger_id)
            self.elevators[assigned_elevator_id].pickup_floors.add(req.source)
            next_request_idx += 1

        return next_request_idx

    def _process_stops(
        self,
        current_time: int,
        states: dict[str, PassengerState],
        waiting_by_elevator: dict[int, list[str]],
    ) -> None:
        for elevator in self.elevators:
            floor = elevator.current_floor

            remaining_onboard: list[str] = []
            for passenger_id in elevator.onboard_passengers:
                passenger = states[passenger_id]
                if passenger.request.dest == floor:
                    passenger.dropoff_time = current_time
                else:
                    remaining_onboard.append(passenger_id)
            elevator.onboard_passengers = remaining_onboard

            waiting_here = [
                pid
                for pid in waiting_by_elevator[elevator.elevator_id]
                if states[pid].request.source == floor and states[pid].pickup_time is None
            ]
            waiting_here.sort(key=lambda pid: (states[pid].request.time, states[pid].request.passenger_id))

            for passenger_id in waiting_here:
                if elevator.load >= elevator.capacity:
                    break
                passenger = states[passenger_id]
                passenger.pickup_time = current_time
                elevator.onboard_passengers.append(passenger_id)
                elevator.dropoff_floors.add(passenger.request.dest)

            elevator.dropoff_floors = {
                states[pid].request.dest
                for pid in elevator.onboard_passengers
                if states[pid].dropoff_time is None
            }

            elevator.pickup_floors = {
                states[pid].request.source
                for pid in waiting_by_elevator[elevator.elevator_id]
                if states[pid].pickup_time is None
            }


def load_requests_from_csv(path: str | Path) -> list[PassengerRequest]:
    requests: list[PassengerRequest] = []
    with Path(path).open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"time", "id", "source", "dest"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("CSV must contain headers: time,id,source,dest")

        for row in reader:
            requests.append(
                PassengerRequest(
                    time=int(row["time"]),
                    passenger_id=row["id"],
                    source=int(row["source"]),
                    dest=int(row["dest"]),
                )
            )

    return requests


def write_positions_log(path: str | Path, timeline: list[list[int]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["time"] + [f"elevator_{i}" for i in range(len(timeline[0]))]
        writer.writerow(header)
        for t, positions in enumerate(timeline):
            writer.writerow([t, *positions])


def write_passenger_log(path: str | Path, states: dict[str, PassengerState]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "request_time",
                "pickup_time",
                "dropoff_time",
                "wait_time",
                "travel_time",
                "total_time",
                "assigned_elevator",
            ]
        )

        for pid in sorted(states.keys()):
            s = states[pid]
            writer.writerow(
                [
                    pid,
                    s.request.time,
                    s.pickup_time,
                    s.dropoff_time,
                    s.wait_time,
                    s.travel_time,
                    s.total_time,
                    s.assigned_elevator,
                ]
            )


def build_summary(states: dict[str, PassengerState]) -> str:
    metrics = build_metrics(states)
    above_avg_wait = sum(1 for value in metrics["wait_times"] if value > metrics["avg_wait"])

    lines = [
        "Passenger Summary Statistics",
        "==========================",
        f"Passengers served: {metrics['passengers']}",
        "",
        "Wait time (pickup_time - request_time):",
        f"  min={metrics['min_wait']} max={metrics['max_wait']} avg={metrics['avg_wait']:.2f}",
        "",
        "Total time (dropoff_time - request_time):",
        f"  min={metrics['min_total']} max={metrics['max_total']} avg={metrics['avg_total']:.2f}",
        "",
        "Notable observations:",
        f"  - {above_avg_wait} passengers had wait time above average.",
        f"  - Longest total-time passenger took {metrics['max_total']} time units.",
    ]

    return "\n".join(lines)


def build_metrics(states: dict[str, PassengerState]) -> dict[str, float | int | list[int]]:
    wait_times = [state.wait_time for state in states.values()]
    total_times = [state.total_time for state in states.values()]

    avg_wait = statistics.fmean(wait_times)
    avg_total = statistics.fmean(total_times)
    return {
        "passengers": len(states),
        "min_wait": min(wait_times),
        "max_wait": max(wait_times),
        "avg_wait": avg_wait,
        "min_total": min(total_times),
        "max_total": max(total_times),
        "avg_total": avg_total,
        "wait_times": wait_times,
        "total_times": total_times,
    }


def write_summary(path: str | Path, summary_text: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(summary_text + "\n", encoding="utf-8")
