# Presentation Guide — Elevator Simulation (20 min)

---

## Overview

```
Problem restatement     2 min   (no code)
Design decisions        3 min   (no code)
Walk the main loop      4 min   (simulation.py)
Live demo               7 min   (browser — presentation.html)
Trade-offs              3 min   (no code)
Hand back to panel      1 min
```

---

## 1. Problem Restatement (2 min)

> "The task was to simulate a destination dispatch elevator system in discrete time.
> Passengers submit where they are and where they want to go upfront.
> The system immediately assigns them to a specific elevator and tracks
> how efficiently everyone gets served — measuring wait time and total time."

Key points to land:
- Destination dispatch — passenger gives BOTH floors at request time
- Discrete time — 1 tick = 1 floor of travel
- Goal is to minimize total_time = wait_time + travel_time

---

## 2. Design Decisions (3 min)

> "Before writing any code I identified three questions the system needs to answer:
>
> 1. Which elevator should serve this passenger? — answered by the Scheduler
> 2. Where should each elevator go next? — answered by the SCAN movement algorithm
> 3. What happens when an elevator arrives at a floor? — answered by the stop processor
>
> Each question lives in its own piece of code. They don't talk to each other directly —
> they communicate through two shared data structures on the elevator:
> pickup_floors and dropoff_floors."

Point to files:
- scheduler.py → answers Q1
- models.py (choose_next_target) → answers Q2
- simulation.py (_process_stops) → answers Q3

---

## 3. Walk the Main Loop (4 min)

Open: elevator_sim/simulation.py — the run() method

> "Everything runs on a single time loop. Each tick has a fixed order:"

Point to each line as you say it:

```
1. Record all elevator positions     ← positions_timeline.append(...)
2. Admit requests for this tick      ← _assign_new_requests()
3. Board and unboard passengers      ← _process_stops()
4. Check if simulation is done
5. Move every elevator one floor     ← elevator.move_one_tick()
6. current_time += 1
```

> "The order matters — positions are recorded before movement,
> so the log shows where elevators were at time T, not after they moved."

Then briefly show _assign_new_requests:
> "This only admits requests where time == current_time.
> Anything beyond that is a future request — the simulation never peeks ahead.
> When a passenger is admitted it does three things:
> records the assignment, adds them to the elevator's waiting list,
> and adds their pickup floor to the elevator's targets."

Then briefly show _process_stops:
> "Every elevator checks its current floor each tick.
> First it drops off anyone who has arrived at their destination.
> Then it boards anyone waiting at that floor — dropoffs first,
> so freed capacity is available for new boarders in the same tick."

---

## 4. Live Demo (7 min)

Open: output/presentation.html in browser

Run the simulation first if needed:
    python visualize.py

### Building tab (2 min)
- Press Play — show elevators moving
- Point out: orange dots = pickup floors, green dots = dropoff floors
- Point out: direction arrows on each car
- Right panel shows onboard passengers and targets

> "You can see elevator 0 heading to floor 1 to pick up passenger1,
> then travelling all the way to floor 51."

### Passengers tab (2 min)
- Show cards changing color as simulation plays
- Orange border = waiting, blue = riding, green = done

> "Each card shows the full journey — when they requested,
> which elevator was assigned, when they boarded and arrived."

### Timeline tab (2 min)
- Show Gantt chart
- Orange bar = waiting period, blue bar = travel period

> "This makes the trade-off visible — passengers going to high floors
> have short waits but long travel. Passengers going nearby have
> long waits if the elevator is far away."

### Stats tab (1 min)
- Show avg/max wait and total times
- Show per-passenger bar chart

---

## 5. Trade-offs and Improvements (3 min)

> "The main simplification is no physics — 1 tick always equals 1 floor
> regardless of speed or direction. In reality an elevator accelerates,
> cruises, then decelerates — it can't stop at every floor at full speed."

> "The scheduler is greedy — it makes the best local decision at assignment
> time but doesn't think ahead. It also doesn't consider elevator direction,
> so it might assign a passenger to an elevator that's moving away from them."

> "With more time I'd add:
> 1. Direction-aware scoring — prefer elevators already heading toward the passenger
> 2. A realistic time model — separate states for accelerating, cruising, door open, boarding
> 3. Zone-based routing — assign elevators to floor ranges in tall buildings"

---

## 6. Hand Back (1 min)

> "That's the overview. Happy to dive into any piece —
> the scheduling logic, the movement algorithm, the data model,
> or the trade-offs in more detail."

---

## Likely Questions and Answers

**"Why workload times 2 in the score?"**
> Distance and workload are both integers. Without the multiplier,
> a nearby elevator with 5 pending stops would beat a slightly farther idle one.
> The x2 weight makes workload matter enough to actually influence the decision.

**"What happens if the elevator is full and passengers are waiting?"**
> They stay in waiting_by_elevator with pickup_time = None.
> The pickup floor stays in pickup_floors, so the elevator comes back.
> Once it drops someone off, capacity frees up and it boards the next one.

**"Why SCAN and not just always go to the nearest target?"**
> Always nearest causes thrashing — the elevator keeps reversing direction
> every tick if there are targets both above and below.
> SCAN commits to one direction until it runs out of targets that way,
> which is more efficient and prevents starvation.

**"How does no-peek-ahead work?"**
> Requests are sorted by time. next_request_idx is a pointer into that list.
> Each tick only admits requests where time == current_time.
> The pointer never goes back, and never reads ahead.

**"What's the difference between the three schedulers?"**
> Nearest: distance + workload penalty — best overall performance
> Strict nearest: distance only — simple but can overload one elevator
> Round robin: ignores position entirely — fair but blind

**"Why separate PassengerRequest from PassengerState?"**
> Request is what the passenger submitted — it never changes, so it's frozen.
> State is what happened to them during the simulation — it changes constantly.
> Separating them makes it clear what's input vs what's output.

---

## Files to Have Open Before You Start

1. Browser: output/presentation.html
2. Editor: elevator_sim/simulation.py (run() method visible)
3. Editor: elevator_sim/scheduler.py
4. Editor: elevator_sim/models.py (choose_next_target visible)

---

## Commands to Run Beforehand

```bash
# Generate fresh visualization
python visualize.py

# Run simulation to generate output files
python main.py

# Compare schedulers
python compare_schedulers.py
```
