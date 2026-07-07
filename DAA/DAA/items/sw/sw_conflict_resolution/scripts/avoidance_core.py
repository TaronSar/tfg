#!/usr/bin/env python3
"""
Core (headless) avoidance simulation.

Given an encounter parameter spec, simulate per-step:
  - vision measurement (synthesised from current ownship + true intruder),
  - UKF tracking with the embedded CV estimator,
  - 1-sigma cylinder-distance evaluation over the list of candidate
    ownship trajectories produced by ``candidate_trajectories.
    generate_candidates`` for the next LOOKAHEAD seconds.

Candidates are treated as opaque ``(name, positions)`` pairs sorted in
order of preference: index 0 is the "do-nothing / current-path"
baseline used for alert detection, and indices >=1 are alternatives.
When the baseline's minimum 1-sigma cylinder distance drops below
``ALERT_THRESHOLD`` the simulator commits to the first alternative
that still clears the threshold; if none do, it falls back to the
alternative with the largest minimum distance.  Once committed, the
ownship is rolled forward by following the chosen candidate's
sampled positions (regenerated each step from the current state).

This module is intentionally GUI-free so it can be reused by
high-throughput Monte Carlo loops.  ``visualize_avoidance.py`` wraps
``run_simulation()`` and animates the recorded history.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Imports from sibling packages.
# ---------------------------------------------------------------------------
from daa_trajectory_generator.generate_encounters import generate_single_encounter

from .candidate_trajectories import (
    CandidateTrajectory, CandidateGenerator,
    CpaContext,
    default_generators,
    compose_route_xf,
    HOLD_VELOCITY,
    DEFAULT_LATERAL_SHIFT_RATIO,
    DEFAULT_VERTICAL_SHIFT_RATIO,
    vertical_shift_m_nominal,
    DEFAULT_SLOWDOWN_RATIO,
    DEFAULT_MANEUVER_FAMILY,
    DEFAULT_K_XT_PER_M,
    DEFAULT_A_MAX_ALONG_M_S2,
    DEFAULT_RATE_MAX_AZIMUTH_RAD_S,
    DEFAULT_RATE_MAX_ELEVATION_RAD_S,
    DEFAULT_SIM_DT_MAX_S,
)
from .avoidance_state_machine import (
    AvoidanceStateMachine, DEFAULT_ENERGY_COST_RATIOS,
    DEFAULT_HYSTERESIS_S, DEFAULT_RETURN_HYSTERESIS_S,
    CLOSED_LOOP_OPEN, CLOSED_LOOP_ON_CONFLICT, CLOSED_LOOP_PERIODIC,
    DEFAULT_CLOSED_LOOP_MODE,
    DEFAULT_SWITCH_IMPROVE_RATIO,
)
from .encounter_classifier import (
    EncounterClassification, classify_encounter,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LOOKAHEAD_S       = 60.0
DEFAULT_DT_S      = 0.1
FT_TO_M           = 0.3048   # sw_trajectory_generator outputs feet; multiply at boundary
CYL_HEIGHT_M    = 304.8
CYL_DIAMETER_M  = 609.6
# Re-exported for CLI scripts that still build the default generator set
# from these knobs.  The core itself no longer takes them — pass a
# pre-built ``generators`` list to :func:`run_simulation` instead.
LATERAL_SHIFT_RATIO = DEFAULT_LATERAL_SHIFT_RATIO
PROCESS_NOISE_STD = 10.0
# CTRA model only: process-noise std of the *turn rate* (angular
# acceleration, rad/s^2).  The CTRA state mixes a tangential acceleration
# (m/s^2) and a turn rate (rad/s) — quantities so different that one
# lumped scalar cannot drive both: a jerk-sized value on the turn-rate
# channel makes the predicted heading (hence position) envelope explode
# over the lookahead.  This separate, much smaller value drives the
# turn-rate random walk; the tangential-acceleration channel keeps using
# ``process_noise_std`` (a jerk, m/s^3).  Small on purpose — a UAV's
# turn rate drifts slowly: 0.002 rad/s^2 ⇒ ~0.9°/s of 1-σ drift over a
# 60 s horizon.
PROCESS_NOISE_OMEGA_STD_CTRA = 0.002  # rad/s^2
INIT_WINDOW       = 50
ALERT_THRESHOLD   = 1.0   # min 1-sigma cylinder distance triggering an alert

# First-sighting bootstrap (C++ ``est_init_from_measurement``) seeds the
# intruder velocity and acceleration at zero with a wide variance; the
# in-FOV measurement stream then pulls them in.  The velocity 1-sigma
# bounds the plausible intruder speed (a few hundred m/s).  The
# acceleration 1-sigma is deliberately SMALL: at first sighting the
# overwhelming prior is straight-and-level flight, so seeding a ~= 0
# with a tight initial covariance encodes that prior instead of throwing
# it away.  This is the INITIAL covariance (P0) only — it governs the
# bootstrap transient, not steady-state agility: the process-noise sigma
# (Q) still lets the filter grow the acceleration estimate when the
# intruder actually manoeuvres, so a tight P0 does NOT make the tracker
# sluggish.  A wide accel seed, by contrast, integrates twice into
# position and is a major source of predicted-envelope fan-out over the
# lookahead.  Used only by the CA / CAB / CTRA models (CV has no
# acceleration state).
INIT_VELOCITY_STD = 91.44   # m/s   (zero-velocity seed 1-sigma, horizontal)
INIT_ACCEL_STD    = 0.4572  # m/s^2 (zero-accel seed 1-sigma, ~0.05 g cruise jitter)

# Vertical (down) seed 1-sigmas.  Aircraft trajectories are largely
# level, so the vertical rate and vertical acceleration are far more
# tightly bounded than the horizontal speed / manoeuvre.  Seeding the
# down velocity / acceleration states tighter keeps the predicted
# altitude envelope from fanning out over the 60 s lookahead and tripping
# the cylinder on dispersion alone, while still bounding the worst
# realistic climb / descent.  Size the vertical velocity to the maximum
# vertical rate (~6000 ft/min = 100 m/s).  As with the horizontal accel,
# the vertical-accel seed is the INITIAL covariance only and is kept
# small (cruise is level); the process noise still tracks a genuine
# vertical manoeuvre.
INIT_VELOCITY_STD_VERTICAL = 30.48   # m/s   (~6000 ft/min climb/descent)
INIT_ACCEL_STD_VERTICAL    = 0.2286  # m/s^2 (tight: level-cruise prior)

# Camera field-of-view limits (degrees), applied to the body-frame
# azimuth / elevation of the synthesised vision measurement.  The
# ownship can only "see" — and therefore track — the intruder while it
# lies inside this cone.  Outside it the EKF receives no update and,
# after ``DEFAULT_TRACK_TIMEOUT_S`` without a sighting, the track is
# dropped so a fresh sighting re-initialises the estimate from scratch.
DEFAULT_FOV_AZ_MIN_DEG = -60.0
DEFAULT_FOV_AZ_MAX_DEG =  60.0
DEFAULT_FOV_EL_MIN_DEG = -15.0
DEFAULT_FOV_EL_MAX_DEG =  15.0
DEFAULT_TRACK_TIMEOUT_S = 5.0

_MEAS_NOISE = {
    'azimuth_rad':   float(np.radians(2.0)),
    'elevation_rad': float(np.radians(2.0)),
}

# Per-frame range-measurement 1-sigma noise as a fraction of the measured
# distance.  Management policy: the vision system's range error grows with
# distance, so the default range std fed to each ``est_update`` (and to the
# first-sighting bootstrap) is 15% of the measured range.  Azimuth /
# elevation noise stay fixed (``_MEAS_NOISE``) for now; a sensor that
# reports its own bounds can override this per frame.
RANGE_NOISE_FRACTION = 0.15
_OWN_POS_STD = np.array([1.0, 1.0, 2.0])
_OWN_ATT_STD = np.array([0.01, 0.01, 0.02])
_OWN_COV = np.diag(np.concatenate([_OWN_POS_STD**2, _OWN_ATT_STD**2]))


def finite_difference_velocity_var(meas_pos_var, dt):
    """Two-point finite-difference velocity variance for the first-sighting
    bootstrap: the velocity uncertainty implied by differencing two position
    measurements one frame ``dt`` apart.

    This is the statistically consistent track-initiation seed for the
    velocity state given the transverse position-measurement variance
    ``meas_pos_var`` (= r = the seeded P0p) and the frame step ``dt``::

        var((x1 - x0) / dt) = (sigma_x1^2 + sigma_x0^2) / dt^2 = 2 r / dt^2

    Seeding P0v at this value matches the velocity information the incoming
    position stream actually carries, so the zero-velocity seed relaxes to
    the true speed without the over-correction (overshoot) a tighter seed
    forces.  Returns the variance P0v (m/s)^2; take the square root for a
    1-sigma.
    """
    dt = float(dt)
    return 2.0 * float(meas_pos_var) / (dt * dt)


# ---------------------------------------------------------------------------
# DAA simulator (C++/DLL via ctypes)
# ---------------------------------------------------------------------------

# The ownship's real flight is driven entirely by the C++
# ``DAA_simulator`` (``daa_sil.daa_dll.Simulator``): it owns the route,
# the active :class:`RouteTransform` and the Virtual_ownship integrator.
# Per ``dt`` it is advanced by ``sim.step``; counterfactual / candidate
# look-aheads are projected non-destructively by ``sim.simulate``.

from daa_sil import daa_dll as _daa_dll


# ---------------------------------------------------------------------------
# Vision measurement (NED relative position + ownship attitude -> az/el/range)
# ---------------------------------------------------------------------------

def _ned_to_measurement(intr_pos, own_pos, own_att):
    rel_n = intr_pos[0] - own_pos[0]
    rel_e = intr_pos[1] - own_pos[1]
    rel_d = intr_pos[2] - own_pos[2]
    roll, pitch, yaw = own_att
    cp, sp = np.cos(yaw),   np.sin(yaw)
    ct, st = np.cos(pitch), np.sin(pitch)
    cr, sr = np.cos(roll),  np.sin(roll)
    x_b =  cp*ct*rel_n + sp*ct*rel_e - st*rel_d
    y_b = (-sp*cr + cp*st*sr)*rel_n + ( cp*cr + sp*st*sr)*rel_e + ct*sr*rel_d
    z_b = ( sp*sr + cp*st*cr)*rel_n + (-cp*sr + sp*st*cr)*rel_e + ct*cr*rel_d
    rng = float(np.sqrt(x_b*x_b + y_b*y_b + z_b*z_b))
    az  = float(np.arctan2(y_b, x_b))
    el  = float(np.arctan2(-z_b, np.sqrt(x_b*x_b + y_b*y_b)))
    return np.array([az, el, rng])


def _compute_initial_intruder_position(meas, own_pos, own_att):
    """Project a single (az, el, range) measurement back to NED."""
    az, el, rng = meas
    x_b = rng * np.cos(el) * np.cos(az)
    y_b = rng * np.cos(el) * np.sin(az)
    z_b = -rng * np.sin(el)
    roll, pitch, yaw = own_att
    cp, sp = np.cos(yaw),   np.sin(yaw)
    ct, st = np.cos(pitch), np.sin(pitch)
    cr, sr = np.cos(roll),  np.sin(roll)
    # body -> NED (transpose of the NED->body rotation above)
    n = ct*cp*x_b + (sr*st*cp - cr*sp)*y_b + (cr*st*cp + sr*sp)*z_b
    e = ct*sp*x_b + (sr*st*sp + cr*cp)*y_b + (cr*st*sp - sr*cp)*z_b
    d = -st*x_b   +  sr*ct       *y_b      +  cr*ct       *z_b
    return own_pos + np.array([n, e, d])


def _in_fov(meas, az_min_rad, az_max_rad, el_min_rad, el_max_rad):
    """True when the body-frame az/el of ``meas`` lie inside the camera cone.

    ``meas`` is the ``[azimuth, elevation, range]`` triple returned by
    :func:`_ned_to_measurement`; the azimuth and elevation are already
    expressed in the ownship body frame, so they are exactly the angles
    the camera FOV gates on.
    """
    az, el = float(meas[0]), float(meas[1])
    return (az_min_rad <= az <= az_max_rad) and (el_min_rad <= el <= el_max_rad)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class AvoidanceResult:
    """History recorded by :func:`run_simulation`.

    Per-step lookahead fields use the tracker's natural timeline,
    which has a *variable* length M_i per step (the route shortens
    as waypoints are popped).  They are therefore stored as lists
    of arrays rather than dense ndarrays:

      * ``sweep_taus[i]``    — (M_i,) relative times for step i.
      * ``cand_positions[i]``— (K, M_i, 3) candidate positions.
      * ``int_pred_pos[i]``  — (M_i, 3) intruder propagation.
      * ``int_pred_P[i]``    — (M_i, 4) intruder packed position
        covariance [Pnn, Pne, Pee, Pdd] (horizontal 2x2 + vertical var).

    All other time-indexed arrays have length T (number of steps
    actually executed); ``d_candidates`` has shape (T, K) where K is
    the number of candidate trajectories returned by the candidate
    generator.  ``candidate_names`` is a length-K tuple of opaque
    labels assigned by that generator (index 0 = baseline /
    current-path).
    """
    times:            np.ndarray
    sweep_taus:       list                  # list[np.ndarray]  per step
    own_pos:          np.ndarray            # (T, 3)
    own_vel:          np.ndarray
    own_att:          np.ndarray
    intr_true_pos:    np.ndarray            # (T, 3)
    intr_est_pos:     np.ndarray            # (T, 3)
    intr_est_P:       np.ndarray            # (T, 3, 3) position covariance
    # Estimator velocity / acceleration variances (diagonal, per NED
    # axis).  ``intr_est_vel_var[i]`` is ``(var_vn, var_ve, var_vd)`` and
    # ``intr_est_acc_var[i]`` is ``(var_an, var_ae, var_ad)`` (zero for
    # the CV model, which has no acceleration state).  NaN on steps with
    # no active track.  Visualiser-only; shape ``(0, 3)`` when history is
    # not recorded.
    intr_est_vel_var: np.ndarray            # (T, 3)
    intr_est_acc_var: np.ndarray            # (T, 3)
    candidate_names:  tuple                 # length K (opaque labels)
    cand_positions:   list                  # list[np.ndarray (K, M_i, 3)]
    d_candidates:     np.ndarray            # (T, K) min 1-sigma cylinder distance
    int_pred_pos:     list                  # list[np.ndarray (M_i, 3)]
    int_pred_P:       list                  # list[np.ndarray (M_i, 4)]  packed [Pnn,Pne,Pee,Pdd]
    track_point:      np.ndarray            # (T, 3) tracker projection on route
    cpa_own_pos:      np.ndarray            # (T, 3) ownship pos at predicted CPA (route candidate)
    cpa_intr_pos:     np.ndarray            # (T, 3) intruder mean pos at predicted CPA
    alert:            np.ndarray            # (T,) bool, d_candidates[:,0] < threshold
    in_maneuver:      np.ndarray            # (T,) bool (state != ROUTE)
    flown_idx:        np.ndarray            # (T,) int, candidate idx flown per step (-1=route)
    maneuver_idx:     int                   # last/current chosen maneuver index, -1 if none
    maneuver_start:   int                   # step index when first maneuver started, -1 if none
    n_commits:        int = 0               # total committed escapes (counts closed-loop re-stacks)
    committed_names:  tuple = ()            # chronological names of committed escapes (length n_commits)

    # ICAO Annex 2 §3.2 encounter classification.  ``encounters`` holds
    # one classification per committed maneuver shift, in commit order
    # (``encounters[i]`` matches ``committed_names[i]``); empty until the
    # first commit.  ``encounter`` is a convenience alias for the first
    # classification (``None`` until the first commit).
    encounter:        EncounterClassification = None
    encounters:       tuple = ()

    # Constants captured for downstream plotting
    cyl_h:            float = CYL_HEIGHT_M
    cyl_d:            float = CYL_DIAMETER_M
    alert_threshold:  float = ALERT_THRESHOLD
    # Avoidance-maneuver family the run was flown with.  The visualiser
    # uses it to pick the active-transform panel representation: a
    # constant-bearing (HOLD_VELOCITY) family shows the maneuver
    # azimuth / elevation, the shifted family shows the route shift.
    maneuver_family:  str = DEFAULT_MANEUVER_FAMILY

    # FOV-loss safe point (NED) of the last committed avoidance maneuver,
    # i.e. the last lookahead sample of the selected escape at the
    # instant it was committed.  ``None`` when no maneuver was committed.
    # Used by the FSM to gate the return while the intruder is out of the
    # camera FOV, and surfaced here for the 3-D visualisation.
    safe_point:       np.ndarray = field(default=None, repr=False)
    # Per-step FOV-loss safe-point series.  ``safe_point_series[i]`` is
    # the active safe point (NED) on step ``i`` when the gate is holding
    # back the return, else NaN; ``safe_point_active[i]`` is the matching
    # bool flag.  The visualiser uses these to show the safe-point marker
    # only on the steps where it is actually in use.
    safe_point_series: np.ndarray = field(default=None, repr=False)
    safe_point_active: np.ndarray = field(default=None, repr=False)

    # Live per-step lookahead of the currently-flown trajectory (slot 0:
    # the baseline route in ROUTE, the active candidate otherwise),
    # recomputed every step.  ``flown_lookahead[i]`` is an ``(M_i, 3)``
    # NED array; the visualiser draws it plus the protection cylinder at
    # its lookahead endpoint regardless of whether a decision-point
    # candidate snapshot exists yet.
    flown_lookahead:  list = field(default=None, repr=False)
    # Live per-step lookahead of the return-to-route candidate, sampled
    # only while a return path is being evaluated (AVOIDING / decision
    # point).  ``return_lookahead[i]`` is an ``(M_i, 3)`` NED array when
    # it exists, else a 1-sample NaN placeholder so the visualiser draws
    # nothing on steps where no return is in play.
    return_lookahead: list = field(default=None, repr=False)
    # Per-step active route transform (route_xf) committed by the FSM.
    # ``route_xf[i]`` is
    # ``[shift_n, shift_e, shift_d, speed_scale, mode, vel_n, vel_e, vel_d]``
    # (mode: 0 = TRACK_ROUTE, 1 = HOLD_VELOCITY / maintain).  The last
    # three are the commanded NED velocity while the transform holds a
    # constant velocity (NaN otherwise), letting the visualiser render the
    # maneuver azimuth / elevation for the constant-bearing family.
    # Recorded only when ``record_history`` is set (visualiser-only); shape
    # ``(0, 8)`` otherwise.
    route_xf:         np.ndarray = field(default=None, repr=False)

    # Per-step estimator lifecycle flags for the tracking-state panel
    # (always recorded).  ``tracking[i]`` — an active track is held and
    # scored; ``in_fov[i]`` — the intruder is inside the camera FOV;
    # ``est_started[i]`` — a track has been bootstrapped (started, though
    # possibly not yet active).  All length-T bool arrays.
    tracking:         np.ndarray = field(default=None, repr=False)
    in_fov:           np.ndarray = field(default=None, repr=False)
    est_started:      np.ndarray = field(default=None, repr=False)
    # ---------------- Counterfactual / ground-truth evaluation -----------
    # Counterfactual ownship trajectory (NED) = the actually-flown
    # Virtual_ownship trajectory produced by ``daa_simulate_route``
    # along the intended ``own_waypoints`` polyline, evaluated at
    # ``cf_times`` (the simulation time grid).  ``cf_intr_pos`` is
    # the matching linearly-interpolated true intruder track.
    cf_times:          np.ndarray = field(default=None, repr=False)
    cf_own_pos:        np.ndarray = field(default=None, repr=False)
    cf_intr_pos:       np.ndarray = field(default=None, repr=False)
    # Raw ownship target polyline = the user-supplied waypoint
    # vertices ``(N, E, D)`` themselves.  Plotting libraries draw
    # straight segments between consecutive vertices, so there is
    # no need to densify; this is the connect-the-dots geometric
    # reference and is NOT what the airframe would actually fly.
    target_own_pos:    np.ndarray = field(default=None, repr=False)
    # Horizontal / vertical true separations for both cases (LoWC).
    hsep_no_maneuver:  np.ndarray = field(default=None, repr=False)
    vsep_no_maneuver:  np.ndarray = field(default=None, repr=False)
    hsep_maneuver:     np.ndarray = field(default=None, repr=False)
    vsep_maneuver:     np.ndarray = field(default=None, repr=False)
    # Normalized cylinder distance: max(hsep/(cyl_d/2), vsep/(cyl_h/2)).
    # <1 = inside the cylinder (LoWC), =1 on the boundary, >1 outside.
    cyldist_no_maneuver:  np.ndarray = field(default=None, repr=False)
    cyldist_maneuver:     np.ndarray = field(default=None, repr=False)
    # Scalars and flags.
    cyldist_min_no_maneuver: float = float('nan')
    cyldist_min_maneuver:    float = float('nan')
    lowc_no_maneuver:  bool  = False
    lowc_maneuver:     bool  = False
    # True when at least one flown-trajectory LoWC instant
    # (``cyldist_maneuver < 1``) occurred while the EKF was *not* holding
    # an active track on the intruder — i.e. not trackable at that moment
    # (track not yet initialised, or dropped after the post-FOV-loss
    # coast timed out; typically an intruder closing from behind).  Lets
    # the batch table filter the unavoidable "never-tracked" failures from
    # genuine tracked avoidance failures.
    nontracked_lowc:   bool  = False
    classification:    str   = ''   # 'TP' | 'FP' | 'TN' | 'FN_M' | 'FN_NM'


# ---------------------------------------------------------------------------
# Counterfactual evaluation (ground-truth classification)
# ---------------------------------------------------------------------------

def _hv_seps(own_arr: np.ndarray, intr_arr: np.ndarray):
    diff = own_arr - intr_arr
    return np.hypot(diff[:, 0], diff[:, 1]), np.abs(diff[:, 2])


def _compute_classification(*,
                            times: np.ndarray,
                            own_route_dense: np.ndarray,
                            intr_true: np.ndarray,
                            own_flown: np.ndarray,
                            intr_flown: np.ndarray,
                            cyl_h: float,
                            cyl_d: float,
                            triggered: bool) -> dict:
    """Build the counterfactual ground-truth fields for ``AvoidanceResult``.

    Compares the never-maneuvered ownship route (``own_route_dense``,
    the densified intended ownship waypoints) against the actually
    flown trajectory, returning all ``cf_*`` / ``hsep_*`` / ``vsep_*``
    / ``cyldist_*`` arrays plus the TP/FP/TN/FN classification.
    """
    cf_times    = times.copy()
    cf_own_pos  = own_route_dense.copy()
    cf_intr_pos = intr_true.copy()

    half_h = 0.5 * float(cyl_h)
    half_d = 0.5 * float(cyl_d)

    hsep_nm, vsep_nm = _hv_seps(cf_own_pos, cf_intr_pos)
    cyldist_nm       = np.maximum(hsep_nm / half_d, vsep_nm / half_h)

    hsep_m,  vsep_m  = _hv_seps(own_flown, intr_flown)
    cyldist_m        = np.maximum(hsep_m / half_d, vsep_m / half_h)

    lowc_nm = bool(np.any(cyldist_nm < 1.0))
    lowc_m  = bool(cyldist_m.size and np.any(cyldist_m < 1.0))
    if   lowc_nm and not lowc_m:           cls = 'TP'   # real save
    elif (not lowc_nm) and triggered:      cls = 'FP'   # nuisance alert
    elif (not lowc_nm) and not triggered:  cls = 'TN'
    elif triggered:                        cls = 'FN_M'   # maneuvered but still LoWC
    else:                                  cls = 'FN_NM'  # no maneuver, missed entirely

    return dict(
        cf_times                = cf_times,
        cf_own_pos              = cf_own_pos,
        cf_intr_pos             = cf_intr_pos,
        hsep_no_maneuver        = hsep_nm,
        vsep_no_maneuver        = vsep_nm,
        hsep_maneuver           = hsep_m,
        vsep_maneuver           = vsep_m,
        cyldist_no_maneuver     = cyldist_nm,
        cyldist_maneuver        = cyldist_m,
        cyldist_min_no_maneuver = float(cyldist_nm.min()),
        cyldist_min_maneuver    = (float(cyldist_m.min())
                                   if cyldist_m.size else float('nan')),
        lowc_no_maneuver        = lowc_nm,
        lowc_maneuver           = lowc_m,
        classification          = cls,
    )


# ---------------------------------------------------------------------------
# Main simulation
# ---------------------------------------------------------------------------

def _waypoints_to_arrays(waypoints, *, name: str):
    """Validate and unpack an ``(t, N, E, D)`` waypoint iterable.

    Returns ``(t_array, p_array)`` of shapes ``(K,)`` and ``(K, 3)``.
    Times must be strictly ascending and there must be at least two
    points.
    """
    arr = np.asarray(list(waypoints), dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 4 or arr.shape[0] < 2:
        raise ValueError(
            f"{name} waypoints must be an iterable of at least 2 "
            f"(t, N, E, D) tuples; got shape {arr.shape}."
        )
    t = arr[:, 0]
    if not np.all(np.diff(t) > 0.0):
        raise ValueError(f"{name} waypoint times must be strictly ascending.")
    return t, arr[:, 1:4]


def _interp_waypoints(times, wp_t, wp_p):
    """Linearly interpolate (K x 3) waypoints onto ``times``.

    Past the last waypoint ``np.interp`` holds the last value (no
    extrapolation); times before ``wp_t[0]`` likewise hold ``wp_p[0]``.
    Both behaviours are intentional and match the intent that
    waypoints define a finite intended trajectory.
    """
    out = np.empty((times.size, 3), dtype=np.float64)
    for k in range(3):
        out[:, k] = np.interp(times, wp_t, wp_p[:, k])
    return out


# ---------------------------------------------------------------------------
# Per-step loop profiler
# ---------------------------------------------------------------------------

class _LoopProfiler:
    """Accumulates wall-clock time per labelled section of the per-step loop.

    Call :meth:`lap` at each section boundary with the name of the
    section that just finished; call it with ``None`` at the top of every
    iteration to (re)start the clock without attributing the
    inter-iteration gap to any section.  :meth:`report` prints a
    breakdown (seconds, percent of timed total, and ms/step) sorted by
    cost, to help decide what to optimise in Python vs. push into C++.
    """
    __slots__ = ('_t', 'acc', 'n_steps')

    def __init__(self):
        self._t = None
        self.acc = {}
        self.n_steps = 0

    def lap(self, label):
        now = time.perf_counter()
        if label is None:
            self.n_steps += 1
        elif self._t is not None:
            self.acc[label] = self.acc.get(label, 0.0) + (now - self._t)
        self._t = now

    def report(self):
        import sys
        total = sum(self.acc.values())
        if total <= 0.0:
            return
        n = max(self.n_steps, 1)
        print(f"\n[avoidance_core] per-step loop profile "
              f"({self.n_steps} steps, {total:.3f}s in timed sections):",
              file=sys.stderr)
        for label, secs in sorted(self.acc.items(),
                                  key=lambda kv: kv[1], reverse=True):
            print(f"  {label:<22s} {secs:8.3f}s  "
                  f"{100.0 * secs / total:5.1f}%  "
                  f"{1e3 * secs / n:7.3f} ms/step", file=sys.stderr)


class _NullProfiler:
    """No-op profiler used when ``profile`` is False (zero accounting)."""
    __slots__ = ()

    def lap(self, label):
        pass

    def report(self):
        pass


def run_simulation(
    *,
    own_waypoints,
    own_init_vel,
    intr_waypoints,
    own_p0=None,
    dt: float = 0.1,
    own_category: str = '',
    intr_category: str = '',
    alt_min_m: float = float('-inf'),
    alt_max_m: float = float('inf'),
    alt_margin_m: float = vertical_shift_m_nominal(
        DEFAULT_VERTICAL_SHIFT_RATIO, CYL_HEIGHT_M),
    n_alerting: int = 1,
    generators: list = None,
    energy_cost_ratios: dict = None,
    lookahead: float       = LOOKAHEAD_S,
    cyl_h:     float       = CYL_HEIGHT_M,
    cyl_d:     float       = CYL_DIAMETER_M,
    process_noise_std: float = PROCESS_NOISE_STD,
    process_noise_omega: float = PROCESS_NOISE_OMEGA_STD_CTRA,
    meas_noise: dict      = None,
    range_noise_fraction: float = RANGE_NOISE_FRACTION,
    ukf_model: str         = 'cv',
    init_window: int       = INIT_WINDOW,
    init_velocity_std: float = INIT_VELOCITY_STD,
    finite_difference_init_velocity: bool = False,
    init_accel_std: float    = INIT_ACCEL_STD,
    init_velocity_std_vertical: float = INIT_VELOCITY_STD_VERTICAL,
    init_accel_std_vertical: float    = INIT_ACCEL_STD_VERTICAL,
    fov_az_min_deg: float = DEFAULT_FOV_AZ_MIN_DEG,
    fov_az_max_deg: float = DEFAULT_FOV_AZ_MAX_DEG,
    fov_el_min_deg: float = DEFAULT_FOV_EL_MIN_DEG,
    fov_el_max_deg: float = DEFAULT_FOV_EL_MAX_DEG,
    track_timeout_s: float = DEFAULT_TRACK_TIMEOUT_S,
    alert_threshold: float = ALERT_THRESHOLD,
    engage_hysteresis_s: float = DEFAULT_HYSTERESIS_S,
    return_hysteresis_s: float = DEFAULT_RETURN_HYSTERESIS_S,
    closed_loop_mode: str = DEFAULT_CLOSED_LOOP_MODE,
    periodic_interval_s: float = 1.0,
    switch_improve_ratio: float = DEFAULT_SWITCH_IMPROVE_RATIO,
    a_max_along: float    = DEFAULT_A_MAX_ALONG_M_S2,
    rate_max_azimuth: float   = DEFAULT_RATE_MAX_AZIMUTH_RAD_S,
    rate_max_elevation: float = DEFAULT_RATE_MAX_ELEVATION_RAD_S,
    v_max: float = 1.0E12,
    v_min: float = 0.0,
    el_min: float = -1.5708,
    el_max: float = 1.5708,
    slowdown_ratio: float = DEFAULT_SLOWDOWN_RATIO,
    maneuver_family: str  = DEFAULT_MANEUVER_FAMILY,
    k_xt: float           = DEFAULT_K_XT_PER_M,
    sim_dt_max: float     = DEFAULT_SIM_DT_MAX_S,
    record_history: bool   = True,
    profile: bool          = False,
) -> AvoidanceResult:
    """Run one avoidance simulation and return its full history.

    The encounter geometry is defined by two sparse waypoint lists:

    * ``own_waypoints`` — iterable of ``(t, N, E, D)`` tuples (seconds,
      feet, NED).  Defines the intended ownship route.  At least two
      samples are required.  The Route_tracker densifies this
      internally; passing just two endpoints is sufficient for
      a straight-line route.
    * ``intr_waypoints`` — same schema, the assumed ground-truth
      intruder trajectory (used to synthesise vision measurements
      and to evaluate the counterfactual ground-truth classification).
    * ``own_init_vel`` — ``(vN, vE, vD)`` m/s, the ownship velocity
      at the simulation start time.  Roll/pitch/yaw are derived from
      this vector each step from the actually-flown velocity, so no
      attitude needs to be supplied.
    * ``own_p0`` — optional ``(N, E, D)`` ft, the ownship *initial
      position*.  When ``None`` it defaults to the first route
      waypoint (the legacy contract: route and initial state coincide).
      Supplying it explicitly decouples the airframe's starting
      pose from the desired-route polyline, so the controller can
      start off-route and re-acquire the path through the
      cross-track law.

    The simulation runs on a uniform time grid with step ``dt`` from
    the first waypoint time up to ``min(own_waypoints[-1][0],
    intr_waypoints[-1][0])``.  The vision measurements always use the
    *flown* ownship position and the body-frame attitude derived from
    its velocity — the waypoint lists are only consumed as targets
    (ownship) or as the intruder ground truth.

    ``own_category`` / ``intr_category`` are forwarded to the
    encounter classifier and only affect right-of-way reasoning.

    The ownship camera has a finite field of view: the intruder can
    only be tracked while its body-frame azimuth / elevation lie inside
    ``[fov_az_min_deg, fov_az_max_deg]`` x ``[fov_el_min_deg,
    fov_el_max_deg]`` (defaults ``[-60, 60]`` deg az, ``[-15, 15]`` deg
    el).  The intruder EKF is *lazily* initialised the first time the
    ownship sees the intruder (after ``init_window`` consecutive in-FOV
    frames used to seed velocity), updated only while it stays visible,
    and coasted on the motion model during brief occlusions.  After
    ``track_timeout_s`` seconds without a sighting the track is dropped;
    a later sighting re-initialises the estimate from scratch.  While no
    track is active the intruder estimate, predictions and cylinder
    distances are recorded as NaN / ``+inf`` (no alert) and the ownship
    simply follows its route.

    The remaining classifier inputs are exposed so the full 16-case
    catalogue can be exercised from a single encounter geometry:

    * ``alt_min_m`` / ``alt_max_m`` — flight-envelope altitude
      limits (m AGL, positive-up).  The ownship altitude band (Cases
      14 / 15) is derived from the ownship altitude at CPA against
      these limits: a climb is barred when it would exceed
      ``alt_max_m`` (near-ceiling, Case 14) and a descent is barred
      when it would drop below ``alt_min_m`` (near-floor, Case 15).
      ``alt_margin_m`` is the vertical clearance an escape needs
      (defaults to the climb/descend candidate displacement).  The
      ``+inf`` / ``-inf`` defaults disable the band.
    * ``n_alerting`` — number of intruders triggering an alert; ``>= 2``
      selects the global-separation Case 16 (``M_VACATE_LATERAL``).
      Only the classification path consumes this count, so a Case-16
      manoeuvre can be exercised against the single simulated intruder.

    ``generators`` must follow the ``[baseline, *avoidance, return]``
    layout expected by :class:`AvoidanceStateMachine`.  When ``None``,
    :func:`candidate_trajectories.default_generators` is used.

    ``energy_cost_ratios`` is an optional ``{maneuver_name: ratio}``
    dict that overrides the per-maneuver energy-cost ratios the state
    machine uses to rank the escapes a case permits.  At the decision
    instant the FSM picks the compliant escape with the best
    cylindrical-separation-per-energy score, so lowering one ratio
    (e.g. ``{'climb': 0.5}``) activates that branch for a multi-escape
    case without restricting the candidate set.  Unspecified maneuvers
    keep their default ratio (see
    :data:`avoidance_state_machine.DEFAULT_ENERGY_COST_RATIOS`).

    ``slowdown_ratio`` configures the along-track ``slow_down`` escape
    (``M_REDUCE_SPEED``): during that maneuver the ownship horizontal
    speed is capped at this fraction of its horizontal speed at the
    commit instant (e.g. ``0.6`` bleeds 40 % of the speed), staying on
    the route while letting a crossing / overtaking intruder pass
    ahead.  Only consumed when ``generators`` is ``None`` (the default
    set is built here); pass a custom generator list to override.

    ``engage_hysteresis_s`` / ``return_hysteresis_s`` add temporal
    hysteresis (debounce) to the maneuver transitions, both in seconds:

    * ``engage_hysteresis_s`` — the alert must persist continuously for
      at least this long before an avoidance maneuver is committed
      (and before the encounter is classified, which now happens at
      that same instant).  Any single conflict-free step resets the
      window, so a transient spike — e.g. an unconverged track on the
      frame it is re-initialised after re-entering the camera FOV —
      never triggers a maneuver or a (possibly mis-sided)
      classification.
    * ``return_hysteresis_s`` — the return path must stay continuously
      conflict-free for at least this long before the return-to-route
      maneuver starts; any single alerting step resets the window.

    ``engage_hysteresis_s`` defaults to :data:`DEFAULT_HYSTERESIS_S`
    (2 s) and ``return_hysteresis_s`` to
    :data:`DEFAULT_RETURN_HYSTERESIS_S` (10 s); set them to ``0.0`` for
    the legacy "act on the first qualifying step" behaviour.

    The encounter step ``dt`` is the single time-resolution knob:
    it sets the airframe re-decision cadence, the UKF predict step,
    and the spacing of the lookahead sampling grid used for
    candidate evaluation, intruder propagation and the
    cylinder-distance scan (``M = lookahead / dt`` snapshots per
    step).

    When ``record_history`` is False, the per-step / per-sweep buffers
    used only by the visualiser (candidate ownship trajectories,
    intruder propagation buffers, estimator state snapshots) are not
    recorded.  Only the time, distance, alert, ownship-position and
    true-intruder-position series — needed for the classification —
    are kept.  This is the mode used by ``batch_avoidance.py``.

    When ``profile`` is True, the per-step loop is instrumented with a
    lightweight section timer and a breakdown (seconds, percent and
    ms/step per labelled section) is printed to stderr at the end of the
    run.  It is a no-op stub otherwise, so leaving it off costs nothing.
    """

    if meas_noise is None:
        meas_noise = _MEAS_NOISE

    # Per-step loop profiler — opt-in (``profile=True``).  When off it is
    # a no-op stub so batch runs pay no measurable overhead.
    prof = _LoopProfiler() if profile else _NullProfiler()

    # ---- 1) Validate waypoints, build the simulation time grid ----
    own_t,  own_wp_p  = _waypoints_to_arrays(own_waypoints,  name='Ownship')
    intr_t, intr_wp_p = _waypoints_to_arrays(intr_waypoints, name='Intruder')
    own_init_vel = np.asarray(own_init_vel, dtype=np.float64).reshape(3)

    t_start = float(max(own_t[0],  intr_t[0]))
    t_end   = float(min(own_t[-1], intr_t[-1]))
    if not (t_end > t_start):
        raise ValueError(
            "Ownship and intruder waypoint time ranges do not overlap.")
    if float(dt) <= 0.0:
        raise ValueError("Simulation dt must be > 0.")

    n_steps = int(np.floor((t_end - t_start) / float(dt))) + 1
    if n_steps < init_window + 2:
        raise RuntimeError("Encounter trajectory is too short.")
    times = t_start + np.arange(n_steps, dtype=np.float64) * float(dt)
    T_total = n_steps
    dt_mean = float(dt)

    # Densified intruder ground truth (one row per simulation step).
    intr_true = _interp_waypoints(times, intr_t, intr_wp_p)

    # ``own_route_flown`` is the would-have-flown trajectory: the
    # never-maneuvered baseline produced by the simulator's
    # Virtual_ownship integrator tracking the desired-route polyline
    # from the actual initial state ``own_p0`` / ``own_init_vel``.  When
    # the caller leaves ``own_p0`` unset the legacy contract applies
    # (route and initial state coincide); when the caller supplies it
    # the airframe may start off-route and the cross-track law brings it
    # back onto the polyline.
    if own_p0 is None:
        own_p0 = own_wp_p[0].copy()
    else:
        own_p0 = np.asarray(own_p0, dtype=np.float64).reshape(3).copy()

    # ---- Build the DAA simulator.  It owns the route, the active route
    # transform and the Virtual_ownship integrator.  The guidance law
    # (cross-track gain, acceleration / velocity envelope) is configured
    # once here, so the candidate generators only carry the maneuver
    # *geometry*.  The route is the sparse user-supplied target polyline
    # as ``(N, 4)`` ``[N, E, D, speed]`` rows.
    # Resolve the embedded estimator motion model.  Accept either the
    # short string names used by the UI / CLI or a raw integer code.
    _UKF_MODEL_CODES = {
        'cv':   _daa_dll.UKF_MODEL_CV,
        'ca':   _daa_dll.UKF_MODEL_CA,
        'cab':  _daa_dll.UKF_MODEL_CAB,
        'ctra': _daa_dll.UKF_MODEL_CTRA,
    }
    if isinstance(ukf_model, str):
        _ukf_model_code = _UKF_MODEL_CODES.get(ukf_model.strip().lower(),
                                               _daa_dll.UKF_MODEL_CV)
    else:
        _ukf_model_code = int(ukf_model)

    sim = _daa_dll.Simulator(
        dt=dt_mean,
        sim_dt_max=sim_dt_max,
        k_xt=k_xt,
        p0=own_p0,
        v0=own_init_vel,
        route_capacity=int(own_wp_p.shape[0]) + 2,
        a_max_along=a_max_along,
        rate_max_azimuth=rate_max_azimuth,
        rate_max_elevation=rate_max_elevation,
        v_max=v_max,
        v_min=v_min,
        el_min=el_min,
        el_max=el_max,
        lookahead=lookahead,
        cyl_h=cyl_h,
        cyl_d=cyl_d,
        ukf_model=_ukf_model_code,
    )
    own_route_pdt = np.zeros((own_wp_p.shape[0], 4), dtype=np.float64)
    own_route_pdt[:, :3] = own_wp_p
    if own_wp_p.shape[0] >= 2:
        # Per-point target speed = the speed the ownship shall have when
        # flying *towards* that waypoint, so row i carries the speed of
        # the segment ending at it: chord(wp[i-1], wp[i]) / (t[i]-t[i-1]).
        # Times are strictly ascending (validated), so seg_dt > 0.  The
        # first row's speed is unused (no segment leads to wp[0]); it
        # mirrors row 1 for cleanliness.
        seg_len = np.linalg.norm(np.diff(own_wp_p, axis=0), axis=1)
        seg_dt  = np.diff(own_t)
        own_route_pdt[1:, 3] = seg_len / seg_dt
        own_route_pdt[0, 3]  = own_route_pdt[1, 3]
    sim.push_route(own_route_pdt)

    # Never-maneuvered counterfactual baseline: project the identity
    # transform over the whole encounter without mutating the simulator
    # (``sim.simulate`` uses a private Virtual_ownship copy).  Sampled
    # ``dt`` apart, so row ``i`` is the would-have-flown position at
    # ``times[i]``.
    own_route_flown = sim.simulate(int(T_total))

    # ---- 2) Embedded CV estimator — lazily initialised on first sight ----
    # The estimator is *not* primed up front: the camera has a finite
    # field of view, so the intruder is only tracked once it has been
    # seen.  On the first in-FOV frame the filter is bootstrapped
    # *entirely on the C++ side* (``sim.est_init_from_measurement``):
    # the measurement is back-projected to NED with an anisotropic
    # position covariance and a zero-velocity seed, and every subsequent
    # in-FOV frame is folded in with a normal predict/update.  The track
    # only becomes "active" (eligible to drive propagation / scoring /
    # alerts) once it has ingested ``init_window`` in-FOV frames, so the
    # wide bootstrap covariance has settled and cannot raise a false
    # alert.  The lifecycle state below is advanced inside the per-step
    # loop.
    # The estimator now lives *inside* the simulator (the ``sim.est_*``
    # methods), sharing its single opaque handle; its propagation output
    # buffers were sized at construction from the look-ahead horizon and
    # step.  This lets the slot-0 flown trajectory be projected and
    # scored against the intruder track in one fused ``simulate_and_score``
    # call per step.

    # Camera FOV cone (body-frame az/el), converted to radians once.
    _fov_az_min = float(np.radians(fov_az_min_deg))
    _fov_az_max = float(np.radians(fov_az_max_deg))
    _fov_el_min = float(np.radians(fov_el_min_deg))
    _fov_el_max = float(np.radians(fov_el_max_deg))
    _track_timeout = float(track_timeout_s)

    # Wide zero-seed variances handed to the C++ bootstrap.
    _init_vel_var = float(init_velocity_std) * float(init_velocity_std)
    _init_acc_var = float(init_accel_std) * float(init_accel_std)
    _init_vel_var_vert = (float(init_velocity_std_vertical)
                          * float(init_velocity_std_vertical))
    _init_acc_var_vert = (float(init_accel_std_vertical)
                          * float(init_accel_std_vertical))

    # CTRA carries two manoeuvre states with different physical
    # quantities — tangential acceleration (m/s^2) and turn rate
    # (rad/s) — so a single lumped process-noise scalar cannot size both.
    # Build the explicit per-state Q diagonal once and push it to the
    # estimator after each (re)bootstrap (initialize resets Q): the
    # tangential-acceleration channel is driven by the jerk
    # ``process_noise_std`` (m/s^3), the turn-rate channel by the much
    # smaller ``process_noise_omega`` (rad/s^2).  The continuous
    # white-noise variances are scaled by dt to match the per-step Q the
    # model's initialize() uses (q^2 * dt).
    _is_ctra = (_ukf_model_code == _daa_dll.UKF_MODEL_CTRA)
    _ctra_q_diag = None
    if _is_ctra:
        _q_at = float(process_noise_std)        # m/s^3 (tangential jerk)
        _q_om = float(process_noise_omega)      # rad/s^2 (angular accel)
        _ctra_q_diag = np.zeros(8, dtype=np.float64)
        _ctra_q_diag[6] = _q_at * _q_at * dt_mean   # a_tang channel
        _ctra_q_diag[7] = _q_om * _q_om * dt_mean   # omega channel

    est_started  = False        # filter bootstrapped & receiving updates
    est_active   = False        # settled enough to drive scoring / alerts
    last_seen_t  = None         # sim time of the most recent in-FOV frame
    n_warmup     = 0            # in-FOV frames since the current (re)start
    start_idx = 0               # lazy lifecycle runs the loop from frame 0


    # Pre-built per-step lookahead grid template.  Uniform spacing
    # ``dt`` from 0 up to ``lookahead``; sliced each step to the
    # remaining encounter horizon.  ``out_t[1] == dt`` is the next
    # encounter step.  In the simulator model the real flight is driven
    # by ``sim.step``, so this grid is only the look-ahead sampling grid
    # for candidate previews, intruder propagation and the
    # cylinder-distance scan.
    _dt_f       = float(dt_mean)
    _lookahead_f = float(lookahead)
    _out_t_full = np.arange(0.0, _lookahead_f + 0.5 * _dt_f, _dt_f)
    _M_full     = int(_out_t_full.size)

    # Constant NaN placeholders for the no-active-track branch, allocated
    # once at the full horizon and sliced to ``M`` each step.  They are
    # never written to in that branch (all scoring is gated on
    # ``est_active``) and are ``.copy()``-ed into history, so sharing a
    # single buffer across steps is safe.
    _int_pos_nan = np.full((_M_full, 3),    np.nan, dtype=np.float64)
    _int_cov_nan = np.full((_M_full, 4),    np.nan, dtype=np.float64)

    # Reusable estimator state / covariance buffers for the per-step
    # history capture.  ``est_get_state`` writes into these in place
    # (zero-copy); only the small slices that go into history are copied
    # out, so a single pair of buffers is shared across every step.
    _est_state_buf = np.empty(6, dtype=np.float64)
    _est_P_buf     = np.empty((6, 6), dtype=np.float64)
    _est_acc_buf   = np.empty(3, dtype=np.float64)

    # ---- 3) Per-step buffers are allocated inside the loop now ----
    # (Their length M_i comes from the Route_tracker on every step;
    # there is no fixed sweep grid.)

    # ---- 4) Output history (lists; converted to arrays at the end) ----
    # Lightweight series — always recorded; classification and the batch
    # CSV depend on these.
    _light_keys = ('times', 'own_pos', 'intr_true_pos',
                   'd_candidates', 'alert', 'in_maneuver', 'flown_idx',
                   'sweep_taus', 'track_point',
                   'cpa_own_pos', 'cpa_intr_pos',
                   'tracking', 'in_fov', 'est_started',
                   'safe_point', 'safe_point_active')
    # Heavy per-step / per-sweep buffers — only recorded for the
    # visualiser.  Skipped for batch runs (record_history=False).
    _heavy_keys = ('own_vel', 'own_att',
                   'intr_est_pos', 'intr_est_P',
                   'intr_est_vel_var', 'intr_est_acc_var',
                   'cand_positions', 'flown_lookahead', 'return_lookahead',
                   'int_pred_pos', 'int_pred_P', 'route_xf')
    hist_keys = _light_keys + (_heavy_keys if record_history else ())
    hist = {k: [] for k in hist_keys}

    if generators is None:
        generators = default_generators(
            slowdown_ratio=slowdown_ratio,
            maneuver_family=maneuver_family,
        )
    fsm = AvoidanceStateMachine(generators,
                                alert_threshold=alert_threshold,
                                engage_hysteresis_s=engage_hysteresis_s,
                                return_hysteresis_s=return_hysteresis_s,
                                closed_loop_mode=closed_loop_mode,
                                switch_improve_ratio=switch_improve_ratio)
    # Override the per-maneuver energy-cost ratios the FSM uses to rank
    # the escapes a case permits.  Unspecified maneuvers keep their
    # default ratio, so a partial dict (e.g. ``{'climb': 0.5}``) only
    # nudges the one branch the caller wants to favour.
    if energy_cost_ratios:
        fsm.energy_cost.update(
            {str(k): float(v) for k, v in energy_cost_ratios.items()})

    # Candidate labels are fixed by the generator list (index order),
    # so they can be captured once up-front rather than rediscovered on
    # the first sampled step.
    candidate_names = tuple(g.name for g in generators)
    n_gen = len(generators)

    # Last full candidate-evaluation snapshot, ``(K, M, 3)`` NED.  The
    # avoidance loop only samples *every* candidate at a decision point
    # (a conflict that commits / re-commits a maneuver); between those
    # it evaluates the minimum set needed to drive the FSM (the flown
    # path, plus the return path while avoiding).  For the visualiser
    # the most recent full snapshot is carried forward so the candidate
    # trajectories appear fixed in place from the instant they were
    # computed.  ``None`` until the first full evaluation.
    last_cand_snapshot: np.ndarray = None

    # 16-case classification — recomputed at every commit.  Each
    # predicted LoWC that (re-)commits a maneuver — on the original route
    # or stacked on top of an active avoidance — gets its own
    # classification, so there are as many entries as committed maneuver
    # shifts (returns do not classify).  ``encounter_classes[i]`` matches
    # ``fsm.committed_names[i]``.
    encounter_classes: list = []
    own_cat  = str(own_category  or '')
    intr_cat = str(intr_category or '')
    n_alerting_in = int(n_alerting)

    # Ownship velocity (NED) at the predicted CPA on the route
    # candidate, carried one step so the candidate preview can orient
    # the lateral escapes to the starboard / port perpendicular of the
    # CPA heading.  ``None`` until the first step that has an active
    # track; the candidate resolvers fall back to the route-tangent
    # perpendicular while it is ``None`` / non-finite.
    own_vel_cpa_prev: np.ndarray = None

    # ---- 5) Per-step loop ----
    # The ownship's real flight is driven by ``sim.step``: ``cur_pos`` /
    # ``cur_vel`` / ``cur_track`` hold the live state for the current
    # step (seeded from the simulator's initial state, then advanced by
    # ``sim.step`` at the end of each iteration under whatever route
    # transform the state machine has committed).  ``cur_track`` is the
    # simulator's per-step track point (foot of the perpendicular from
    # the ownship onto the active route); it is the ownship position at
    # step 0 until the first ``sim.step`` produces a real projection.
    cur_pos   = sim.get_position()
    cur_vel   = sim.get_velocity()
    cur_track = cur_pos.copy()
    # Wall time of the last periodic closed-loop re-evaluation; ``-inf``
    # so the first AVOIDING step in ``periodic`` mode evaluates at once.
    last_periodic_t = float('-inf')
    for i in range(start_idx, T_total):
        prof.lap(None)
        own_pos = cur_pos
        own_vel = cur_vel
        track_point = cur_track
        intr_p  = intr_true[i]
        # Body-frame attitude derived from the live ownship velocity
        # (roll = 0; pitch / yaw from the flight-path vector).
        _h_xy = float(np.hypot(own_vel[0], own_vel[1]))
        _h_sf = _h_xy if _h_xy > 1e-9 else 1e-9
        own_att = np.array([0.0,
                            float(np.arctan2(-own_vel[2], _h_sf)),
                            float(np.arctan2(own_vel[1], own_vel[0]))])

        # 5a) Vision measurement.  The body-frame azimuth / elevation
        # returned here are the camera bearing to the intruder, so the
        # FOV gate decides whether the ownship can currently see it.
        meas = _ned_to_measurement(intr_p, own_pos, own_att)
        dt = dt_mean
        t_now = float(times[i])
        visible = _in_fov(meas, _fov_az_min, _fov_az_max,
                          _fov_el_min, _fov_el_max)
        prof.lap('5a_meas_attitude')

        # 5a') Estimator visibility lifecycle.  Bootstrap the track on
        # the first sighting straight from the measurement (C++ side),
        # fold in every subsequent in-FOV frame with predict/update,
        # coast on the motion model during brief occlusions, and drop the
        # track after ``track_timeout_s`` without a sighting so a later
        # sighting re-initialises it.  The track is held back from
        # scoring (``est_active``) until it has ingested ``init_window``
        # in-FOV frames.
        if visible:
            last_seen_t = t_now
            if est_started:
                # Refine the bootstrapped track with this in-FOV frame.
                # The range measurement noise scales with the measured
                # distance (``range_noise_fraction`` of range); az / el
                # stay fixed.  A real sensor could substitute its own
                # reported uncertainty here.
                sim.est_predict()
                meas_std = np.array([
                    meas_noise['azimuth_rad'],
                    meas_noise['elevation_rad'],
                    range_noise_fraction * float(meas[2]),
                ])
                sim.est_update(meas, meas_std, own_pos, own_att, _OWN_COV)
            else:
                # First sighting: bootstrap the filter directly from the
                # measurement on the C++ side (anisotropic position
                # covariance, zero-velocity / zero-acceleration seed).
                # No Python-side velocity finite-difference.  The range
                # 1-sigma scales with the measured distance just like the
                # update stream (``range_noise_fraction`` of range); az /
                # el stay fixed.  For CTRA,
                # ``_ctra_q_diag`` overrides the lumped-scalar Q with an
                # explicit per-channel diagonal (a_tang vs turn-rate need
                # very different magnitudes); ``None`` for other models
                # keeps their own (possibly structured) Q.
                boot_noise = {
                    'azimuth_rad':   meas_noise['azimuth_rad'],
                    'elevation_rad': meas_noise['elevation_rad'],
                    'range_m':      range_noise_fraction * float(meas[2]),
                }
                # Horizontal velocity seed.  When the finite-difference
                # option is on, size P0v per sighting from the transverse
                # position accuracy (range * angular 1-sigma) as the
                # two-point finite-difference velocity variance -- the
                # consistent track-initiation seed -- instead of the fixed
                # configured value.
                if finite_difference_init_velocity:
                    _meas_pos_var = (float(meas[2])
                                     * float(meas_noise['azimuth_rad'])) ** 2
                    _boot_vel_var = finite_difference_velocity_var(
                        _meas_pos_var, dt_mean)
                else:
                    _boot_vel_var = _init_vel_var
                sim.est_init_from_measurement(
                    meas, own_pos, own_att, _OWN_COV,
                    dt_mean, process_noise_std, boot_noise,
                    velocity_variance=_boot_vel_var,
                    acceleration_variance=_init_acc_var,
                    velocity_variance_vertical=_init_vel_var_vert,
                    acceleration_variance_vertical=_init_acc_var_vert,
                    q_var_diag=_ctra_q_diag,
                )
                est_started = True
            n_warmup += 1
            est_active = (n_warmup >= init_window)
        else:
            if est_started:
                if (last_seen_t is not None
                        and (t_now - last_seen_t) > _track_timeout):
                    # Track lost: drop it so a fresh sighting re-inits
                    # the estimate from scratch.
                    est_started = False
                    est_active = False
                    n_warmup = 0
                else:
                    # Brief occlusion: coast on the motion model only.
                    sim.est_predict()
        prof.lap('5a_estimator')

        # 5b) Lookahead sampling grid.  The simulator owns the route, so
        # there is no Python-side polyline any more: the per-step grid is
        # simply the uniform ``dt`` lookahead template, sliced to the
        # remaining encounter horizon.  ``out_t[1] == dt`` is the next
        # encounter step.  It is the common grid for candidate sampling,
        # intruder propagation and the cylinder-distance scan, and is
        # estimator-independent so the ownship always advances along its
        # route even with no active track.
        M = min(_M_full, T_total - i)
        if M < 2:
            # Not enough horizon left to evaluate / roll forward.
            break
        out_t = _out_t_full[:M]

        # 5b') Propagate the intruder once for all candidates, at the
        # dense output timeline — only meaningful with an active track.
        # Without one the intruder is unknown, so the predictions are
        # NaN and no alert can fire.  With a track, the buffers are the
        # estimator-owned views (overwritten in place each step).
        if est_active:
            int_pos_buf, int_cov_buf = sim.propagate(M)
        else:
            int_pos_buf = _int_pos_nan[:M]
            int_cov_buf = _int_cov_nan[:M]
        prof.lap('5b_propagate')

        # 5c) Build candidate ownship trajectories — lazily.  Sampling a
        # candidate (a DLL route integration) and scoring its minimum
        # 1-sigma cylinder distance is the dominant per-step cost, so we
        # evaluate only the candidates the state machine actually needs
        # this step:
        #   * always the *currently flown* trajectory (the baseline route
        #     in ROUTE; the committed avoidance / return otherwise),
        #     mirrored into slot 0 so ``ds[0]`` is the alert distance of
        #     what is being flown right now;
        #   * the return candidate while AVOIDING, to detect when the
        #     path back to the route has cleared;
        #   * *every* candidate only at a decision point — i.e. when an
        #     alert has been confirmed in ROUTE / RETURNING and a
        #     maneuver is about to be (re-)committed — so
        #     ``select_avoidance`` can rank the full escape set.
        # Unevaluated candidates keep ``ds = +inf`` (no alert) and a
        # ``None`` trajectory slot.
        cand_buf = np.empty((n_gen, M, 3), dtype=np.float64)
        cands: list = [None] * n_gen
        ds = np.full(n_gen, np.inf, dtype=np.float64)
        # CPA context (cylinder dims + intruder covariance at the CPA)
        # used to size the committed ratio-based lateral / vertical
        # escapes.  Populated in the 5d block once the flown-trajectory
        # CPA index is known (active track only); ``None`` otherwise, in
        # which case the resolvers fall back to nominal (sigma=0) sizing.
        cpa_ctx = None

        def _sample_cand(k):
            generators[k].sample(simulator=sim, n_out=M,
                                  own_vel_cpa=own_vel_cpa_prev,
                                  fwd_vel=own_vel, cpa_ctx=cpa_ctx,
                                  out=cand_buf[k])
            cands[k] = CandidateTrajectory(generators[k].name, cand_buf[k])

        def _sample_score_cand(k):
            # Fused sample + cylinder-distance score in one DLL call.
            # Requires the intruder propagation to be loaded into the
            # simulator-owned buffers (done at 5b' while a track is live),
            # so callers gate this on ``est_active``.  Returns
            # ``(min_cyldist, idx_cpa)``.
            _, d, idx = generators[k].sample_and_score(
                simulator=sim, n_out=M,
                own_vel_cpa=own_vel_cpa_prev, fwd_vel=own_vel,
                cpa_ctx=cpa_ctx, out=cand_buf[k])
            cands[k] = CandidateTrajectory(generators[k].name, cand_buf[k])
            return d, idx

        def _sample_score_cand_composed(k, base_xf):
            # Closed-loop preview: fused sample + score of candidate ``k``
            # *composed on top of* the active transform ``base_xf`` so the
            # ranking reflects the stacked trajectory.  Mirrors
            # ``_sample_score_cand`` but folds the active transform in
            # first.  Requires a live track (propagation loaded).
            delta = generators[k].transform(own_vel_cpa=own_vel_cpa_prev,
                                             fwd_vel=own_vel,
                                             cpa_ctx=cpa_ctx)
            xf = base_xf if delta is None else compose_route_xf(base_xf, delta)
            _, d, idx = sim.simulate_and_score(
                M, shift=xf.shift, speed_scale=xf.speed_scale,
                mode=xf.mode, velocity=xf.velocity,
                track_p0=xf.track_p0, track_p1=xf.track_p1,
                track_speed=xf.track_speed, out=cand_buf[k])
            cands[k] = CandidateTrajectory(generators[k].name, cand_buf[k])
            return d, idx

        # Currently flown trajectory (slot 0).  Always the simulator's
        # *active* route transform: identity while in ROUTE, the
        # committed escape while AVOIDING / RETURNING.  With a live track
        # the projection and its cylinder-distance score are fused into a
        # single ``simulate_and_score`` DLL call (the dominant per-step
        # cost); without one only the trajectory is projected (no alert
        # can fire), so ``ds[0]`` stays ``+inf``.  Either way slot 0 is
        # exactly what ``sim.step`` will fly, so ``ds[0]`` is the alert
        # distance of what is being flown right now.
        _flown_shift, _flown_speed_scale, _flown_mode, _flown_vel, \
            _flown_tp0, _flown_tp1, _flown_tspeed = sim.get_route_xf()
        if est_active:
            _, _flown_d, _flown_idx = sim.simulate_and_score(
                M,
                shift=_flown_shift, speed_scale=_flown_speed_scale,
                mode=_flown_mode, velocity=_flown_vel,
                track_p0=_flown_tp0, track_p1=_flown_tp1,
                track_speed=_flown_tspeed, out=cand_buf[0])
        else:
            sim.simulate(M, shift=_flown_shift, speed_scale=_flown_speed_scale,
                         mode=_flown_mode, velocity=_flown_vel,
                         track_p0=_flown_tp0, track_p1=_flown_tp1,
                         track_speed=_flown_tspeed,
                         out=cand_buf[0])
            _flown_d = np.inf
            _flown_idx = 0
        cands[0] = CandidateTrajectory(generators[0].name, cand_buf[0])
        prof.lap('5c_flown_sample')

        # 5d) Minimum 1-sigma cylinder distance + predicted CPA on the
        # flown trajectory — only with an active track.  Without one
        # there is no intruder estimate, so distances stay ``+inf`` (no
        # alert) and the CPA fields are NaN.
        if est_active:
            ds[0] = _flown_d
            if fsm.state != fsm.ROUTE:
                ds[fsm.active_idx] = ds[0]
            idx_cpa_route = int(_flown_idx)
            # CPA positions on the flown candidate at this step — reused
            # by the encounter classifier (first alert only) and by the
            # visualiser (every frame).
            own_pos_cpa_step  = cand_buf[0][idx_cpa_route].copy()
            intr_pos_cpa_step = int_pos_buf[idx_cpa_route].copy()
            # Freeze the CPA context for this step's potential commit:
            # the cylinder dimensions, the intruder covariance, and the
            # estimated ownship→intruder separation at the flown-trajectory
            # CPA index.  The ratio-based escapes size their shift against
            # this — reduced by the separation already present along the
            # escape direction — so the achieved cylinder distance at the
            # CPA lands near the configured ratio.
            cpa_ctx = CpaContext(
                cyl_d=cyl_d, cyl_h=cyl_h,
                intr_cov_cpa=int_cov_buf[idx_cpa_route].copy(),
                rel_cpa=(intr_pos_cpa_step - own_pos_cpa_step),
                own_pos=own_pos.copy(),
                intr_pos_cpa=intr_pos_cpa_step.copy())
            # CPA velocities — finite-differenced from the flown candidate
            # (own) and the propagated intruder mean.
            _k1 = min(idx_cpa_route + 1, M - 1)
            _k0 = max(idx_cpa_route - 1, 0)
            _dt_cpa = float(out_t[_k1] - out_t[_k0]) or 1e-6
            own_vel_cpa_step  = (cand_buf[0][_k1]
                                 - cand_buf[0][_k0]) / _dt_cpa
            intr_vel_cpa_step = (int_pos_buf[_k1]
                                 - int_pos_buf[_k0]) / _dt_cpa
        else:
            idx_cpa_route = 0
            own_pos_cpa_step  = cand_buf[0][0].copy()
            intr_pos_cpa_step = np.full(3, np.nan)
            own_vel_cpa_step  = own_vel.copy()
            intr_vel_cpa_step = np.full(3, np.nan)
        prof.lap('5d_score_flown')

        # Return candidate while AVOIDING: needed to detect when the
        # path back to the route has cleared (drives AVOIDING -> RETURNING)
        # and to roll the ownship forward along it once the return
        # commits.  The trajectory is pure geometry, so it is sampled
        # whenever avoiding; only its cylinder-distance score needs an
        # active track.
        if fsm.state == fsm.AVOIDING:
            if est_active:
                ds[fsm.return_idx], _ = _sample_score_cand(fsm.return_idx)
            else:
                _sample_cand(fsm.return_idx)
        prof.lap('5d_return_cand')

        # Ownship velocity (NED) at the flown-candidate CPA — i.e. the
        # route tangent there.  Used to orient the committed lateral
        # escape to the starboard / port perpendicular of the CPA
        # heading (fresh value for this step's commit) and carried to
        # the next step's candidate preview.  Falls back to the current
        # ownship velocity with no active track, in which case the
        # resolvers use the current route tangent.
        own_vel_cpa_cur = own_vel_cpa_step

        # 5e) Advance the state machine.  It owns commit/reset and
        # picks the avoidance candidate when entering AVOIDING.
        alert_now = bool(ds[0] < alert_threshold)

        # Refresh the FSM debounce timers for this step and read whether
        # the engage condition is *confirmed* (alert held continuously
        # for ``engage_hysteresis_s``).  ``fsm.step`` below reuses these
        # same timers (no double-count), so the classification fires on
        # the exact step the maneuver is committed.
        engage_confirmed, _ = fsm.update_timers(ds=ds, t_now=t_now,
                                                track_valid=est_active)

        # 5d') Decision-point evaluation: an alert has been confirmed and
        # a maneuver is about to be (re-)committed this step.  Sample the
        # full escape set now so ``select_avoidance`` can rank every
        # option and the safe-point capture sees the chosen maneuver's
        # lookahead.  This fires when entering AVOIDING from ROUTE /
        # RETURNING and, in closed-loop mode, also while already AVOIDING
        # (to stack another escape) — in which case the candidates are
        # sampled *composed on top of* the active transform so the
        # ranking reflects the stacked trajectory.  This is the only
        # place every candidate is evaluated; snapshot it for the
        # visualiser so the candidate trajectories appear fixed from the
        # instant they were computed.
        # ``on_conflict`` closed-loop re-stacks while AVOIDING whenever
        # the flown maneuver is still confirmed in conflict (gated by
        # ``engage_confirmed`` below); ``periodic`` closed-loop re-stacks
        # on a fixed wall cadence instead, independent of the alert
        # hysteresis, and lets the FSM apply its anti-flicker switch test
        # (``periodic_eval`` to ``fsm.step``) on the freshly-ranked set.
        on_conflict_restack = (
            fsm.closed_loop_mode == CLOSED_LOOP_ON_CONFLICT
            and fsm.state == fsm.AVOIDING)
        periodic_due = (
            fsm.closed_loop_mode == CLOSED_LOOP_PERIODIC
            and fsm.state == fsm.AVOIDING
            and est_active
            and (t_now - last_periodic_t) >= periodic_interval_s)
        if periodic_due:
            last_periodic_t = t_now
        # Sample the full candidate set composed on top of the active
        # transform on any closed-loop re-evaluation while AVOIDING.
        restack_compose = on_conflict_restack or periodic_due
        if (est_active
                and ((engage_confirmed
                      and (fsm.state in (fsm.ROUTE, fsm.RETURNING)
                           or on_conflict_restack))
                     or periodic_due)):
            for k in fsm.avoidance_indices:
                if cands[k] is None:
                    if restack_compose:
                        ds[k], _ = _sample_score_cand_composed(
                            k, fsm.active_xf)
                    else:
                        ds[k], _ = _sample_score_cand(k)
            if cands[fsm.return_idx] is None:
                ds[fsm.return_idx], _ = _sample_score_cand(fsm.return_idx)
            if record_history:
                last_cand_snapshot = cand_buf.copy()

            # 5e') Classify the encounter for this commit.  The
            # decision-point gate fires exactly when a maneuver is about
            # to be (re-)committed this step, so every committed escape —
            # the first engage from ROUTE / RETURNING and each
            # closed-loop re-stack while AVOIDING — gets its own
            # classification.  The four kinematic inputs are the CPA of
            # the currently-flown (composed) route candidate against the
            # intruder, so a re-stack re-classifies the *stacked*
            # geometry, not the original one.  Done BEFORE ``fsm.step``
            # so the FSM's case-aware policy has the compliant-action set
            # in hand for this commit.  Returns never pass through here,
            # so they never classify.
            ec_now = classify_encounter(
                own_pos_cpa  = own_pos_cpa_step,
                own_vel_cpa  = own_vel_cpa_step,
                intr_pos_cpa = intr_pos_cpa_step,
                intr_vel_cpa = intr_vel_cpa_step,
                own_category = own_cat,
                intr_category= intr_cat,
                alt_min_m   = alt_min_m,
                alt_max_m   = alt_max_m,
                alt_margin_m= alt_margin_m,
                n_alerting   = n_alerting_in,
                same_level_ft= cyl_h / 2.0,
            )
            encounter_classes.append(ec_now)
            fsm.compliant_action_names = ec_now.compliant_actions
        prof.lap('5e_timers_decision')

        flown_idx_now = fsm.step(t_now=t_now, p0=own_pos, v0=own_vel,
                                 track_point=track_point,
                                 ds=ds, step_idx=len(hist['times']),
                                 sim=sim,
                                 own_vel_cpa=own_vel_cpa_cur,
                                 cpa_ctx=cpa_ctx,
                                 track_valid=est_active,
                                 cand_positions=cand_buf,
                                 periodic_eval=periodic_due)

        # Carry this step's CPA heading to the next step's candidate
        # preview so the lateral escapes stay oriented to the starboard /
        # port perpendicular of the CPA heading before the next commit.
        own_vel_cpa_prev = own_vel_cpa_cur
        prof.lap('5e_fsm_step')

        # 5f) Record this step into history
        hist['times'        ].append(times[i])
        hist['own_pos'      ].append(own_pos.copy())
        hist['intr_true_pos'].append(intr_p.copy())
        hist['d_candidates' ].append(ds)
        hist['alert'        ].append(alert_now)
        hist['in_maneuver'  ].append(fsm.state != fsm.ROUTE)
        hist['flown_idx'    ].append(flown_idx_now if fsm.state != fsm.ROUTE else -1)
        hist['sweep_taus'   ].append(out_t.copy())
        hist['track_point'  ].append(np.asarray(track_point,
                                                dtype=np.float64).copy())
        hist['cpa_own_pos'  ].append(own_pos_cpa_step)
        hist['cpa_intr_pos' ].append(intr_pos_cpa_step)
        # Whether the EKF holds an active track on the intruder this step.
        # Unlike raw FOV visibility, this accounts for the estimator
        # lifecycle: it only turns True after the init warm-up
        # (``init_window`` consecutive sightings) and stays True while
        # coasting through brief occlusions, dropping only after
        # ``track_timeout_s`` without a sighting.  Combined with the
        # flown-trajectory LoWC at the end to flag encounters whose loss
        # of well-clear happened while the intruder was not being tracked.
        hist['tracking'     ].append(bool(est_active))
        # Estimator lifecycle flags for the tracking-state panel: whether
        # the intruder is currently inside the camera FOV, and whether a
        # track has been bootstrapped (started, even if not yet active).
        hist['in_fov'       ].append(bool(visible))
        hist['est_started'  ].append(bool(est_started))
        # FOV-loss safe point — recorded only on the steps where the gate
        # is actually holding back the return (NaN otherwise), so the
        # visualiser shows the marker only while it is in use.
        if fsm._safe_point_active and fsm._safe_point is not None:
            hist['safe_point' ].append(fsm._safe_point.copy())
            hist['safe_point_active'].append(True)
        else:
            hist['safe_point' ].append(np.full(3, np.nan))
            hist['safe_point_active'].append(False)
        if record_history:
            if est_started:
                _est_state, _est_P, _est_acc = sim.est_get_state(
                    state_out=_est_state_buf, P_out=_est_P_buf,
                    accel_var_out=_est_acc_buf)
                intr_est_pos_step = _est_state[:3].copy()
                intr_est_P_step   = _est_P[:3, :3].copy()
                # Per-axis velocity / acceleration variances (diagonal).
                # Velocity variance is the (3,4,5) diagonal of the 6x6
                # block; acceleration variance comes from the dedicated
                # accel output (zero for the CV model).
                intr_est_vel_var_step = np.array(
                    [_est_P[3, 3], _est_P[4, 4], _est_P[5, 5]])
                intr_est_acc_var_step = _est_acc.copy()
            else:
                # No track bootstrapped yet (or dropped after timeout):
                # record the intruder estimate as NaN so the visualiser
                # leaves a gap rather than drawing a stale or fabricated
                # track.
                intr_est_pos_step = np.full(3, np.nan)
                intr_est_P_step   = np.full((3, 3), np.nan)
                intr_est_vel_var_step = np.full(3, np.nan)
                intr_est_acc_var_step = np.full(3, np.nan)
            hist['own_vel'        ].append(own_vel.copy())
            hist['own_att'        ].append(own_att.copy())
            hist['intr_est_pos'   ].append(intr_est_pos_step)
            hist['intr_est_P'     ].append(intr_est_P_step)
            hist['intr_est_vel_var'].append(intr_est_vel_var_step)
            hist['intr_est_acc_var'].append(intr_est_acc_var_step)
            # Candidate trajectories are no longer sampled every step;
            # record the most recent full-evaluation snapshot (carried
            # forward) so the visualiser shows them fixed in place from
            # the instant they were computed.  Before the first
            # evaluation there is nothing to show — record a 1-sample NaN
            # placeholder so the per-step list stays well-formed.
            if last_cand_snapshot is not None:
                hist['cand_positions'].append(last_cand_snapshot)
            else:
                hist['cand_positions'].append(
                    np.full((n_gen, 1, 3), np.nan, dtype=np.float64))
            # The currently-flown trajectory (slot 0) IS recomputed every
            # step, so record it live — independent of the carried
            # alternative-candidate snapshot — so the current trajectory
            # and its lookahead-end protection cylinder always render.
            hist['flown_lookahead'].append(cand_buf[0].copy())
            # The return-to-route candidate is sampled only while a return
            # path is being evaluated; record it live when present so the
            # visualiser draws it (and its end cylinder), else a NaN
            # placeholder so those frames draw nothing.
            if cands[fsm.return_idx] is not None:
                hist['return_lookahead'].append(cand_buf[fsm.return_idx].copy())
            else:
                hist['return_lookahead'].append(
                    np.full((1, 3), np.nan, dtype=np.float64))
            hist['int_pred_pos'   ].append(int_pos_buf.copy())
            hist['int_pred_P'     ].append(int_cov_buf.copy())
            # Active route transform committed this step (after
            # ``fsm.step`` applied it): [shift_n, shift_e, shift_d,
            # speed_scale, mode, vel_n, vel_e, vel_d].  Drives the
            # visualiser's route_xf panel.  The velocity is recorded only
            # while the transform holds a constant velocity
            # (HOLD_VELOCITY); NaN otherwise so the angle trace shows gaps.
            _axf = fsm.active_xf
            if int(_axf.mode) == HOLD_VELOCITY and _axf.velocity is not None:
                _vel = np.asarray(_axf.velocity,
                                  dtype=np.float64).reshape(3)
            else:
                _vel = np.full(3, np.nan, dtype=np.float64)
            hist['route_xf'].append(
                np.array([_axf.shift[0], _axf.shift[1], _axf.shift[2],
                          _axf.speed_scale, float(_axf.mode),
                          _vel[0], _vel[1], _vel[2]],
                         dtype=np.float64))
        prof.lap('5f_record')

        # 5g) Roll the ownship's real flight forward to step i+1 by
        # advancing the simulator one ``dt`` under whatever route
        # transform the state machine committed this step (``fsm.step``
        # applies ``set_route_xf`` *before* this call, so it takes effect
        # here).  ``sim.step`` returns the new ownship position, velocity
        # and route track point, which become the live state for the next
        # iteration.
        if i + 1 < T_total:
            cur_pos, cur_vel, cur_track = sim.step()
        prof.lap('5g_sim_step')

    prof.report()

    # ---- 6) Counterfactual evaluation against ground truth -------------
    own_flown  = np.asarray(hist['own_pos'],       dtype=np.float64)
    intr_flown = np.asarray(hist['intr_true_pos'], dtype=np.float64)
    cf = _compute_classification(
        times=times, own_route_dense=own_route_flown, intr_true=intr_true,
        own_flown=own_flown, intr_flown=intr_flown,
        cyl_h=cyl_h, cyl_d=cyl_d,
        triggered=(fsm.maneuver_idx >= 0),
    )
    cf['target_own_pos'] = own_wp_p.copy()

    # ---- 7) Pack history ----
    def _arr(name, dtype=np.float64):
        return np.asarray(hist[name], dtype=dtype)

    def _empty_like(shape, dtype=np.float64):
        return np.empty(shape, dtype=dtype)

    K = len(candidate_names)

    # When history was not recorded, fill the heavy fields with empty
    # arrays of the right rank so downstream code can still introspect
    # them (shape[0] == 0 signals "no history").
    if record_history:
        own_vel_arr     = _arr('own_vel')
        own_att_arr     = _arr('own_att')
        intr_est_pos_a  = _arr('intr_est_pos')
        intr_est_P_a    = _arr('intr_est_P')
        intr_est_vel_var_a = _arr('intr_est_vel_var')
        intr_est_acc_var_a = _arr('intr_est_acc_var')
        cand_pos_a      = list(hist['cand_positions'])
        flown_la_a      = list(hist['flown_lookahead'])
        return_la_a     = list(hist['return_lookahead'])
        int_pred_pos_a  = list(hist['int_pred_pos'])
        int_pred_P_a    = list(hist['int_pred_P'])
        route_xf_a      = _arr('route_xf')
    else:
        own_vel_arr     = _empty_like((0, 3))
        own_att_arr     = _empty_like((0, 3))
        intr_est_pos_a  = _empty_like((0, 3))
        intr_est_P_a    = _empty_like((0, 3, 3))
        intr_est_vel_var_a = _empty_like((0, 3))
        intr_est_acc_var_a = _empty_like((0, 3))
        cand_pos_a      = []
        flown_la_a      = []
        return_la_a     = []
        int_pred_pos_a  = []
        int_pred_P_a    = []
        route_xf_a      = _empty_like((0, 8))

    # Non-tracked LoWC flag: any flown-trajectory loss of well-clear
    # (``cyldist_maneuver < 1``) that coincides with the EKF *not* holding
    # an active track on that same step, i.e. the intruder was not being
    # tracked when separation was lost (track not yet initialised, or
    # dropped after the post-FOV-loss coast timed out).
    tracking_arr     = _arr('tracking', dtype=bool)
    cyldist_m_arr    = np.asarray(cf['cyldist_maneuver'], dtype=np.float64)
    nontracked_lowc  = bool(np.any((cyldist_m_arr < 1.0) & ~tracking_arr))

    return AvoidanceResult(
        times          = _arr('times'),
        sweep_taus     = list(hist['sweep_taus']),
        own_pos        = _arr('own_pos'),
        own_vel        = own_vel_arr,
        own_att        = own_att_arr,
        intr_true_pos  = _arr('intr_true_pos'),
        intr_est_pos   = intr_est_pos_a,
        intr_est_P     = intr_est_P_a,
        intr_est_vel_var = intr_est_vel_var_a,
        intr_est_acc_var = intr_est_acc_var_a,
        candidate_names= candidate_names,
        cand_positions = cand_pos_a,
        flown_lookahead= flown_la_a,
        return_lookahead= return_la_a,
        route_xf       = route_xf_a,
        d_candidates   = _arr('d_candidates'),
        int_pred_pos   = int_pred_pos_a,
        int_pred_P     = int_pred_P_a,
        track_point    = _arr('track_point'),
        cpa_own_pos    = _arr('cpa_own_pos'),
        cpa_intr_pos   = _arr('cpa_intr_pos'),
        alert          = _arr('alert', dtype=bool),
        in_maneuver    = _arr('in_maneuver', dtype=bool),
        flown_idx      = _arr('flown_idx', dtype=int),
        maneuver_idx   = int(fsm.maneuver_idx),
        maneuver_start = int(fsm.maneuver_start),
        n_commits      = int(fsm.n_commits),
        committed_names= tuple(fsm.committed_names),
        safe_point     = (None if fsm._safe_point is None
                          else fsm._safe_point.copy()),
        safe_point_series = _arr('safe_point'),
        safe_point_active = _arr('safe_point_active', dtype=bool),
        tracking       = tracking_arr,
        in_fov         = _arr('in_fov', dtype=bool),
        est_started    = _arr('est_started', dtype=bool),
        encounter      = (encounter_classes[0] if encounter_classes
                          else None),
        encounters     = tuple(encounter_classes),
        nontracked_lowc= nontracked_lowc,
        cyl_h          = float(cyl_h),
        cyl_d          = float(cyl_d),
        alert_threshold= float(alert_threshold),
        maneuver_family= str(maneuver_family),
        **cf,
    )


# ---------------------------------------------------------------------------
# Convenience: build a fixed parameter spec from a single integer seed
# ---------------------------------------------------------------------------

def make_spec_from_seed(seed: int) -> dict:
    """Draw a single random encounter spec deterministically from ``seed``.

    Re-uses ``sw_montecarlo.run_montecarlo.sample_param_spec`` so the
    generated encounters are identical to what the Monte Carlo harness
    would draw with the same master seed.
    """
    from daa_montecarlo.run_montecarlo import sample_param_spec
    rng = np.random.default_rng(int(seed))
    return sample_param_spec(rng)


# ---------------------------------------------------------------------------
# Convenience: run a simulation directly from a Monte-Carlo parameter spec
# ---------------------------------------------------------------------------

def _track_to_waypoints(track: dict, *, positive_up: bool):
    """Convert one encounter ``track`` dict to a (T, 4) waypoint array
    ``[t, N, E, D]``.

    The encounter generator returns NED with ``up_ft`` (positive up, feet);
    positions are converted to metres (FT_TO_M) and the up axis is flipped
    to NED-down convention when ``positive_up=True``.
    """
    t = np.asarray(track['time'],     dtype=np.float64).reshape(-1)
    n = np.asarray(track['north_ft'], dtype=np.float64).reshape(-1) * FT_TO_M
    e = np.asarray(track['east_ft'],  dtype=np.float64).reshape(-1) * FT_TO_M
    u = np.asarray(track['up_ft'],    dtype=np.float64).reshape(-1) * FT_TO_M
    d = -u if positive_up else u
    K = min(t.size, n.size, e.size, d.size)
    return np.column_stack([t[:K], n[:K], e[:K], d[:K]])


def run_simulation_from_spec(spec: dict, **kwargs) -> AvoidanceResult:
    """Run a simulation from a Monte-Carlo parameter spec.

    Thin wrapper that calls the encounter generator, extracts the
    sparse-but-dense ownship and intruder waypoint lists from the
    resulting tracks (the route tracker handles dense input fine), and
    delegates to :func:`run_simulation`.  Forwards every keyword
    argument to that function.

    The ownship initial velocity is taken from the first sample of
    the ownship track (speed + Euler angles); the encounter
    categories are forwarded as ``own_category`` / ``intr_category``
    so the encounter classifier can reason about right-of-way.
    """
    _, _, encounter = generate_single_encounter(spec)
    own_track  = encounter[0]
    intr_track = encounter[1]
    own_wps  = _track_to_waypoints(own_track,  positive_up=True)
    intr_wps = _track_to_waypoints(intr_track, positive_up=True)

    spd0   = float(np.asarray(own_track['speed_ftps'])[0]) * FT_TO_M  # ft/s -> m/s
    psi0   = float(np.asarray(own_track['psi_rad'])[0])
    theta0 = float(np.asarray(own_track['theta_rad'])[0])
    horiz0 = spd0 * np.cos(theta0)
    own_init_vel = np.array([
        horiz0 * np.cos(psi0),
        horiz0 * np.sin(psi0),
        -spd0 * np.sin(theta0),   # NED down
    ], dtype=np.float64)

    return run_simulation(
        own_waypoints  = own_wps,
        own_init_vel   = own_init_vel,
        intr_waypoints = intr_wps,
        own_category   = str(spec.get('Ownship_category',  '')),
        intr_category  = str(spec.get('Intruder_category', '')),
        **kwargs,
    )
