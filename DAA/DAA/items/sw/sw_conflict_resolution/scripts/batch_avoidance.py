#!/usr/bin/env python3
"""
Batch driver for the avoidance simulator.

Runs ``avoidance_core.run_simulation`` for a range of integer seeds and
writes a CSV report with the per-encounter classification and the
key ground-truth / detection metrics.  Every row is keyed by ``seed``
so the corresponding encounter can be replayed visually with::

    python visualize_avoidance.py --seed <SEED>

Example::

    python batch_avoidance.py --n 200 --seed-start 0 --out batch_results.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from .avoidance_core import (
    run_simulation_from_spec,
    make_spec_from_seed,
    LOOKAHEAD_S,
    CYL_HEIGHT_M,
    CYL_DIAMETER_M,
    ALERT_THRESHOLD,
    DEFAULT_HYSTERESIS_S,
    DEFAULT_RETURN_HYSTERESIS_S,
    CLOSED_LOOP_OPEN, CLOSED_LOOP_ON_CONFLICT, CLOSED_LOOP_PERIODIC,
    DEFAULT_CLOSED_LOOP_MODE,
    DEFAULT_SWITCH_IMPROVE_RATIO,
)
from .candidate_trajectories import (
    default_generators,
    DEFAULT_LATERAL_SHIFT_RATIO,
    DEFAULT_VERTICAL_SHIFT_RATIO,
    DEFAULT_SLOWDOWN_RATIO,
    DEFAULT_MANEUVER_FAMILY,
    MANEUVER_FAMILY_SHIFTED,
    MANEUVER_FAMILY_MIN_BEARING,
    MANEUVER_FAMILY_MIN_CONST_BEARING,
    DEFAULT_K_XT_PER_M,
    DEFAULT_A_MAX_ALONG_M_S2,
    DEFAULT_RATE_MAX_AZIMUTH_RAD_S,
    DEFAULT_RATE_MAX_ELEVATION_RAD_S,
)


CSV_FIELDS = [
    'seed',
    'classification',          # TP / FP / TN / FN_M / FN_NM / ERROR
    'lowc_no_maneuver',
    'lowc_maneuver',
    'nontracked_lowc',         # 1 if any flown LoWC happened while the EKF had no active track on the intruder (not trackable: pre-init or post-FOV-loss timeout, e.g. closing from behind), else 0
    'triggered',
    'n_maneuvers',             # number of committed avoidance maneuvers in the flown sequence (1 = single escape; >1 = stacked closed-loop escapes)
    'maneuver_sequence',       # ';'-joined chronological names of committed avoidances, '' if none
    'first_maneuver_t_s',      # seconds from run start (times[0]) to the first committed maneuver, '' if none
    'steps',
    'min_d_baseline',          # min 1-sigma cylinder distance of the baseline (alert)
    'min_d_chosen',            # min 1-sigma cylinder distance of the chosen alternative
    'cyldist_min_no_maneuver', # ground-truth normalized cyl distance
    'cyldist_min_maneuver',
    # ICAO Annex 2 §3.2 encounter classification.  The core re-classifies
    # on every committed maneuver shift, so these columns carry one
    # ';'-separated entry per sub-encounter, in the same order as
    # ``maneuver_sequence`` (entry i matches commit i).  '' if no alert.
    'encounter_geometry',      # ';'-joined case geometries, one per commit (head_on / converging_right / overtaking / vertical_above / near_ceiling / ...)
    'crossing_angle_deg',      # ';'-joined crossing angles, one per commit
    'relative_bearing_deg',    # ';'-joined relative bearings, one per commit
    'own_gives_way',           # ';'-joined 1/0 right-of-way flags, one per commit
    'all_actions_compliant',   # 1 if every committed avoidance is ICAO-compliant, else 0, '' if no alert/no maneuver
    'wall_time_s',
    'error',
]


def _run_one(seed: int, *, lookahead, cyl_h, cyl_d,
             lateral_shift_ratio, alert_threshold,
             engage_hysteresis_s=DEFAULT_HYSTERESIS_S,
             return_hysteresis_s=DEFAULT_RETURN_HYSTERESIS_S,
             closed_loop_mode=DEFAULT_CLOSED_LOOP_MODE,
             periodic_interval_s=1.0,
             switch_improve_ratio=DEFAULT_SWITCH_IMPROVE_RATIO,
             vertical_shift_ratio=DEFAULT_VERTICAL_SHIFT_RATIO,
             slowdown_ratio=DEFAULT_SLOWDOWN_RATIO,
             maneuver_family=DEFAULT_MANEUVER_FAMILY,
             k_xt=DEFAULT_K_XT_PER_M,
             a_max_along=DEFAULT_A_MAX_ALONG_M_S2,
             rate_max_azimuth=DEFAULT_RATE_MAX_AZIMUTH_RAD_S,
             rate_max_elevation=DEFAULT_RATE_MAX_ELEVATION_RAD_S,
             v_max=1.0E12,
             v_min=0.0,
             el_min=-1.5708,
             el_max=1.5708,
             process_noise_std=None,
             process_noise_omega=None,
             ukf_model='cv',
             sigma_az=None, sigma_el=None, range_noise_fraction=None,
             finite_difference_init_velocity=False):
    """Run one simulation and return a dict matching ``CSV_FIELDS``."""
    row = {k: '' for k in CSV_FIELDS}
    row['seed'] = int(seed)
    t0 = time.perf_counter()
    try:
        spec = make_spec_from_seed(seed)
        sim_extra = {'ukf_model': ukf_model}
        if process_noise_std is not None:
            sim_extra['process_noise_std'] = float(process_noise_std)
        if process_noise_omega is not None:
            sim_extra['process_noise_omega'] = float(process_noise_omega)
        if any(v is not None for v in (sigma_az, sigma_el)):
            from .avoidance_core import _MEAS_NOISE as _DEF_MN
            sim_extra['meas_noise'] = {
                'azimuth_rad':   float(sigma_az    if sigma_az    is not None
                                       else _DEF_MN['azimuth_rad']),
                'elevation_rad': float(sigma_el    if sigma_el    is not None
                                       else _DEF_MN['elevation_rad']),
            }
        if range_noise_fraction is not None:
            sim_extra['range_noise_fraction'] = float(range_noise_fraction)
        if finite_difference_init_velocity:
            sim_extra['finite_difference_init_velocity'] = True
        r = run_simulation_from_spec(
            spec,
            generators=default_generators(
                lateral_shift_ratio=lateral_shift_ratio,
                vertical_shift_ratio=vertical_shift_ratio,
                slowdown_ratio=slowdown_ratio,
                maneuver_family=maneuver_family,
            ),
            lookahead=lookahead,
            cyl_h=cyl_h,
            cyl_d=cyl_d,
            alert_threshold=alert_threshold,
            engage_hysteresis_s=engage_hysteresis_s,
            return_hysteresis_s=return_hysteresis_s,
            closed_loop_mode=closed_loop_mode,
            periodic_interval_s=periodic_interval_s,
            switch_improve_ratio=switch_improve_ratio,
            a_max_along=a_max_along,
            rate_max_azimuth=rate_max_azimuth,
            rate_max_elevation=rate_max_elevation,
            v_max=v_max,
            v_min=v_min,
            el_min=el_min,
            el_max=el_max,
            k_xt=k_xt,
            record_history=False,
            **sim_extra,
        )
        triggered = (r.maneuver_idx >= 0)
        man_t = (float(r.times[r.maneuver_start] - r.times[0])
                 if triggered and r.maneuver_start >= 0 else float('nan'))
        # Chronological sequence of *committed* avoidance maneuvers,
        # straight from the state machine (one entry per commit).  Under
        # closed-loop stacking each entry is one escape composed onto the
        # active transform — including consecutive re-stacks of the same
        # maneuver type, since each materially changes the flown path
        # (the accumulated shift grows).  In open-loop this is normally a
        # single committed maneuver.  This is authoritative and matches
        # the number of ``active_xf`` transitions (the route-transform
        # plot), unlike a reconstruction from the flown candidate index
        # which would collapse same-type re-stacks into one.
        man_sequence = list(r.committed_names)
        d_base = r.d_candidates[:, 0]
        d_chosen = (r.d_candidates[:, r.maneuver_idx]
                    if triggered else np.empty(0))
        row.update({
            'classification':          r.classification,
            'lowc_no_maneuver':        int(r.lowc_no_maneuver),
            'lowc_maneuver':           int(r.lowc_maneuver),
            'nontracked_lowc':         int(r.nontracked_lowc),
            'triggered':               int(triggered),
            'n_maneuvers':             len(man_sequence),
            'maneuver_sequence':       ';'.join(man_sequence),
            'first_maneuver_t_s':      f'{man_t:.3f}' if np.isfinite(man_t) else '',
            'steps':                   int(len(r.times)),
            'min_d_baseline':          f'{float(d_base.min()):.4f}',
            'min_d_chosen':            (f'{float(d_chosen.min()):.4f}'
                                        if d_chosen.size else ''),
            'cyldist_min_no_maneuver': f'{r.cyldist_min_no_maneuver:.4f}',
            'cyldist_min_maneuver':    f'{r.cyldist_min_maneuver:.4f}',
        })
        # ICAO §3.2 classification (None if no alert ever fired).  The
        # core re-classifies on every commit, so ``r.encounters`` holds
        # one classification per committed maneuver shift.  Every
        # per-encounter column below is reported as a ';'-joined list with
        # one entry per sub-encounter, in commit order (entry i matches
        # ``maneuver_sequence`` entry i).
        if r.encounter is not None:
            ec = r.encounter
            encs = tuple(r.encounters) or (ec,)

            def _fnum(v, fmt='{:.2f}'):
                return fmt.format(v) if np.isfinite(v) else ''

            row.update({
                'encounter_geometry':      ';'.join(e.geometry for e in encs),
                'crossing_angle_deg':      ';'.join(
                    _fnum(e.crossing_angle_deg) for e in encs),
                'relative_bearing_deg':    ';'.join(
                    _fnum(e.relative_bearing_deg) for e in encs),
                'own_gives_way':           ';'.join(
                    str(int(e.own_gives_way)) for e in encs),
                # All committed avoidances compliant: 1 iff *every*
                # committed avoidance in the flown sequence is an
                # ICAO-compliant action of the classification taken at
                # *its own* commit (covers stacked closed-loop maneuvers,
                # each re-classified, not just the first escape).
                'all_actions_compliant': (
                    int(all(
                        a in (encs[i].compliant_actions if i < len(encs)
                              else ec.compliant_actions)
                        for i, a in enumerate(man_sequence)))
                    if man_sequence else ''),
            })
    except Exception as exc:                                      # noqa: BLE001
        row['classification'] = 'ERROR'
        row['error'] = f'{type(exc).__name__}: {exc}'
        # Keep stderr informative but compact.
        sys.stderr.write(f'[seed {seed}] ERROR: {row["error"]}\n')
        sys.stderr.write(traceback.format_exc())
    row['wall_time_s'] = f'{time.perf_counter() - t0:.3f}'
    return row


def _print_summary(rows):
    n = len(rows)
    counts = {k: 0 for k in ('TP', 'FP', 'TN', 'FN_M', 'FN_NM', 'ERROR')}
    for r in rows:
        counts[r['classification']] = counts.get(r['classification'], 0) + 1
    valid = n - counts['ERROR']
    # Classical FN is the sum of both maneuver modes.
    fn = counts['FN_M'] + counts['FN_NM']
    print('\n================ batch summary ================')
    print(f'  total simulations : {n}')
    print(f'  errors            : {counts["ERROR"]}')
    for k in ('TP', 'FP', 'TN'):
        pct = (100.0 * counts[k] / valid) if valid else 0.0
        print(f'  {k:<5}            : {counts[k]:5d}   ({pct:5.1f}%)')
    pct = (100.0 * fn / valid) if valid else 0.0
    print(f'  {"FN":<5}            : {fn:5d}   ({pct:5.1f}%)')
    for k in ('FN_M', 'FN_NM'):
        pct = (100.0 * counts[k] / valid) if valid else 0.0
        print(f'    {k:<7}        : {counts[k]:5d}   ({pct:5.1f}%)')
    if valid:
        tp, fp = counts['TP'], counts['FP']
        recall    = tp / (tp + fn) if (tp + fn) else float('nan')
        precision = tp / (tp + fp) if (tp + fp) else float('nan')
        print(f'  recall    (TP/(TP+FN)) = {recall:.3f}')
        print(f'  precision (TP/(TP+FP)) = {precision:.3f}')

    # ----- Maneuver-stacking stats (closed-loop) -------------------------
    # ``n_maneuvers`` counts the committed escapes in each run (1 = a
    # single maneuver; >1 = stacked closed-loop escapes).  Summarise the
    # distribution over the runs that actually maneuvered so the effect
    # of closed-loop stacking is visible at a glance.
    def _as_int(v, default=0):
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    n_man = [_as_int(r.get('n_maneuvers')) for r in rows]
    triggered_man = [m for m in n_man if m > 0]
    n_triggered = len(triggered_man)
    if n_triggered:
        stacked = sum(1 for m in triggered_man if m > 1)
        single  = n_triggered - stacked
        max_depth = max(triggered_man)
        mean_depth = sum(triggered_man) / n_triggered
        print('  --- maneuvers ---')
        print(f'  triggered (>=1 maneuver) : {n_triggered:5d}')
        pct_single  = 100.0 * single  / n_triggered
        pct_stacked = 100.0 * stacked / n_triggered
        print(f'    single  (1 maneuver)   : {single:5d}   ({pct_single:5.1f}%)')
        print(f'    stacked (>1 maneuver)  : {stacked:5d}   ({pct_stacked:5.1f}%)')
        print(f'  mean commits / triggered : {mean_depth:6.2f}')
        print(f'  max  commits in a run    : {max_depth:5d}')
        # Per-depth histogram (only depths that occur).
        depth_counts = {}
        for m in triggered_man:
            depth_counts[m] = depth_counts.get(m, 0) + 1
        for d in sorted(depth_counts):
            c = depth_counts[d]
            pct = 100.0 * c / n_triggered
            print(f'    {d:2d} maneuver(s)         : {c:5d}   ({pct:5.1f}%)')
    print('===============================================')


def main():
    p = argparse.ArgumentParser(
        description='Run N avoidance simulations and write a per-seed CSV report.')
    p.add_argument('--n', type=int, default=100,
                   help='Number of seeds to run (default: 100)')
    p.add_argument('--seed-start', type=int, default=0,
                   help='First seed (default: 0)')
    p.add_argument('--seed-step', type=int, default=1,
                   help='Increment between consecutive seeds (default: 1)')
    p.add_argument('--out', type=str, default='batch_results.csv',
                   help='Output CSV path (default: batch_results.csv)')
    p.add_argument('--workers', type=int, default=1,
                   help='Parallel processes (default: 1 = sequential). '
                        'Use >1 for multiprocessing.')
    p.add_argument('--lookahead',       type=float, default=LOOKAHEAD_S)
    p.add_argument('--cyl-h',           type=float, default=CYL_HEIGHT_M)
    p.add_argument('--cyl-d',           type=float, default=CYL_DIAMETER_M)
    p.add_argument('--lateral-shift-pct',  type=float,
                   default=DEFAULT_LATERAL_SHIFT_RATIO * 100.0,
                   help='Lateral escape offset as a percentage of the '
                        'protection-cylinder radius (cyl_d/2) at CPA. '
                        '100%% grazes the cylinder (ideal cyldist = 1); '
                        '150%% keeps a 50%% safety margin. Default: 150.')
    p.add_argument('--vertical-shift-pct', type=float,
                   default=DEFAULT_VERTICAL_SHIFT_RATIO * 100.0,
                   help='Vertical escape offset as a percentage of the '
                        'protection-cylinder half-height (cyl_h/2) at CPA. '
                        '100%% grazes the cylinder (ideal cyldist = 1); '
                        '150%% keeps a 50%% safety margin. Default: 150.')
    p.add_argument('--k-xt', type=float, default=DEFAULT_K_XT_PER_M,
                   help='Cross-track line-attraction gain (1/m, = 1/look-ahead) '
                        'of the route guidance law. Larger = sharper transition '
                        'onto the offset route.')
    p.add_argument('--a-max-along',    type=float, default=DEFAULT_A_MAX_ALONG_M_S2,
                   help='Along-track (speed-module) acceleration limit '
                        '(m/s²) of the integrator.')
    p.add_argument('--rate-max-azimuth',   type=float,
                   default=DEFAULT_RATE_MAX_AZIMUTH_RAD_S,
                   help='Course-angle (azimuth) rate limit (rad/s) of the '
                        'integrator.')
    p.add_argument('--rate-max-elevation', type=float,
                   default=DEFAULT_RATE_MAX_ELEVATION_RAD_S,
                   help='Flight-path-angle (elevation) rate limit (rad/s) '
                        'of the integrator.')
    p.add_argument('--alert-threshold', type=float, default=ALERT_THRESHOLD)
    p.add_argument('--closed-loop-mode',
                   choices=[CLOSED_LOOP_OPEN, CLOSED_LOOP_ON_CONFLICT,
                            CLOSED_LOOP_PERIODIC],
                   default=DEFAULT_CLOSED_LOOP_MODE,
                   help='Avoidance re-evaluation policy. "open" = legacy '
                        'single-maneuver behaviour. '
                        '"on_conflict" = closed-loop stacking while the '
                        'flown maneuver is still confirmed in conflict. '
                        '"periodic" (default) = re-check on a fixed cadence '
                        '(--periodic-interval) and switch (stack) to a '
                        'better escape only when the anti-flicker margin '
                        '(--switch-improve-ratio) is met.')
    p.add_argument('--periodic-interval', type=float, default=1.0,
                   help='Re-evaluation interval (s) for '
                        '--closed-loop-mode periodic. Default: 1.0.')
    p.add_argument('--switch-improve-ratio', type=float,
                   default=DEFAULT_SWITCH_IMPROVE_RATIO,
                   help='Anti-flicker margin for --closed-loop-mode '
                        'periodic: minimum fractional CPA-distance '
                        'improvement before switching escapes. '
                        'Default: 0.15 (15%%).')
    p.add_argument('--ukf-model', choices=['cv', 'ca', 'cab', 'ctra'],
                   default='cv',
                   help='UKF motion model: cv (constant velocity), '
                        'ca (constant accel, NED frame), cab '
                        '(constant accel, body frame), or ctra (constant '
                        'turn-rate + tangential accel). Default: cv.')
    p.add_argument('--maneuver-set',
                   choices=[MANEUVER_FAMILY_SHIFTED,
                            MANEUVER_FAMILY_MIN_BEARING,
                            MANEUVER_FAMILY_MIN_CONST_BEARING],
                   default=DEFAULT_MANEUVER_FAMILY,
                   help='Avoidance-maneuver family for the right / left / '
                        'climb / descend escapes: "shifted" (parallel-'
                        'route offset, the legacy behaviour), '
                        '"min_bearing" '
                        '(a fresh straight segment from the current '
                        'position that clears the predicted intruder CPA '
                        'by the safety margin) or "min_const_bearing" '
                        '(the constant-velocity / HOLD_VELOCITY analogue '
                        'of min_bearing, the default). The maintain and '
                        'slow-down escapes are shared.')
    p.add_argument('--process-noise-std', type=float, default=None,
                   help='UKF process-noise acceleration std (m/s^2). '
                        'Default: core value (10.0).')
    p.add_argument('--sigma-az', type=float, default=None,
                   help='Sensor azimuth   noise std (rad). Default: 0.02.')
    p.add_argument('--sigma-el', type=float, default=None,
                   help='Sensor elevation noise std (rad). Default: 0.02.')
    p.add_argument('--range-noise-fraction', type=float, default=None,
                   help='Sensor range noise 1-sigma as a fraction of the '
                        'measured distance. Default: 0.15 (15%%).')
    p.add_argument('--finite-difference-init-velocity', action='store_true',
                   help='Seed the first-sighting horizontal velocity '
                        'covariance per sighting as the two-point '
                        'finite-difference velocity variance '
                        '(2*sigma_pos^2/dt^2) instead of the fixed init '
                        'velocity std. Off (default) = fixed seed.')
    p.add_argument('--quiet', action='store_true',
                   help='Suppress per-seed progress lines.')
    args = p.parse_args()

    seeds = [args.seed_start + k * args.seed_step for k in range(args.n)]
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sim_kw = dict(
        lookahead=args.lookahead,
        cyl_h=args.cyl_h,
        cyl_d=args.cyl_d,
        lateral_shift_ratio=args.lateral_shift_pct / 100.0,
        vertical_shift_ratio=args.vertical_shift_pct / 100.0,
        maneuver_family=args.maneuver_set,
        k_xt=args.k_xt,
        a_max_along=args.a_max_along,
        rate_max_azimuth=args.rate_max_azimuth,
        rate_max_elevation=args.rate_max_elevation,
        alert_threshold=args.alert_threshold,
        closed_loop_mode=args.closed_loop_mode,
        periodic_interval_s=args.periodic_interval,
        switch_improve_ratio=args.switch_improve_ratio,
        process_noise_std=args.process_noise_std,
        ukf_model=args.ukf_model,
        sigma_az=args.sigma_az,
        sigma_el=args.sigma_el,
        range_noise_fraction=args.range_noise_fraction,
        finite_difference_init_velocity=args.finite_difference_init_velocity,
    )

    print(f'Running {len(seeds)} simulations '
          f'(seeds {seeds[0]}..{seeds[-1]} step {args.seed_step}) '
          f'[ukf_model={args.ukf_model}] '
          f'with {args.workers} worker(s) -> {out_path}')

    rows = []
    t_start = time.perf_counter()

    if args.workers <= 1:
        for k, s in enumerate(seeds):
            row = _run_one(s, **sim_kw)
            rows.append(row)
            if not args.quiet:
                print(f'  [{k+1:>5}/{len(seeds)}] seed={s:>10}  '
                      f'cls={row["classification"]:<6} '
                      f'd_base_min={row["min_d_baseline"]:>7}  '
                      f'cyldist_nm={row["cyldist_min_no_maneuver"]:>7}  '
                      f'cyldist_m={row["cyldist_min_maneuver"]:>7}')
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(_run_one, s, **sim_kw): s for s in seeds}
            done = 0
            for fut in as_completed(futures):
                row = fut.result()
                rows.append(row)
                done += 1
                if not args.quiet:
                    print(f'  [{done:>5}/{len(seeds)}] seed={row["seed"]:>10}  '
                          f'cls={row["classification"]:<6} '
                          f'cyldist_nm={row["cyldist_min_no_maneuver"]:>7}  '
                          f'cyldist_m={row["cyldist_min_maneuver"]:>7}')
        # Preserve seed order in the output for reproducibility.
        rows.sort(key=lambda r: int(r['seed']))

    with out_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    elapsed = time.perf_counter() - t_start
    print(f'\nWrote {len(rows)} rows to {out_path} (wall time {elapsed:.1f} s).')
    _print_summary(rows)
    print('\nReplay any encounter with:')
    print(f'  python {Path("visualize_avoidance.py")} --seed <SEED>')


if __name__ == '__main__':
    main()
