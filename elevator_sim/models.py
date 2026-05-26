from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterable


class Direction(IntEnum):
    DOWN = -1
    IDLE = 0
    UP = 1


@dataclass(frozen=True)
class PassengerRequest:
    time: int
    passenger_id: str
    source: int
    dest: int

    def __post_init__(self) -> None:
        if self.time < 0:
            raise ValueError("Request time must be >= 0.")
        if self.source <= 0 or self.dest <= 0:
            raise ValueError("Floors must be positive integers.")
        if self.source == self.dest:
            raise ValueError("source and dest must differ.")

    @property
    def requested_direction(self) -> Direction:
        return Direction.UP if self.dest > self.source else Direction.DOWN


@dataclass
class PassengerState:
    request: PassengerRequest
    assigned_elevator: int | None = None
    pickup_time: int | None = None
    dropoff_time: int | None = None

    @property
    def wait_time(self) -> int:
        if self.pickup_time is None:
            raise ValueError("Passenger not yet picked up.")
        return self.pickup_time - self.request.time

    @property
    def travel_time(self) -> int:
        if self.pickup_time is None or self.dropoff_time is None:
            raise ValueError("Passenger travel not completed.")
        return self.dropoff_time - self.pickup_time

    @property
    def total_time(self) -> int:
        if self.dropoff_time is None:
            raise ValueError("Passenger not yet dropped off.")
        return self.dropoff_time - self.request.time


@dataclass
class Elevator:
    elevator_id: int
    current_floor: int
    capacity: int
    direction: Direction = Direction.IDLE
    onboard_passengers: list[str] = field(default_factory=list)
    pickup_floors: set[int] = field(default_factory=set)
    dropoff_floors: set[int] = field(default_factory=set)

    @property
    def load(self) -> int:
        return len(self.onboard_passengers)

    @property
    def has_pending_work(self) -> bool:
        return bool(self.pickup_floors or self.dropoff_floors)

    def all_targets(self) -> Iterable[int]:
        return self.pickup_floors | self.dropoff_floors

    def choose_next_target(self) -> int | None:
        targets = list(self.all_targets())
        if not targets:
            return None

        if self.direction == Direction.UP:
            upward = [floor for floor in targets if floor >= self.current_floor]
            if upward:
                return min(upward)
        elif self.direction == Direction.DOWN:
            downward = [floor for floor in targets if floor <= self.current_floor]
            if downward:
                return max(downward)

        return min(targets, key=lambda floor: abs(floor - self.current_floor))

    def move_one_tick(self) -> None:
        target = self.choose_next_target()
        if target is None or target == self.current_floor:
            self.direction = Direction.IDLE
            return

        if target > self.current_floor:
            self.current_floor += 1
            self.direction = Direction.UP
        else:
            self.current_floor -= 1
            self.direction = Direction.DOWN
