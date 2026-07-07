# sw_montecarlo — Monte Carlo DAA Evaluation

Monte Carlo analysis framework for evaluating the Detect-and-Avoid (DAA) conflict
prediction system across thousands of randomised encounter scenarios.

## Overview

The pipeline for each encounter:

1. **Trajectory generation** — random encounter parameters are sampled and fed to
   `sw_trajectory_generator` to produce synthetic ownship + intruder tracks.
2. **Vision simulation** — the true trajectories are converted to azimuth / elevation /
   range measurements simulating a forward-looking camera.
3. **UKF tracking** — an Unscented Kalman Filter (from `sw_conflict_prediction`)
   recovers the intruder's state and covariance from the noisy vision measurements.
4. **1σ conflict assessment** — at every time step, the 1σ-inflated cylindrical
   distance is computed at a 60 s lookahead.  A collision is flagged when this
   distance drops below 1.0.
5. **Ground-truth comparison** — the noise-free trajectories are checked for an
   actual cylinder violation.  The time of first penetration is recorded so that
   **alert lead time** can be computed.
6. **Lead-time classification** — an alert is only meaningful if it fires with
   enough advance warning.  The analysis script classifies each encounter into
   TP / FP / TN / FN using configurable time-zone boundaries (see below).

## Quick Start

```bash
# From the sw/ directory, activate the virtual environment
.venv\Scripts\Activate.ps1   # Windows

# Run 100 encounters on 4 workers (quick smoke test)
python sw_montecarlo/scripts/run_montecarlo.py -n 100 -w 4 -o mc_results.csv

# Full run (e.g. 5000 encounters)
python sw_montecarlo/scripts/run_montecarlo.py -n 5000 -w 8 -o mc_results.csv

# Analyze
python sw_montecarlo/scripts/analyze_results.py -i mc_results.csv --plots
```

## Scripts

| Script | Purpose |
|--------|---------|
| `pipeline.py` | Single-encounter in-memory pipeline (generate → vision → UKF → 1σ detect) |
| `run_montecarlo.py` | Parallel orchestration, random sampling, incremental CSV output |
| `analyze_results.py` | Confusion matrix, breakdown analysis, optional plots |

## CLI Reference

### run_montecarlo.py

```
-n, --num-encounters   Total encounters to simulate (default: 1000)
-w, --workers          Parallel processes (default: CPU count - 1)
-o, --output           Output CSV path (default: montecarlo_results.csv)
--estimator            UKF model: cv, ca, cab (default: cv)
--lookahead            Conflict lookahead in seconds (default: 60)
--cyl-height           Protection cylinder height in ft (default: 1000)
--cyl-diameter         Protection cylinder diameter in ft (default: 2000)
--master-seed          RNG seed for reproducibility (default: 42)
--resume               Resume from existing output file
```

### analyze_results.py

```
-i, --input       Path to results CSV
--plots           Generate PNG plots
--plot-dir        Output directory for plots (default: figures/)
--dead-zone       Dead-zone boundary in seconds (default: 15)
--lead-margin     Tolerance above lookahead in seconds (default: 5)
```

## Collision Criterion

A collision risk is flagged when, at any time step during the encounter, the
**1σ cylindrical distance** at a 60 s lookahead is **less than 1.0**.

The 1σ cylinder inflates the standard protection volume (1000 ft height ×
2000 ft diameter) by the projected ±1σ uncertainty from the UKF's covariance:
- **Radial** direction: √(uᵀ P_NE u), where u is the unit vector toward the intruder
- **Down** direction: √(P_dd)

This ensures that encounters where the intruder *might* be inside the protection
volume (given tracking uncertainty) are conservatively flagged.

## Output Columns

| Column | Description |
|--------|-------------|
| `daa_collision_detected` | True if 1σ distance < 1.0 at any time step |
| `daa_min_1sigma_cyl_dist` | Minimum 1σ cylindrical distance observed |
| `daa_detection_time_s` | First time (encounter clock) the distance dropped below 1.0 |
| `gt_collision` | Ground truth: did the intruder enter the real cylinder? |
| `gt_min_cyl_dist` | Ground truth minimum cylinder distance |
| `gt_collision_time_s` | Ground truth time of first cylinder penetration (NaN if none) |
| `daa_lead_time_s` | `gt_collision_time_s − daa_detection_time_s` (NaN if no collision or no alert) |

## Zone-Aware Classification

An alert is only as good as the time it buys you.  A late alert is penalised
just as harshly as no alert at all.  The analysis script classifies each
encounter by comparing the alert **lead time** against two boundaries:

```
|<-- Dead Zone -->|<-- Actionable Window -->|<-- Unrelated -->
0              dead_zone_s            lookahead + margin
```

| Ground truth | Alert lead time | Classification | Reasoning |
|---|---|---|---|
| Collision | `[dead_zone, lookahead + margin]` | **TP** | Detected the real collision in time |
| Collision | `< dead_zone` | **FN** | Alert too late to act on |
| Collision | `> lookahead + margin` | **FN** | Alert was about a phantom 1σ geometry, not the real collision |
| Collision | No alert | **FN** | Missed entirely |
| No collision | Alert | **FP** | False alarm |
| No collision | No alert | **TN** | Correct silence |

### Why lead time can exceed the lookahead

The 1σ-inflated cylinder is larger than the real protection cylinder.  The
alert may trigger when the inflated geometry predicts a breach within
`[t, t + lookahead]`, but the real collision on the non-inflated cylinder
happens much later.  These are not genuine detections of the actual event,
so they are classified as FN (sub-category: **unrelated**).

### Default boundaries

| Parameter | Default | Justification |
|---|---|---|
| `--dead-zone` | 15 s | Sensor latency (~2 s) + operator reaction (~4 s) + aircraft dynamics (~9 s) |
| `--lead-margin` | 5 s | Tolerance for discrete time sampling and minor 1σ stretching |
