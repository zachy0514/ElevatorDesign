"""
present.py — Interview presentation + live elevator visualization.

Usage:
    python present.py
    python present.py --input simple_requests.csv --num-elevators 2 --num-floors 10
"""

import argparse
import json
from pathlib import Path

from elevator_sim.models import PassengerState
from elevator_sim.scheduler import create_scheduler
from elevator_sim.simulation import (
    ElevatorSimulation,
    SimulationConfig,
    SimulationResult,
    load_requests_from_csv,
)


class CapturingSimulation(ElevatorSimulation):
    def __init__(self, config, scheduler=None):
        super().__init__(config, scheduler)
        self.snapshots: list[dict] = []

    def run(self, requests) -> SimulationResult:
        requests_sorted = sorted(requests, key=lambda r: (r.time, r.passenger_id))
        states = {r.passenger_id: PassengerState(request=r) for r in requests_sorted}
        waiting_by_elevator = {e.elevator_id: [] for e in self.elevators}
        next_request_idx = 0
        current_time = 0
        positions_timeline: list[list[int]] = []

        while True:
            positions_timeline.append([e.current_floor for e in self.elevators])
            next_request_idx = self._assign_new_requests(
                current_time, next_request_idx, requests_sorted, states, waiting_by_elevator
            )
            self._process_stops(current_time, states, waiting_by_elevator)
            self._snapshot(current_time, states)

            all_done = all(s.dropoff_time is not None for s in states.values())
            no_future = next_request_idx >= len(requests_sorted)
            if all_done and no_future:
                return SimulationResult(
                    finished_at_time=current_time,
                    passenger_states=states,
                    positions_timeline=positions_timeline,
                )

            for elevator in self.elevators:
                elevator.move_one_tick()
            current_time += 1

    def _snapshot(self, t: int, states: dict) -> None:
        self.snapshots.append({
            "time": t,
            "elevators": [
                {
                    "id": e.elevator_id,
                    "floor": e.current_floor,
                    "direction": e.direction.name,
                    "onboard": list(e.onboard_passengers),
                    "pickup_targets": sorted(e.pickup_floors),
                    "dropoff_targets": sorted(e.dropoff_floors),
                }
                for e in self.elevators
            ],
            "passengers": {
                pid: {
                    "source": s.request.source,
                    "dest": s.request.dest,
                    "request_time": s.request.time,
                    "assigned": s.assigned_elevator,
                    "pickup_time": s.pickup_time,
                    "dropoff_time": s.dropoff_time,
                    "status": (
                        "done"    if s.dropoff_time is not None else
                        "riding"  if s.pickup_time  is not None else
                        "waiting" if s.assigned_elevator is not None else
                        "pending"
                    ),
                }
                for pid, s in states.items()
            },
        })


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Elevator Simulation — Presentation</title>
<style>
/* ── Design tokens ── */
:root {
  --bg:       #09090f;
  --surface:  rgba(255,255,255,0.03);
  --surface2: rgba(255,255,255,0.06);
  --border:   rgba(255,255,255,0.07);
  --accent:   #6366f1;
  --accent2:  #818cf8;
  --teal:     #5eead4;
  --text:     #ededf5;
  --muted:    #a0a0c0;
  --pending:#546e7a;--waiting:#f57c00;--riding:#1976d2;--done:#388e3c;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{
  background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
  height:100vh;overflow:hidden;
  background-image:radial-gradient(circle,rgba(99,102,241,.07) 1px,transparent 1px);
  background-size:30px 30px;
}

/* ── Progress bar ── */
#progress{
  position:fixed;top:0;left:0;height:2px;z-index:9999;
  background:linear-gradient(90deg,var(--accent),var(--accent2));
  transition:width .35s ease;border-radius:0 2px 2px 0;
}

/* ── Slide nav pill ── */
#pres-nav{
  position:fixed;bottom:28px;left:50%;transform:translateX(-50%);
  z-index:9999;display:flex;align-items:center;gap:18px;
  background:rgba(9,9,15,.8);border:1px solid var(--border);
  backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  border-radius:40px;padding:10px 24px;transition:opacity .25s;
}
#pres-nav.hidden{opacity:0;pointer-events:none;}
.pnav-btn{
  background:none;border:none;color:var(--muted);font-size:1rem;
  cursor:pointer;padding:4px 10px;border-radius:6px;transition:all .15s;
  font-weight:500;letter-spacing:.02em;
}
.pnav-btn:hover{color:var(--text);background:var(--surface2);}
.pnav-btn:disabled{opacity:.2;cursor:default;background:none;}
#slide-counter{font-size:0.82rem;color:var(--muted);min-width:40px;text-align:center;font-variant-numeric:tabular-nums;}
.nav-hint{font-size:0.7rem;color:var(--muted);opacity:.5;display:none;}

/* ── Slides layer ── */
#slides-layer{
  position:fixed;inset:0;z-index:100;
  display:flex;align-items:center;justify-content:center;
  transition:opacity .3s;
}
#slides-layer.hidden{opacity:0;pointer-events:none;}

.slide{
  display:none;flex-direction:column;opacity:0;
  transform:translateY(14px);
  width:100%;max-width:1060px;padding:0 72px;
  max-height:90vh;overflow-y:auto;
  transition:opacity .35s ease,transform .35s ease;
}
.slide.active{display:flex;}
.slide.visible{opacity:1;transform:translateY(0);}

/* ── Slide headings ── */
.slide h2{
  font-size:2.1rem;font-weight:700;letter-spacing:-.025em;
  margin-bottom:32px;padding-bottom:16px;position:relative;color:var(--text);
}
.slide h2::after{
  content:'';position:absolute;left:0;bottom:0;
  width:100%;height:1px;background:var(--border);
}
.slide h2::before{
  content:'';position:absolute;left:0;bottom:0;
  width:44px;height:2px;background:var(--accent);border-radius:2px;z-index:1;
}
.slide .sub{
  font-size:1rem;color:var(--muted);margin-bottom:26px;
  line-height:1.65;margin-top:-20px;
}

/* ── List items ── */
.slide>ul{list-style:none;display:flex;flex-direction:column;gap:10px;}
.slide>ul>li{
  background:var(--surface);border:1px solid var(--border);
  border-radius:10px;padding:16px 22px;
  font-size:1rem;line-height:1.55;position:relative;overflow:hidden;
}
.slide>ul>li::before{
  content:'';position:absolute;left:0;top:0;bottom:0;width:3px;
  background:linear-gradient(180deg,var(--accent),var(--accent2));
  border-radius:3px 0 0 3px;
}
.li-title{font-size:1.02rem;font-weight:600;color:var(--text);margin-bottom:4px;}
.li-sub{font-size:0.87rem;color:var(--muted);line-height:1.65;margin-top:5px;}
.mono{font-family:'Cascadia Code','Fira Code','Consolas',monospace;color:var(--teal);font-size:.95em;}

