from __future__ import annotations

from typing import Protocol

from elevator_sim.models import Elevator, PassengerRequest


class ElevatorScheduler(Protocol):
    def choose_elevator(self, request: PassengerRequest, elevators: list[Elevator]) -> int:
        ...


class NearestCarScheduler:
    """Simple nearest-car scheduler with light workload balancing."""

    def choose_elevator(self, request: PassengerRequest, elevators: list[Elevator]) -> int:
        best_elevator: Elevator | None = None
        best_score: int | None = None

        for elevator in elevators:
            score = self._score(elevator, request)
            if best_score is None or score < best_score:
                best_score = score
                best_elevator = elevator

        if best_elevator is None:
            raise RuntimeError("No elevator candidates available.")

        return best_elevator.elevator_id

    def _score(self, elevator: Elevator, request: PassengerRequest) -> int:
        distance_to_pickup = abs(elevator.current_floor - request.source)
        workload = len(elevator.pickup_floors) + len(elevator.dropoff_floors)

        # Simple and interview-friendly: nearest elevator wins, with light tie-break for load.
        return distance_to_pickup + (workload * 2)


class StrictNearestScheduler:
    """Simpler baseline: choose elevator with minimum distance only."""

    def choose_elevator(self, request: PassengerRequest, elevators: list[Elevator]) -> int:
        return min(
            elevators,
            key=lambda elevator: (abs(elevator.current_floor - request.source), elevator.elevator_id),
        ).elevator_id


class RoundRobinScheduler:
    """Fairness baseline: rotate assignments regardless of state."""

    def __init__(self) -> None:
        self._next_index = 0

    def choose_elevator(self, request: PassengerRequest, elevators: list[Elevator]) -> int:
        if not elevators:
            raise RuntimeError("No elevators configured.")

        chosen = elevators[self._next_index % len(elevators)]
        self._next_index += 1
        return chosen.elevator_id


def create_scheduler(name: str) -> ElevatorScheduler:
    normalized = name.strip().lower()
    if normalized == "nearest":
        return NearestCarScheduler()
    if normalized == "strict_nearest":
        return StrictNearestScheduler()
    if normalized == "round_robin":
        return RoundRobinScheduler()

    raise ValueError(
        "Unknown scheduler. Use one of: nearest, strict_nearest, round_robin."
    )
