import unittest

from elevator_sim.models import PassengerRequest
from elevator_sim.scheduler import create_scheduler
from elevator_sim.simulation import ElevatorSimulation, SimulationConfig


class SimulationTests(unittest.TestCase):
    def test_all_passengers_are_served(self) -> None:
        requests = [
            PassengerRequest(time=0, passenger_id="a", source=1, dest=5),
            PassengerRequest(time=1, passenger_id="b", source=2, dest=6),
            PassengerRequest(time=2, passenger_id="c", source=6, dest=1),
        ]
        sim = ElevatorSimulation(
            SimulationConfig(num_elevators=2, num_floors=10, max_passengers_per_elevator=2)
        )
        result = sim.run(requests)

        for state in result.passenger_states.values():
            self.assertIsNotNone(state.pickup_time)
            self.assertIsNotNone(state.dropoff_time)
            self.assertGreaterEqual(state.wait_time, 0)
            self.assertGreaterEqual(state.total_time, state.wait_time)

    def test_all_scheduler_modes_complete_requests(self) -> None:
        requests = [
            PassengerRequest(time=0, passenger_id="p1", source=1, dest=8),
            PassengerRequest(time=0, passenger_id="p2", source=1, dest=3),
            PassengerRequest(time=1, passenger_id="p3", source=5, dest=2),
            PassengerRequest(time=2, passenger_id="p4", source=7, dest=10),
        ]

        config = SimulationConfig(num_elevators=3, num_floors=12, max_passengers_per_elevator=2)
        for scheduler_name in ["nearest", "strict_nearest", "round_robin"]:
            sim = ElevatorSimulation(config, scheduler=create_scheduler(scheduler_name))
            result = sim.run(requests)
            self.assertGreaterEqual(result.finished_at_time, 0)
            self.assertEqual(len(result.positions_timeline[-1]), config.num_elevators)
            self.assertTrue(all(state.dropoff_time is not None for state in result.passenger_states.values()))


if __name__ == "__main__":
    unittest.main()