/* ── Two-column grid ── */
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:14px;width:100%;}

/* ── Glassmorphism cards ── */
.card{
  background:var(--surface);border:1px solid var(--border);
  border-radius:12px;padding:20px 22px;position:relative;overflow:hidden;
}
.card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,var(--accent),rgba(129,140,248,.3),transparent);
}
.card h3{
  font-size:0.7rem;color:var(--accent2);text-transform:uppercase;
  letter-spacing:.1em;margin-bottom:13px;font-weight:600;
}
.card p{font-size:0.95rem;color:var(--muted);line-height:1.9;}

/* ── Code blocks ── */
.code{
  background:rgba(0,0,0,.5);border:1px solid var(--border);
  border-radius:8px;overflow:hidden;margin:10px 0;
}
.code-bar{
  height:30px;background:rgba(255,255,255,.03);border-bottom:1px solid var(--border);
  display:flex;align-items:center;padding:0 14px;gap:6px;
}
.code-dot{width:9px;height:9px;border-radius:50%;background:rgba(255,255,255,.12);}
.code-inner{
  padding:14px 20px;font-family:'Cascadia Code','Fira Code','Consolas',monospace;
  font-size:0.93rem;color:var(--teal);line-height:1.75;
}

/* ── Timeline (slide 4) ── */
.timeline{display:flex;flex-direction:column;gap:0;position:relative;padding-left:20px;}
.timeline::before{
  content:'';position:absolute;left:36px;top:18px;bottom:18px;width:1px;
  background:linear-gradient(180deg,var(--accent),rgba(99,102,241,.1));
}
.tl-item{display:flex;align-items:flex-start;gap:20px;padding:4px 0 18px;}
.tl-item:last-child{padding-bottom:0;}
.tl-node{
  width:34px;height:34px;border-radius:50%;background:var(--accent);
  display:flex;align-items:center;justify-content:center;
  font-weight:700;font-size:0.88rem;flex-shrink:0;color:#fff;
  box-shadow:0 0 0 4px rgba(99,102,241,.15),0 0 16px rgba(99,102,241,.3);
  position:relative;z-index:1;
}
.tl-body{padding-top:6px;flex:1;}
.tl-title{font-size:1.02rem;font-weight:600;color:var(--text);margin-bottom:4px;}
.tl-sub{font-size:0.87rem;color:var(--muted);line-height:1.6;}

/* ── Inline tag ── */
.tag{
  display:inline-block;padding:2px 10px;border-radius:4px;font-size:0.7rem;
  font-weight:600;background:rgba(99,102,241,.2);color:var(--accent2);
  vertical-align:middle;margin-left:8px;letter-spacing:.04em;border:1px solid rgba(99,102,241,.3);
}

/* ── Title slide ── */
.title-eyebrow{
  font-size:0.78rem;color:var(--accent2);text-transform:uppercase;
  letter-spacing:.14em;font-weight:600;margin-bottom:18px;
}
.title-big{font-size:3.6rem;font-weight:800;line-height:1.1;letter-spacing:-.03em;margin-bottom:18px;}
.title-accent{
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.title-sub{font-size:1.1rem;color:var(--muted);margin-bottom:6px;font-weight:400;}
.title-by{font-size:0.9rem;color:var(--muted);opacity:.6;margin-bottom:52px;}
.title-rule{width:48px;height:2px;background:linear-gradient(90deg,var(--accent),transparent);border-radius:2px;margin-bottom:44px;}
.stat-row{display:flex;gap:14px;flex-wrap:wrap;}
.stat-chip{
  background:var(--surface);border:1px solid var(--border);border-radius:10px;
  padding:16px 24px;text-align:center;min-width:138px;position:relative;overflow:hidden;
  transition:border-color .2s,transform .2s;cursor:default;
}
.stat-chip::before{
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,var(--accent),rgba(129,140,248,.2),transparent);
}
.stat-chip:hover{border-color:rgba(99,102,241,.35);transform:translateY(-2px);}
.stat-chip .val{font-size:1.9rem;font-weight:700;color:var(--text);letter-spacing:-.02em;}
.stat-chip .lbl{font-size:0.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;margin-top:5px;}

/* ── Simulation layer ── */
#sim-layer{
  position:fixed;inset:0;z-index:50;display:flex;flex-direction:column;overflow:hidden;
  opacity:0;pointer-events:none;transition:opacity .3s;
}
#sim-layer.visible{opacity:1;pointer-events:auto;}
#sim-layer header{
  padding:10px 20px;background:#0d0d14;border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0;
}
#sim-layer header h1{font-size:0.92rem;font-weight:600;color:var(--text);}
#back-btn{
  background:var(--surface2);color:var(--text);border:1px solid var(--border);
  border-radius:6px;padding:4px 14px;font-size:0.78rem;font-weight:600;
  cursor:pointer;margin-right:10px;transition:all .15s;
}
#back-btn:hover{background:var(--accent);border-color:var(--accent);}
#time-badge{
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  color:#fff;padding:4px 18px;border-radius:20px;font-size:0.9rem;
  font-weight:700;min-width:80px;text-align:center;
}
#sim-layer nav{display:flex;background:#0d0d14;border-bottom:1px solid var(--border);flex-shrink:0;}
#sim-layer nav button{
  background:none;border:none;border-bottom:2px solid transparent;
  color:var(--muted);padding:9px 22px;font-size:0.84rem;cursor:pointer;transition:all .2s;
}
#sim-layer nav button.active{color:var(--text);border-bottom-color:var(--accent);}
#sim-layer nav button:hover{color:var(--text);}
#sim-layer main{flex:1;overflow:hidden;}
.view{display:none;height:100%;padding:13px;overflow-y:auto;}
.view.active{display:flex;}
#view-building{flex-direction:row;gap:13px;overflow:hidden;}
#building-wrap{flex:1;display:flex;background:#0d0d14;border:1px solid var(--border);border-radius:10px;overflow:hidden;min-width:0;}
#floor-labels{display:flex;flex-direction:column;justify-content:space-between;padding:28px 6px 4px;min-width:34px;border-right:1px solid var(--border);position:relative;}
.fl-label{font-size:0.6rem;color:var(--muted);text-align:right;position:absolute;right:4px;}
#shafts{display:flex;flex:1;position:relative;}
.shaft{flex:1;position:relative;border-right:1px solid var(--border);}
.shaft:last-child{border-right:none;}
.shaft-hdr{position:absolute;top:6px;left:0;right:0;text-align:center;font-size:0.7rem;font-weight:700;z-index:5;}
.elev-car{position:absolute;left:15%;width:70%;border-radius:6px;z-index:10;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  transition:top .28s ease;font-size:0.65rem;font-weight:700;color:#fff;gap:1px;
  box-shadow:0 2px 10px rgba(0,0,0,.5);}
.floor-dot{position:absolute;right:4px;width:7px;height:7px;border-radius:50%;z-index:3;}
.floor-dot.pickup{background:var(--waiting);}
.floor-dot.dropoff{background:var(--done);}
.floor-line{position:absolute;left:0;right:0;border-top:1px solid rgba(255,255,255,.03);}
#building-info{width:220px;flex-shrink:0;display:flex;flex-direction:column;gap:9px;overflow:hidden;}
.icard{background:#0d0d14;border:1px solid var(--border);border-radius:10px;padding:12px;}
.icard.grow{flex:1;overflow:hidden;display:flex;flex-direction:column;min-height:0;}
.icard h3{font-size:0.67rem;color:var(--accent2);text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;font-weight:600;}
.elev-row{display:flex;align-items:flex-start;gap:8px;margin-bottom:5px;font-size:0.8rem;}
.elev-dot{width:10px;height:10px;border-radius:3px;margin-top:2px;flex-shrink:0;}
.elev-sub{font-size:0.7rem;color:var(--muted);margin-top:1px;}
#inline-pax-list{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:4px;}
.ipax-row{display:flex;align-items:center;gap:7px;padding:5px 8px 5px 11px;border-radius:6px;
  background:rgba(255,255,255,.02);border:1px solid var(--border);position:relative;overflow:hidden;transition:border-color .3s;}
.ipax-row::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;border-radius:3px 0 0 3px;}
.ipax-row.pending::before{background:rgba(255,255,255,.15);}
.ipax-row.waiting::before{background:var(--waiting);}
.ipax-row.riding::before{background:var(--riding);}
.ipax-row.done::before{background:var(--done);}
.ipax-row.waiting{border-color:rgba(245,124,0,.25);}
.ipax-row.riding{border-color:rgba(25,118,210,.25);}
.ipax-row.done{border-color:rgba(56,142,60,.25);}
.ipax-name{font-size:0.71rem;font-weight:700;color:var(--text);min-width:28px;}
.ipax-route{font-size:0.68rem;color:var(--muted);flex:1;}
.ipax-st{font-size:0.61rem;font-weight:700;text-transform:uppercase;}
.ipax-st.pending{color:var(--muted);}
.ipax-st.waiting{color:var(--waiting);}
.ipax-st.riding{color:var(--riding);}
.ipax-st.done{color:var(--done);}
#view-passengers{flex-wrap:wrap;flex-direction:row;gap:10px;align-content:flex-start;}
.pax-card{background:#0d0d14;border:1px solid var(--border);border-radius:10px;padding:12px;width:175px;transition:border-color .3s;}
.pax-card.waiting{border-color:var(--waiting);}
.pax-card.riding{border-color:var(--riding);}
.pax-card.done{border-color:var(--done);}
.pax-card.pending{border-color:rgba(255,255,255,.1);}
.pax-id{font-size:0.82rem;font-weight:700;margin-bottom:4px;}
.pax-route{font-size:0.84rem;color:var(--muted);margin-bottom:6px;}
.pax-badge{display:inline-block;padding:2px 9px;border-radius:8px;font-size:0.67rem;font-weight:700;text-transform:uppercase;margin-bottom:6px;color:#fff;}
.pax-badge.pending{background:rgba(255,255,255,.1);color:var(--muted);}
.pax-badge.waiting{background:var(--waiting);}
.pax-badge.riding{background:var(--riding);}
.pax-badge.done{background:var(--done);}
.pax-meta{font-size:0.71rem;color:var(--muted);line-height:1.7;}
#view-timeline{flex-direction:column;}
#tl-wrap{flex:1;background:#0d0d14;border:1px solid var(--border);border-radius:10px;padding:12px;overflow-x:auto;}
#view-stats{flex-direction:row;gap:13px;align-items:flex-start;}
#stat-bigs{display:flex;flex-direction:column;gap:9px;width:150px;flex-shrink:0;}
.stat-big{background:#0d0d14;border:1px solid var(--border);border-radius:10px;padding:14px;text-align:center;}
.stat-val{font-size:1.7rem;font-weight:700;color:var(--accent2);}
.stat-lbl{font-size:0.67rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-top:2px;}
#bars-wrap{flex:1;background:#0d0d14;border:1px solid var(--border);border-radius:10px;padding:16px;}
#bars-wrap h3{font-size:0.7rem;color:var(--accent2);text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px;}
.bar-row{display:flex;align-items:center;gap:8px;margin-bottom:7px;}
.bar-lbl{font-size:0.71rem;color:var(--muted);width:76px;text-align:right;flex-shrink:0;}
.bar-track{flex:1;background:rgba(255,255,255,.05);border-radius:3px;height:14px;position:relative;overflow:hidden;}
.bar-wait{position:absolute;left:0;top:0;height:100%;background:var(--waiting);}
.bar-ride{position:absolute;top:0;height:100%;background:var(--riding);}
.bar-num{font-size:0.67rem;color:var(--muted);width:26px;flex-shrink:0;}
#sim-layer footer{
  padding:9px 18px;background:#0d0d14;border-top:1px solid var(--border);
  display:flex;align-items:center;gap:12px;flex-shrink:0;
}
.btn{background:var(--accent);color:#fff;border:none;border-radius:7px;
  padding:5px 16px;font-size:0.8rem;font-weight:600;cursor:pointer;transition:opacity .15s;}
.btn:hover{opacity:.85;}
.btn.sec{background:var(--surface2);border:1px solid var(--border);}
#scrubber{flex:1;accent-color:var(--accent);cursor:pointer;}
.ft-label{font-size:0.73rem;color:var(--muted);white-space:nowrap;}
#speed-sel{background:#0d0d14;color:var(--text);border:1px solid var(--border);border-radius:5px;padding:3px 7px;font-size:0.73rem;}
</style>
</head>
<body>

<!-- Progress bar -->
<div id="progress" style="width:12.5%"></div>

<!-- Nav pill -->
<div id="pres-nav">
  <button class="pnav-btn" id="btn-prev" onclick="prevSlide()" disabled>←</button>
  <span id="slide-counter">1 / 8</span>
  <button class="pnav-btn" id="btn-next" onclick="nextSlide()">→</button>
</div>

<!-- ── Slides ── -->
<div id="slides-layer">

  <!-- 1 · Title -->
  <div class="slide active" id="slide-1">
    <div class="title-eyebrow">Take-Home Interview · Elevator System</div>
    <div class="title-big">
      <span class="title-accent">Elevator</span><br>Simulation
    </div>
    <div class="title-sub">Destination Dispatch · Discrete-Time · Greedy Nearest-Car</div>
    <div class="title-by">Zach Yang</div>
    <div class="title-rule"></div>
    <div class="stat-row">
      <div class="stat-chip"><div class="val">SCAN</div><div class="lbl">Movement Algo</div></div>
      <div class="stat-chip"><div class="val">3</div><div class="lbl">Schedulers</div></div>
      <div class="stat-chip"><div class="val">0</div><div class="lbl">Future Peeks</div></div>
      <div class="stat-chip"><div class="val">4–5h</div><div class="lbl">Time Spent</div></div>
    </div>
  </div>

  <!-- 2 · Problem -->
  <div class="slide" id="slide-2">
    <h2>The Problem</h2>
    <div class="sub">Three objectives from the spec, plus one hard constraint that shapes every design decision</div>
    <ul>
      <li>
        <div class="li-title">Serve all requests eventually</div>
        <div class="li-sub">Every passenger must be picked up and dropped off — no one waits indefinitely. This is a correctness floor, not an optimization goal. The simulation cannot terminate until all passengers are served.</div>
      </li>
      <li>
        <div class="li-title">Minimize total_time = wait_time + travel_time</div>
        <div class="li-sub">Unlike a traditional elevator where passengers only press Up or Down, destination dispatch means both floors are known at request time. That gives the scheduler full information to make a smarter assignment decision upfront rather than figuring it out on the fly.</div>
      </li>
      <li>
        <div class="li-title">Honor elevator constraints: capacity and direction logic</div>
        <div class="li-sub">Elevators have a maximum passenger count that must be respected at boarding time. Movement follows the SCAN algorithm — an elevator commits to its current direction and finishes the sweep before reversing, rather than thrashing back and forth.</div>
      </li>
      <li>
        <div class="li-title">No peeking at future requests</div>
        <div class="li-sub">The simulation only sees requests as they arrive in real time. Each tick only admits requests whose timestamp matches the current tick — even if the input file has future entries already loaded in memory, they are never read ahead of schedule.</div>
      </li>
    </ul>
  </div>

  <!-- 3 · Architecture -->
  <div class="slide" id="slide-3">
    <h2>Architecture</h2>
    <div class="sub">Four files, each with a single responsibility — they communicate through two shared sets on the Elevator object: pickup_floors and dropoff_floors</div>
    <div class="two-col">
      <div class="card">
        <h3>models.py — Data &amp; Physics</h3>
        <p>Defines the core data model. PassengerRequest is frozen — it never changes after submission. PassengerState tracks the mutable journey (assigned, boarded, dropped off). Elevator owns the SCAN movement logic and capacity. The Direction enum drives which targets are considered next.</p>
      </div>
      <div class="card">
        <h3>scheduler.py — Assignment</h3>
        <p>Answers one question: which elevator should serve this passenger? Defined as a Protocol so any strategy can be swapped in. Three implementations: NearestCar (distance + workload), StrictNearest (distance only), and RoundRobin (rotation). All produce the same output — an elevator ID.</p>
      </div>
      <div class="card">
        <h3>simulation.py — Engine</h3>
        <p>Owns the main tick loop and coordinates everything. _assign_new_requests admits passengers and calls the scheduler. _process_stops handles boarding and alighting each tick. Also writes the positions log and summary stats to disk when the simulation ends.</p>
      </div>
      <div class="card">
        <h3>main.py — CLI</h3>
        <p>Thin entrypoint that wires everything together. Accepts --scheduler, --num-elevators, --num-floors, and --capacity as arguments. Loads the CSV, constructs the simulation, runs it, and writes outputs to the output/ directory.</p>
      </div>
    </div>
  </div>

  <!-- 4 · Tick Loop -->
  <div class="slide" id="slide-4">
    <h2>The Simulation Loop</h2>
    <div class="sub">One tick = one floor of travel = one time unit</div>
    <div class="timeline">
      <div class="tl-item">
        <div class="tl-node">1</div>
        <div class="tl-body">
          <div class="tl-title">Record positions</div>
          <div class="tl-sub">Snapshot every elevator's current floor before anything moves. This ensures the log captures where elevators actually were at time T, not where they ended up after moving — which matters for accurate replay and debugging.</div>
        </div>
      </div>
      <div class="tl-item">
        <div class="tl-node">2</div>
        <div class="tl-body">
          <div class="tl-title">Assign new requests</div>
          <div class="tl-sub">Scan the request list for any passenger whose arrival time equals the current tick. Each one is handed to the scheduler, which picks an elevator and locks in the assignment. The passenger's source floor is immediately added to that elevator's pickup targets. Requests beyond the current tick are never read — this is how no-peek is enforced.</div>
        </div>
      </div>
      <div class="tl-item">
        <div class="tl-node">3</div>
        <div class="tl-body">
          <div class="tl-title">Process stops — dropoffs first, then pickups</div>
          <div class="tl-sub">Every elevator checks its current floor. First, anyone whose destination matches alights and frees their seat. Then, waiting passengers at that floor board in arrival order, up to capacity. Dropoffs run before pickups deliberately — so a seat freed this tick is immediately available to a new boarder in the same tick, rather than making them wait another full loop.</div>
        </div>
      </div>
      <div class="tl-item">
        <div class="tl-node">4</div>
        <div class="tl-body">
          <div class="tl-title">Move elevators</div>
          <div class="tl-sub">Each elevator advances one floor toward its next SCAN target. Before moving, the simulation checks if both conditions are true: all passengers have been dropped off, and no future requests remain. Only when both are satisfied does the loop terminate — one condition alone is not enough.</div>
        </div>
      </div>
    </div>
    <div class="code" style="margin-top:18px;">
      <div class="code-bar"><div class="code-dot"></div><div class="code-dot"></div><div class="code-dot"></div></div>
      <div class="code-inner">while not all_done:<br>&nbsp;&nbsp;record() → assign() → process_stops() → move()</div>
    </div>
  </div>

  <!-- 5 · Schedulers -->
  <div class="slide" id="slide-5">
    <h2>Schedulers</h2>
    <div class="sub">All three answer one question: which elevator do we send for this request? — Multiple schedulers were listed as a bonus item in the spec; all three are implemented and compared via <span class="mono">compare_schedulers.py</span></div>
    <ul>
      <li>
        <div class="li-title">nearest <span class="tag">default</span></div>
        <div class="code" style="margin-top:10px;">
          <div class="code-bar"><div class="code-dot"></div><div class="code-dot"></div><div class="code-dot"></div></div>
          <div class="code-inner">score = distance_to_pickup + (pending_stops × 2)  →  lowest wins</div>
        </div>
        <div class="li-sub">The workload penalty (×2) stops the closest elevator from being assigned indefinitely — without it, a nearby elevator with five pending stops would always win over an idle one slightly further away, even though the idle one would arrive first. The multiplier makes workload count enough to actually change the decision.</div>
      </li>
      <li>
        <div class="li-title">strict_nearest</div>
        <div class="code" style="margin-top:10px;">
          <div class="code-bar"><div class="code-dot"></div><div class="code-dot"></div><div class="code-dot"></div></div>
          <div class="code-inner">min(elevators, key=lambda e: abs(e.floor - request.source))</div>
        </div>
        <div class="li-sub">Pure distance — no workload awareness. Simple and fast, but can pile requests onto one elevator when multiple arrive simultaneously near the same car, while others sit idle across the building. Useful as a baseline to measure how much the workload penalty actually helps.</div>
      </li>
      <li>
        <div class="li-title">round_robin</div>
        <div class="code" style="margin-top:10px;">
          <div class="code-bar"><div class="code-dot"></div><div class="code-dot"></div><div class="code-dot"></div></div>
          <div class="code-inner">elevators[counter % N];  counter += 1</div>
        </div>
        <div class="li-sub">Ignores position entirely and rotates assignments in order. No single elevator ever gets more than its share of requests, but it may send an elevator from floor 60 to pick up someone on floor 1 when another car is already there. Acts as a fairness lower bound — if nearest-car only beats this by a small margin, the spatial heuristic isn't adding much value.</div>
      </li>
    </ul>
  </div>

  <!-- 6 · SCAN -->
  <div class="slide" id="slide-6">
    <h2>SCAN — Elevator Movement</h2>
    <div class="sub">Commit to the current direction before reversing — like a scanner head sweeping across a page</div>
    <div class="two-col">
      <div>
        <ul>
          <li>
            <div class="li-title">Going UP</div>
            <div class="li-sub">Pick the lowest target floor that is at or above the current position — keep moving up, serve the next stop in line, never reverse early</div>
          </li>
          <li>
            <div class="li-title">Going DOWN</div>
            <div class="li-sub">Pick the highest target floor that is at or below the current position — mirror image of going up, commit to the downward sweep until it's exhausted</div>
          </li>
          <li>
            <div class="li-title">Idle</div>
            <div class="li-sub">No direction set yet — pick the nearest target by absolute distance to get moving as quickly as possible</div>
          </li>
        </ul>
        <div class="code" style="margin-top:14px;">
          <div class="code-bar"><div class="code-dot"></div><div class="code-dot"></div><div class="code-dot"></div></div>
          <div class="code-inner">if UP:&nbsp;&nbsp; return min(targets ≥ current)<br>if DOWN: return max(targets ≤ current)<br>else:&nbsp;&nbsp;&nbsp; return nearest(targets)</div>
        </div>
      </div>
      <div class="card">
        <h3>Why SCAN?</h3>
        <p>Always-nearest causes thrashing — if there are targets both above and below, the elevator reverses direction every single tick and never makes progress in either direction.<br><br>
        SCAN commits to one direction until it runs out of targets that way, then reverses. Everyone traveling in the same direction gets served in one sweep, which is both more efficient and prevents any floor from being skipped indefinitely.</p>
      </div>
    </div>
  </div>

  <!-- 7 · Trade-offs -->
  <div class="slide" id="slide-7">
    <h2>Trade-offs &amp; What I'd Improve</h2>
    <ul>
      <li>
        <div class="li-title">No physics — 1 tick = 1 floor, always</div>
        <div class="li-sub">This is the biggest simplification. In reality an elevator accelerates, cruises, then decelerates — it cannot stop at every floor at full speed, and door open/close takes real time. In a production system I'd model distinct states: accelerating, cruising, decelerating, door open, boarding, door close. This changes scheduling decisions significantly because stopping at an intermediate floor has a real cost, whereas passing through it does not.</div>
      </li>
      <li>
        <div class="li-title">Scheduler ignores capacity at assignment time</div>
        <div class="li-sub">The scheduler picks an elevator based on distance and workload, but never checks whether it will actually have room when it arrives. A full elevator can be assigned a new passenger, travel all the way to their floor, and then fail to board them — capacity is only enforced at pickup time. The fix is non-trivial: current load isn't reliable because passengers may drop off before arrival, so the real solution is to project future load at estimated arrival time.</div>
      </li>
      <li>
        <div class="li-title">No dynamic reassignment</div>
        <div class="li-sub">Once a passenger is assigned to an elevator, that assignment is permanent — even if a much better elevator becomes available nearby two ticks later. A smarter system would re-evaluate assignments each tick and switch a passenger to a closer elevator if the time savings exceed a threshold, without causing churn from constant reassignments.</div>
      </li>
      <li>
        <div class="li-title">No zone-based routing</div>
        <div class="li-sub">Every elevator serves every floor, which is wasteful in a tall building. If a passenger on floor 2 is assigned to an elevator sitting on floor 58, it travels the full height just for one pickup. A real building would pin elevators to floor ranges — low, mid, high — with a dedicated express bank for the top floors, dramatically reducing average travel distance.</div>
      </li>
      <li>
        <div class="li-title">No stress testing</div>
        <div class="li-sub">The test suite verifies basic correctness on small inputs but there are no stress tests — high passenger volume, tight capacity limits, or adversarial patterns like all passengers requesting the same floor simultaneously. These are exactly the conditions that expose edge cases in scheduling logic, and the capacity deadlock bug discovered during development is a direct example of what stress tests would have caught earlier.</div>
      </li>
    </ul>
  </div>

</div><!-- /slides-layer -->

<!-- ── Simulation layer (slide 8) ── -->
<div id="sim-layer">
  <header>
    <div style="display:flex;align-items:center;">
      <button id="back-btn" onclick="prevSlide()">← Slides</button>
      <h1 id="page-title">Elevator Simulation — Live Demo</h1>
    </div>
    <div id="time-badge">T = 0</div>
  </header>
  <nav>
    <button class="active" onclick="switchTab('building',this)">Building</button>
    <button onclick="switchTab('passengers',this)">Passengers</button>
    <button onclick="switchTab('timeline',this)">Timeline</button>
    <button onclick="switchTab('stats',this)">Stats</button>
  </nav>
  <main>
    <div id="view-building" class="view active">
      <div id="building-wrap">
        <div id="floor-labels"></div>
        <div id="shafts"></div>
      </div>
      <div id="building-info">
        <div class="icard"><h3>Elevators</h3><div id="elev-details"></div></div>
        <div class="icard">
          <h3>Legend</h3>
          <div style="font-size:.74rem;line-height:2.1;color:var(--muted)">
            <span style="color:var(--waiting)">●</span> Pickup floor<br>
            <span style="color:var(--done)">●</span> Dropoff floor<br>
            ↑ Up · ↓ Down · — Idle
          </div>
        </div>
        <div class="icard grow"><h3>Passengers</h3><div id="inline-pax-list"></div></div>
      </div>
    </div>
    <div id="view-passengers" class="view"></div>
    <div id="view-timeline" class="view"><div id="tl-wrap"><svg id="tl-svg"></svg></div></div>
    <div id="view-stats" class="view">
      <div id="stat-bigs"></div>
      <div id="bars-wrap"><h3>Per-passenger breakdown</h3><div id="bars-inner"></div></div>
    </div>
  </main>
  <footer>
    <button class="btn sec" onclick="restart()">↺</button>
    <button class="btn sec" onclick="stepBack()">◀</button>
    <button class="btn" id="play-btn" onclick="togglePlay()">▶ Play</button>
    <button class="btn sec" onclick="stepForward()">▶</button>
    <input type="range" id="scrubber" min="0" value="0" step="1">
    <span class="ft-label" id="tick-info">0 / 0</span>
    <span class="ft-label">Speed:</span>
    <select id="speed-sel" onchange="intervalMs=+this.value">
      <option value="700">0.5×</option>
      <option value="350" selected>1×</option>
      <option value="175">2×</option>
      <option value="70">5×</option>
      <option value="16">Max</option>
    </select>
  </footer>
</div>

<script>
/* ── Presentation ── */
let currentSlide = 1;
const TOTAL = 8;

function showSlide(n) {
  n = Math.max(1, Math.min(TOTAL, n));
  const sl = document.getElementById('slides-layer');
  const sm = document.getElementById('sim-layer');
  const nav = document.getElementById('pres-nav');
  const pct = (n / TOTAL * 100).toFixed(1);
  document.getElementById('progress').style.width = pct + '%';

  if (n < TOTAL) {
    sl.classList.remove('hidden');
    sm.classList.remove('visible');
    nav.classList.remove('hidden');
    document.querySelectorAll('.slide').forEach(function(s) {
      s.classList.remove('active','visible');
    });
    var slide = document.getElementById('slide-' + n);
    slide.classList.add('active');
    requestAnimationFrame(function() {
      requestAnimationFrame(function() { slide.classList.add('visible'); });
    });
  } else {
    sl.classList.add('hidden');
    sm.classList.add('visible');
    nav.classList.add('hidden');
  }

  document.getElementById('slide-counter').textContent = n + ' / ' + TOTAL;
  document.getElementById('btn-prev').disabled = (n <= 1);
  document.getElementById('btn-next').disabled = (n >= TOTAL);
  currentSlide = n;
}

function nextSlide() { showSlide(currentSlide + 1); }
function prevSlide() { showSlide(currentSlide - 1); }

document.addEventListener('keydown', function(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') { e.preventDefault(); nextSlide(); }
  if (e.key === 'ArrowLeft'  || e.key === 'PageUp')  { e.preventDefault(); prevSlide(); }
});

/* Trigger initial visible animation */
requestAnimationFrame(function() {
  requestAnimationFrame(function() {
    var s = document.getElementById('slide-1');
    if (s) s.classList.add('visible');
  });
});

/* ── Simulation ── */
const DATA     = __DATA_JSON__;
const snaps    = DATA.snapshots;
const CFG      = DATA.config;
const N_FLOORS = CFG.num_floors;
const N_ELEVS  = CFG.num_elevators;
const PAX_IDS  = Object.keys(snaps[0].passengers).sort();
const COLORS   = ['#6366f1','#22d3ee','#f43f5e','#f59e0b','#a78bfa','#34d399'];
const SHAFT_H  = 540;

let tick = 0, playing = false, intervalMs = 350, timer = null;

document.getElementById('page-title').textContent =
  'Elevator Simulation — ' + CFG.scheduler + ' · ' + N_ELEVS + ' elevators · ' + N_FLOORS + ' floors';
document.getElementById('scrubber').max = snaps.length - 1;

function carH() { return Math.max(22, Math.floor(SHAFT_H / N_FLOORS) - 2); }
function floorToTop(f) { return (1 - (f - 1) / (N_FLOORS - 1)) * (SHAFT_H - carH()); }

function buildBuilding() {
  var lbl = document.getElementById('floor-labels');
  lbl.style.height = (SHAFT_H + 28) + 'px';
  var step = N_FLOORS <= 10 ? 1 : N_FLOORS <= 20 ? 2 : N_FLOORS <= 40 ? 5 : 10;
  for (var f = 1; f <= N_FLOORS; f++) {
    if (f !== 1 && f !== N_FLOORS && f % step !== 0) continue;
    var el = document.createElement('div');
    el.className = 'fl-label'; el.textContent = f;
    el.style.top = (28 + floorToTop(f) + carH() / 2 - 6) + 'px';
    lbl.appendChild(el);
  }
  var shafts = document.getElementById('shafts');
  shafts.style.height = (SHAFT_H + 28) + 'px';
  for (var ei = 0; ei < N_ELEVS; ei++) {
    var shaft = document.createElement('div');
    shaft.className = 'shaft'; shaft.id = 'shaft' + ei; shaft.style.height = '100%';
    for (var f2 = 1; f2 <= N_FLOORS; f2++) {
      var line = document.createElement('div');
      line.className = 'floor-line';
      line.style.top = (28 + floorToTop(f2) + carH()) + 'px';
      shaft.appendChild(line);
    }
    var hdr = document.createElement('div');
    hdr.className = 'shaft-hdr'; hdr.textContent = 'E' + ei;
    hdr.style.color = COLORS[ei % COLORS.length];
    shaft.appendChild(hdr);
    var car = document.createElement('div');
    car.className = 'elev-car'; car.id = 'car' + ei;
    car.style.background = COLORS[ei % COLORS.length];
    car.style.height = carH() + 'px';
    shaft.appendChild(car);
    shafts.appendChild(shaft);
  }
}

function buildInlinePaxList() {
  var list = document.getElementById('inline-pax-list');
  var last = snaps[snaps.length - 1].passengers;
  PAX_IDS.forEach(function(pid) {
    var p = last[pid];
    var row = document.createElement('div');
    row.id = 'irow-' + pid;
    row.className = 'ipax-row pending';
    row.innerHTML =
      '<span class="ipax-name">' + pid + '</span>' +
      '<span class="ipax-route">F' + p.source + ' → F' + p.dest + ' · T=' + snaps[0].passengers[pid].request_time + '</span>' +
      '<span class="ipax-st pending" id="ist-' + pid + '">pending</span>';
    list.appendChild(row);
  });
}

function updateInlinePax(snap) {
  PAX_IDS.forEach(function(pid) {
    var p = snap.passengers[pid];
    var row = document.getElementById('irow-' + pid);
    var st  = document.getElementById('ist-' + pid);
    row.className = 'ipax-row ' + p.status;
    st.className  = 'ipax-st ' + p.status;
    st.textContent = p.status;
  });
}

function buildPassengerCards() {
  var view = document.getElementById('view-passengers');
  var last = snaps[snaps.length - 1].passengers;
  PAX_IDS.forEach(function(pid) {
    var p = last[pid];
    var card = document.createElement('div');
    card.id = 'pcard-' + pid; card.className = 'pax-card pending';
    card.innerHTML = '<div class="pax-id">' + pid + '</div>' +
      '<div class="pax-route">Floor ' + p.source + ' → ' + p.dest + '</div>' +
      '<span class="pax-badge pending" id="pbadge-' + pid + '">pending</span>' +
      '<div class="pax-meta" id="pmeta-' + pid + '"></div>';
    view.appendChild(card);
  });
}

function render(t) {
  var snap = snaps[t];
  document.getElementById('time-badge').textContent = 'T = ' + snap.time;
  document.getElementById('tick-info').textContent = t + ' / ' + (snaps.length - 1);
  document.getElementById('scrubber').value = t;
  renderBuilding(snap); renderPassengers(snap);
  var active = document.querySelector('.view.active').id;
  if (active === 'view-timeline') renderTimeline(t);
  if (active === 'view-stats')    renderStats(t);
}

function renderBuilding(snap) {
  document.querySelectorAll('.floor-dot').forEach(function(d) { d.remove(); });
  snap.elevators.forEach(function(e) {
    var car = document.getElementById('car' + e.id);
    car.style.top = (28 + floorToTop(e.floor)) + 'px';
    var dir = e.direction === 'UP' ? '↑' : e.direction === 'DOWN' ? '↓' : '—';
    car.innerHTML = '<span>' + dir + ' Fl.' + e.floor + '</span><span>' + e.onboard.length + 'p</span>';
    var shaft = document.getElementById('shaft' + e.id);
    function placeDot(floor, cls) {
      var dot = document.createElement('div');
      dot.className = 'floor-dot ' + cls;
      dot.style.top = (28 + floorToTop(floor) + carH() / 2 - 3.5) + 'px';
      shaft.appendChild(dot);
    }
    e.pickup_targets.forEach(function(f) { placeDot(f, 'pickup'); });
    e.dropoff_targets.forEach(function(f) { placeDot(f, 'dropoff'); });
  });
  document.getElementById('elev-details').innerHTML = snap.elevators.map(function(e) {
    var dir = e.direction === 'UP' ? '↑' : e.direction === 'DOWN' ? '↓' : '—';
    var c = COLORS[e.id % COLORS.length];
    return '<div class="elev-row"><div class="elev-dot" style="background:' + c + '"></div><div>' +
      '<div>Floor <strong>' + e.floor + '</strong> ' + dir + '</div>' +
      '<div class="elev-sub">' + (e.onboard.length ? e.onboard.join(', ') : 'empty') + '</div>' +
      (e.pickup_targets.length  ? '<div class="elev-sub">Pickup: ' + e.pickup_targets.join(', ') + '</div>' : '') +
      (e.dropoff_targets.length ? '<div class="elev-sub">Drop: '   + e.dropoff_targets.join(', ') + '</div>' : '') +
      '</div></div>';
  }).join('');
  updateInlinePax(snap);
}

function renderPassengers(snap) {
  PAX_IDS.forEach(function(pid) {
    var p = snap.passengers[pid];
    document.getElementById('pcard-' + pid).className = 'pax-card ' + p.status;
    var badge = document.getElementById('pbadge-' + pid);
    badge.className = 'pax-badge ' + p.status; badge.textContent = p.status;
    var m = 'Requested T=' + p.request_time;
    if (p.assigned !== null)     m += '<br>Elevator: E' + p.assigned;
    if (p.pickup_time !== null)  m += '<br>Boarded T=' + p.pickup_time + ' (waited ' + (p.pickup_time - p.request_time) + ')';
    if (p.dropoff_time !== null) m += '<br>Arrived T=' + p.dropoff_time + ' (rode ' + (p.dropoff_time - p.pickup_time) + ')';
    document.getElementById('pmeta-' + pid).innerHTML = m;
  });
}

function renderTimeline(upToTick) {
  var last = snaps[snaps.length - 1];
  var maxTime = last.time;
  var curTime = snaps[Math.min(upToTick, snaps.length - 1)].time;
  var wrap = document.getElementById('tl-wrap');
  var W = Math.max(600, wrap.clientWidth - 30);
  var rowH = 32, padL = 90, padR = 16, padT = 28, padB = 36;
  var H = padT + PAX_IDS.length * rowH + padB;
  var tx = function(t) { return padL + (t / (maxTime || 1)) * (W - padL - padR); };
  var s = '<svg xmlns="http://www.w3.org/2000/svg" width="' + W + '" height="' + H + '">';
  s += '<line x1="' + padL + '" y1="' + padT + '" x2="' + (W-padR) + '" y2="' + padT + '" stroke="rgba(255,255,255,.07)" stroke-width="1"/>';
  var step = Math.max(1, Math.ceil(maxTime / 12));
  for (var t = 0; t <= maxTime; t += step) {
    var x = tx(t);
    s += '<line x1="' + x + '" y1="' + padT + '" x2="' + x + '" y2="' + (H-padB) + '" stroke="rgba(255,255,255,.04)" stroke-width="1"/>';
    s += '<text x="' + x + '" y="' + (padT-5) + '" text-anchor="middle" fill="#6b6b8f" font-size="10">' + t + '</text>';
  }
  s += '<line x1="' + tx(curTime) + '" y1="' + padT + '" x2="' + tx(curTime) + '" y2="' + (H-padB) + '" stroke="#6366f1" stroke-width="2" stroke-dasharray="4,3"/>';
  PAX_IDS.forEach(function(pid, i) {
    var p = last.passengers[pid];
    var mid = padT + i * rowH + rowH / 2;
    s += '<text x="' + (padL-6) + '" y="' + (mid+4) + '" text-anchor="end" fill="#6b6b8f" font-size="11">' + pid + '</text>';
    if (p.pickup_time !== null) {
      s += '<rect x="' + tx(p.request_time) + '" y="' + (mid-7) + '" width="' + Math.max(2,tx(p.pickup_time)-tx(p.request_time)) + '" height="14" rx="3" fill="#f57c00" opacity=".9"/>';
    } else {
      s += '<rect x="' + tx(p.request_time) + '" y="' + (mid-7) + '" width="' + Math.max(2,tx(curTime)-tx(p.request_time)) + '" height="14" rx="3" fill="#f57c00" opacity=".35"/>';
    }
    if (p.pickup_time !== null && p.dropoff_time !== null) {
      s += '<rect x="' + tx(p.pickup_time) + '" y="' + (mid-7) + '" width="' + Math.max(2,tx(p.dropoff_time)-tx(p.pickup_time)) + '" height="14" rx="3" fill="#1976d2" opacity=".9"/>';
    } else if (p.pickup_time !== null) {
      s += '<rect x="' + tx(p.pickup_time) + '" y="' + (mid-7) + '" width="' + Math.max(2,tx(curTime)-tx(p.pickup_time)) + '" height="14" rx="3" fill="#1976d2" opacity=".35"/>';
    }
  });
  var ly = H - padB + 14;
  s += '<rect x="' + padL + '" y="' + ly + '" width="11" height="11" rx="2" fill="#f57c00"/>' +
       '<text x="' + (padL+15) + '" y="' + (ly+9) + '" fill="#6b6b8f" font-size="11">Waiting</text>' +
       '<rect x="' + (padL+75) + '" y="' + ly + '" width="11" height="11" rx="2" fill="#1976d2"/>' +
       '<text x="' + (padL+90) + '" y="' + (ly+9) + '" fill="#6b6b8f" font-size="11">Riding</text>' +
       '<line x1="' + (padL+150) + '" y1="' + ly + '" x2="' + (padL+150) + '" y2="' + (ly+11) + '" stroke="#6366f1" stroke-width="2" stroke-dasharray="4,3"/>' +
       '<text x="' + (padL+156) + '" y="' + (ly+9) + '" fill="#6b6b8f" font-size="11">Now</text>';
  s += '</svg>';
  wrap.innerHTML = s;
}

function renderStats(upToTick) {
  var last = snaps[snaps.length - 1];
  var done = Object.values(last.passengers).filter(function(p) { return p.dropoff_time !== null; });
  var bigs = document.getElementById('stat-bigs');
  if (!done.length) { bigs.innerHTML = '<div class="stat-big"><div class="stat-lbl">No passengers done yet</div></div>'; return; }
  var waits  = done.map(function(p) { return p.pickup_time - p.request_time; });
  var totals = done.map(function(p) { return p.dropoff_time - p.request_time; });
  var avg = function(a) { return (a.reduce(function(s,v){return s+v;},0)/a.length).toFixed(1); };
  bigs.innerHTML = [
    ['Avg Wait',avg(waits)],['Max Wait',Math.max.apply(null,waits)],
    ['Avg Total',avg(totals)],['Max Total',Math.max.apply(null,totals)],
    ['Served',done.length],['Finish T',last.time],
  ].map(function(x){return '<div class="stat-big"><div class="stat-val">'+x[1]+'</div><div class="stat-lbl">'+x[0]+'</div></div>';}).join('');
  var maxT = Math.max.apply(null,totals.concat([1]));
  document.getElementById('bars-inner').innerHTML = PAX_IDS.map(function(pid) {
    var p = last.passengers[pid];
    if (p.pickup_time === null) return '<div class="bar-row"><span class="bar-lbl">'+pid+'</span><span style="font-size:.7rem;color:var(--muted)">waiting…</span></div>';
    var w = p.pickup_time - p.request_time;
    var r = p.dropoff_time !== null ? p.dropoff_time - p.pickup_time : 0;
    var wp = (w/maxT*100).toFixed(1); var rp = (r/maxT*100).toFixed(1);
    return '<div class="bar-row"><span class="bar-lbl">'+pid+'</span>' +
      '<div class="bar-track"><div class="bar-wait" style="width:'+wp+'%"></div>' +
      '<div class="bar-ride" style="left:'+wp+'%;width:'+rp+'%"></div></div>' +
      '<span class="bar-num">'+(w+r)+'</span></div>';
  }).join('');
}

function togglePlay() {
  playing = !playing;
  document.getElementById('play-btn').textContent = playing ? '⏸ Pause' : '▶ Play';
  if (playing) { if (tick >= snaps.length-1) tick=0; stepSim(); }
  else clearTimeout(timer);
}
function stepSim() {
  if (!playing) return;
  if (tick < snaps.length-1) { tick++; render(tick); timer=setTimeout(stepSim,intervalMs); }
  else { playing=false; document.getElementById('play-btn').textContent='▶ Play'; }
}
function restart() { clearTimeout(timer); playing=false; document.getElementById('play-btn').textContent='▶ Play'; tick=0; render(0); }
function stepForward() { clearTimeout(timer); playing=false; document.getElementById('play-btn').textContent='▶ Play'; if(tick<snaps.length-1){tick++;render(tick);} }
function stepBack()    { clearTimeout(timer); playing=false; document.getElementById('play-btn').textContent='▶ Play'; if(tick>0){tick--;render(tick);} }
document.getElementById('scrubber').addEventListener('input', function(e) {
  clearTimeout(timer); playing=false; document.getElementById('play-btn').textContent='▶ Play';
  tick=+e.target.value; render(tick);
});
function switchTab(name, btn) {
  document.querySelectorAll('.view').forEach(function(v){v.classList.remove('active');});
  document.querySelectorAll('#sim-layer nav button').forEach(function(b){b.classList.remove('active');});
  document.getElementById('view-'+name).classList.add('active');
  btn.classList.add('active');
  if (name==='timeline') renderTimeline(tick);
  if (name==='stats')    renderStats(tick);
}

buildBuilding();
buildPassengerCards();
buildInlinePaxList();
render(0);
</script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate interview presentation HTML")
    p.add_argument("--input",         default="simple_requests.csv")
    p.add_argument("--num-elevators", type=int, default=2)
    p.add_argument("--num-floors",    type=int, default=10)
    p.add_argument("--capacity",      type=int, default=4)
    p.add_argument("--scheduler",     default="nearest",
                   choices=["nearest", "strict_nearest", "round_robin"])
    p.add_argument("--output",        default="docs/index.html")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    requests = load_requests_from_csv(args.input)
    config = SimulationConfig(
        num_elevators=args.num_elevators,
        num_floors=args.num_floors,
        max_passengers_per_elevator=args.capacity,
    )
    sim = CapturingSimulation(config, scheduler=create_scheduler(args.scheduler))
    sim.run(requests)

    data = {
        "snapshots": sim.snapshots,
        "config": {
            "num_elevators": args.num_elevators,
            "num_floors": args.num_floors,
            "scheduler": args.scheduler,
        },
    }
    html = HTML.replace("__DATA_JSON__", json.dumps(data, separators=(",", ":")))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote: {out}")
    print(f"Open:  {out.resolve()}")


if __name__ == "__main__":
    main()
