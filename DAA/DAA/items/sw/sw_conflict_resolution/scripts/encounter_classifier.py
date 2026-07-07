#!/usr/bin/env python3
"""
Encounter classification.

Implements the case-selection logic described in
``encounter_cases.md`` (sibling of this file).  Given an ownship and
intruder kinematic state (position + velocity in NED) plus a few
contextual flags (ownship altitude band, intruder
type and number of alerting intruders), returns the
matching case (1..16), the prescribed avoidance manoeuvre tag, the
diagnostic variables used by the decision, and a tuple of candidate-
generator names compliant with that manoeuvre (for the FSM).

The classifier is intended to be invoked at the moment a conflict is
declared (first alert), using the *estimated* intruder state — this is
the geometry the avoidance logic is reacting to, not the
encounter-generation-time geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Thresholds (encounter_cases.md §"Thresholds")
# ---------------------------------------------------------------------------

TH_COALT_M           =  60.96  # |delta_h| co-altitude band
TH_HEADON_DEG        =  15.0   # head-on tolerance around 180°
TH_OVERTAKE_DEG      =  70.0   # overtake cone (track diff and bearing)
TH_CONVERGE_LO_DEG   =  70.0   # lower bound of the converging band
TH_CONVERGE_HI_DEG   = 110.0   # upper bound of the converging band
TH_AHEAD_DEG         =  90.0   # ahead / behind split on bearing_rel


# ---------------------------------------------------------------------------
# Intruder categories flagged as "reduced manoeuvrability" (Case 4).
# Empty by default — the simulator's category set is exclusively
# powered HTA — but the classifier honours the flag if it is set
# explicitly or if the category appears in this set.
# ---------------------------------------------------------------------------

LOW_MANVR_CATEGORIES = frozenset({
    'BAL',   # balloon
    'GLD',   # glider
    'ARS',   # airship
    'SLG',   # slung-load helicopter operation
    'TOW',   # aircraft towing an object
})


# ---------------------------------------------------------------------------
# Manoeuvre tags (encounter_cases.md §"Avoidance manoeuvres")
# ---------------------------------------------------------------------------

M_TURN_RIGHT         = 'M_TURN_RIGHT'
M_TURN_LEFT          = 'M_TURN_LEFT'
M_TURN_RIGHT_OR_SLOW = 'M_TURN_RIGHT_OR_SLOW'
M_VACATE_LATERAL     = 'M_VACATE_LATERAL'
M_REDUCE_SPEED       = 'M_REDUCE_SPEED'
M_DESCEND            = 'M_DESCEND'
M_LATERAL_OR_CLIMB   = 'M_LATERAL_OR_CLIMB'
M_LATERAL_OR_DESCEND = 'M_LATERAL_OR_DESCEND'
M_HOLD_TRACK         = 'M_HOLD_TRACK'

# Mapping from manoeuvre tag to the candidate-generator names the
# state machine treats as compliant.  The default candidate set in
# ``candidate_trajectories.default_generators`` exposes ``maintain``,
# ``right_shift``, ``left_shift``, ``descend``, ``climb`` and
# ``slow_down`` as avoidance options.
_MANEUVER_COMPLIANT_ACTIONS: Mapping[str, Tuple[str, ...]] = {
    M_TURN_RIGHT:         ('right_shift',),
    M_TURN_LEFT:          ('left_shift',),
    M_TURN_RIGHT_OR_SLOW: ('right_shift', 'slow_down'),
    M_VACATE_LATERAL:     ('right_shift', 'left_shift'),
    M_REDUCE_SPEED:       ('slow_down',),
    M_DESCEND:            ('descend',),
    M_LATERAL_OR_CLIMB:   ('right_shift', 'climb'),
    M_LATERAL_OR_DESCEND: ('right_shift', 'descend'),
    M_HOLD_TRACK:         ('maintain',),
}


# ---------------------------------------------------------------------------
# Case metadata: short geometry tag per case id.
# ---------------------------------------------------------------------------

_CASE_GEOMETRY: Mapping[int, str] = {
    1:  'head_on',
    2:  'converging_right',
    3:  'converging_left',
    4:  'low_manoeuvrability',
    5:  'overtaking',
    6:  'being_overtaken',
    10: 'vertical_above',
    11: 'vertical_below',
    12: 'crossing_ahead',
    13: 'crossing_behind',
    14: 'near_ceiling',
    15: 'near_floor',
    16: 'multiple_intruders',
}

# Case 13 (crossing behind, separation opening) is the only case in
# which the UAS holds track and is not under a give-way obligation.
_HOLD_TRACK_CASES = frozenset({13})

# Default vertical clearance (m) used to decide whether the ownship is
# "near" a flight-envelope altitude limit.  An escape that would change
# the altitude by this much is barred when it would bust the limit, so
# the natural value mirrors the nominal climb/descend candidate
# displacement (the configured vertical-shift ratio times the cylinder
# half-height).  The simulator overrides it per-run with that nominal
# vertical shift.
DEFAULT_ALT_MARGIN_M = 213.36


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EncounterClassification:
    """Result of the 16-case classification at conflict time.

    Attributes
    ----------
    case_id:
        Matching case (1..16); 0 when the encounter is undetermined
        (e.g. one of the tracks is stationary).
    case_name:
        Short geometry tag for ``case_id`` (see ``_CASE_GEOMETRY``).
    maneuver:
        Prescribed manoeuvre tag (``M_TURN_RIGHT``, ``M_DESCEND``, ...).
    delta_psi_deg:
        Crossing angle |ψ_int − ψ_own|, folded to [0°, 180°].
    bearing_rel_deg:
        Signed relative bearing of the intruder from the ownship nose,
        in (−180°, +180°].  Positive = on the right.
    delta_h_m:
        Relative altitude ``h_int − h_own`` in metres, positive when the
        intruder is above the ownship.
    cpa_trend:
        ``'closing'`` when the range is shrinking at the detection
        instant, ``'opening'`` otherwise, ``'undetermined'`` when the
        relative motion is below threshold.
    geometry, crossing_angle_deg, relative_bearing_deg,
    intruder_on_right, same_level, own_gives_way,
    compliant_actions:
        Legacy fields kept for downstream consumers (visualiser,
        GUI summary, avoidance state machine).
    """

    # ---- New 16-case fields ----
    case_id:               int
    case_name:             str
    maneuver:              str
    delta_psi_deg:         float
    bearing_rel_deg:       float
    delta_h_m:             float
    cpa_trend:             str
    own_pos_cpa:           Tuple[float, float, float]
    intr_pos_cpa:          Tuple[float, float, float]

    # ---- Legacy fields ----
    geometry:              str
    crossing_angle_deg:    float
    relative_bearing_deg:  float
    intruder_on_right:     bool
    same_level:            bool
    own_gives_way:         bool
    compliant_actions:     Tuple[str, ...]



# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------

def _horizontal_unit(v: np.ndarray) -> Tuple[np.ndarray, float]:
    """Return ``(horizontal unit vector, horizontal speed)`` for NED ``v``.

    Returns a zero vector when the horizontal speed is below 1e-6 m/s.
    """
    vh = np.array([float(v[0]), float(v[1])], dtype=np.float64)
    sp = float(np.hypot(vh[0], vh[1]))
    if sp < 1e-6:
        return np.zeros(2, dtype=np.float64), 0.0
    return vh / sp, sp


def _signed_angle_deg(fwd: np.ndarray, target: np.ndarray) -> float:
    """Signed angle (deg) from ``fwd`` to ``target`` in the NE plane.

    Positive = clockwise = target is on the right of ``fwd``.
    """
    right  = np.array([-fwd[1], fwd[0]])
    dot_f  = float(fwd[0]   * target[0] + fwd[1]   * target[1])
    dot_r  = float(right[0] * target[0] + right[1] * target[1])
    return float(np.degrees(np.arctan2(dot_r, dot_f)))


def _cpa_trend(rel_pos: np.ndarray, rel_vel: np.ndarray) -> str:
    """``'closing'`` / ``'opening'`` / ``'undetermined'`` from rel kinematics.

    Sign of d(range)/dt is the sign of ``rel_pos · rel_vel``: negative
    means range is shrinking.
    """
    rng = float(np.linalg.norm(rel_pos))
    spd = float(np.linalg.norm(rel_vel))
    if rng < 1e-6 or spd < 1e-6:
        return 'undetermined'
    rdot = float(np.dot(rel_pos, rel_vel))
    return 'closing' if rdot < 0.0 else 'opening'


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _build_result(*,
                  case_id:        int,
                  maneuver:       str,
                  delta_psi_deg:  float,
                  bearing_rel:    float,
                  delta_h_m:     float,
                  cpa_trend:      str,
                  same_level:     bool,
                  own_pos_cpa:    Tuple[float, float, float] = (float('nan'),) * 3,
                  intr_pos_cpa:   Tuple[float, float, float] = (float('nan'),) * 3,
                  ) -> EncounterClassification:
    case_name        = _CASE_GEOMETRY.get(case_id, 'undetermined')
    own_gives_way    = (case_id != 0) and (case_id not in _HOLD_TRACK_CASES)
    intruder_on_right = (not np.isnan(bearing_rel)) and bearing_rel > 0.0
    compliant_actions = _MANEUVER_COMPLIANT_ACTIONS.get(maneuver, ('maintain',))
    return EncounterClassification(
        case_id              = int(case_id),
        case_name            = case_name,
        maneuver             = maneuver,
        delta_psi_deg        = float(delta_psi_deg),
        bearing_rel_deg      = float(bearing_rel),
        delta_h_m            = float(delta_h_m),
        cpa_trend            = cpa_trend,
        own_pos_cpa          = tuple(float(v) for v in own_pos_cpa),
        intr_pos_cpa         = tuple(float(v) for v in intr_pos_cpa),
        geometry             = case_name,
        crossing_angle_deg   = float(delta_psi_deg),
        relative_bearing_deg = float(bearing_rel),
        intruder_on_right    = bool(intruder_on_right),
        same_level           = bool(same_level),
        own_gives_way        = bool(own_gives_way),
        compliant_actions    = compliant_actions,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def classify_encounter(*,
                       own_pos_cpa:    np.ndarray,
                       own_vel_cpa:    np.ndarray,
                       intr_pos_cpa:   np.ndarray,
                       intr_vel_cpa:   np.ndarray,
                       own_category:   str = '',
                       intr_category:  str = '',
                       n_alerting:     int  = 1,
                       intr_low_manvr: Optional[bool] = None,
                       alt_min_m:     float = float('-inf'),
                       alt_max_m:     float = float('inf'),
                       alt_margin_m:  float = DEFAULT_ALT_MARGIN_M,
                       same_level_m:  float = TH_COALT_M,
                       head_on_band_deg:    float = TH_HEADON_DEG,
                       overtake_band_deg:   float = TH_OVERTAKE_DEG,
                       converge_lo_deg:     float = TH_CONVERGE_LO_DEG,
                       converge_hi_deg:     float = TH_CONVERGE_HI_DEG,
                       ahead_band_deg:      float = TH_AHEAD_DEG,
                       **_unused,
                       ) -> EncounterClassification:
    """Pick the matching case (1..16) for an ownship/intruder pair.

    All four kinematic inputs are evaluated **at the predicted point
    of closest approach** (CPA), in NED (m, m/s):

      * ``own_pos_cpa``  / ``intr_pos_cpa``  — positions at CPA;
      * ``own_vel_cpa``  / ``intr_vel_cpa``  — velocities at CPA.

    Positions come from the C++ side (``min_1sigma_cylinder_distance``'s
    ``idx_cpa``) and velocities are typically a finite difference of
    the route candidate (own) and the propagated intruder mean around
    that index.  Δψ and ``bearing_rel`` are derived from the velocity
    pair so they reflect the body-X axis at CPA (the correct
    convention when the ownship route is turning inside the
    lookahead horizon).

    The ownship altitude band (Cases 14 / 15) is no longer supplied
    directly: it is derived from the ownship
    altitude at CPA (``-own_pos_cpa[2]``, m AGL) against the
    flight-envelope limits ``alt_min_m`` / ``alt_max_m`` (m AGL,
    positive-up).  A climb is barred (``near_ceiling`` → Case 14) when
    a climb of ``alt_margin_m`` would reach or exceed ``alt_max_m``;
    a descent is barred (``near_floor`` → Case 15) when a descent of
    ``alt_margin_m`` would reach or drop below ``alt_min_m``.  The
    defaults (``alt_max_m = +inf`` / ``alt_min_m = -inf``) disable
    the band so every encounter stays at its nominal case.  When
    ``intr_low_manvr`` is ``None``, the flag is derived from
    ``intr_category`` against :data:`LOW_MANVR_CATEGORIES`.

    Unknown keyword arguments are silently accepted so the call site
    can keep passing legacy kwargs (e.g. ``priority_map``) without
    breaking.
    """
    own_pos_cpa  = np.asarray(own_pos_cpa,  dtype=np.float64)
    own_vel_cpa  = np.asarray(own_vel_cpa,  dtype=np.float64)
    intr_pos_cpa = np.asarray(intr_pos_cpa, dtype=np.float64)
    intr_vel_cpa = np.asarray(intr_vel_cpa, dtype=np.float64)

    own_fwd,  own_sp  = _horizontal_unit(own_vel_cpa)
    intr_fwd, intr_sp = _horizontal_unit(intr_vel_cpa)

    # Crossing angle between tracks, folded to [0, 180].
    if own_sp > 0.0 and intr_sp > 0.0:
        delta_psi = abs(_signed_angle_deg(own_fwd, intr_fwd))
        delta_psi = min(delta_psi, 360.0 - delta_psi)
    else:
        delta_psi = float('nan')

    # Vertical: in NED, +z is down, so above-ownship means intr_z < own_z.
    delta_h_m = float(own_pos_cpa[2] - intr_pos_cpa[2])   # +ve = intr above
    same_level = abs(delta_h_m) <= float(same_level_m)

    # Ownship altitude at CPA, m AGL (positive-up): D is positive-down.
    own_alt_m = -float(own_pos_cpa[2])

    rel_pos_h_cpa = intr_pos_cpa[:2] - own_pos_cpa[:2]
    # cpa_trend: closing vs opening of horizontal range at CPA.  At
    # CPA itself d(range)/dt is ≈0 by construction, so the sign
    # reported here tells whether the geometry is still closing just
    # past the lookahead horizon (when idx_cpa is the interior
    # minimum) or already opening.
    cpa_trend = _cpa_trend(
        intr_pos_cpa - own_pos_cpa,
        intr_vel_cpa - own_vel_cpa,
    )

    # Relative bearing of intruder from ownship nose at CPA.
    if own_sp > 0.0:
        bearing_rel = _signed_angle_deg(own_fwd, rel_pos_h_cpa)
    else:
        bearing_rel = float('nan')

    # Lateral (starboard) component of the horizontal *relative
    # velocity* at CPA.  Positive when the intruder is moving toward
    # the ownship starboard side.  Used to split the converging band
    # (Cases 2 / 3): at CPA the relative-position vector is nearly
    # perpendicular to the relative velocity, so its bearing sign is
    # dominated by ``idx_cpa`` quantisation noise, whereas the
    # velocities are smooth filter states.  ``own_right`` is the
    # starboard unit vector of the ownship heading.
    if own_sp > 0.0 and intr_sp > 0.0:
        own_right = np.array([-own_fwd[1], own_fwd[0]], dtype=np.float64)
        rel_vel_h = intr_vel_cpa[:2] - own_vel_cpa[:2]
        rel_vel_lat = float(own_right[0] * rel_vel_h[0]
                            + own_right[1] * rel_vel_h[1])
    else:
        rel_vel_lat = float('nan')

    if intr_low_manvr is None:
        intr_low_manvr = str(intr_category) in LOW_MANVR_CATEGORIES

    # Bind the CPA positions onto a local builder so every case
    # branch below records them in the result without repetition.
    _own_cpa_tup  = tuple(float(v) for v in own_pos_cpa)
    _intr_cpa_tup = tuple(float(v) for v in intr_pos_cpa)
    def _build(**kwargs):
        kwargs.setdefault('own_pos_cpa',  _own_cpa_tup)
        kwargs.setdefault('intr_pos_cpa', _intr_cpa_tup)
        return _build_result(**kwargs)

    # ------------------------------------------------------------------
    # Priority-ordered case selection (encounter_cases.md §"Notes").
    # ------------------------------------------------------------------

    # Case 16 — multiple intruders / secondary-conflict risk.
    if int(n_alerting) >= 2:
        return _build(
            case_id=16, maneuver=M_VACATE_LATERAL,
            delta_psi_deg=delta_psi, bearing_rel=bearing_rel,
            delta_h_m=delta_h_m, cpa_trend=cpa_trend,
            same_level=same_level,
        )

    # Case 4 — reduced-manoeuvrability intruder.
    if intr_low_manvr:
        return _build(
            case_id=4, maneuver=M_TURN_RIGHT,
            delta_psi_deg=delta_psi, bearing_rel=bearing_rel,
            delta_h_m=delta_h_m, cpa_trend=cpa_trend,
            same_level=same_level,
        )

    # Cases 10 / 11 — vertical encounters (intruder above / below).
    if not same_level:
        if delta_h_m > 0.0:
            case_id, maneuver = 10, M_DESCEND
        else:
            case_id, maneuver = 11, M_LATERAL_OR_CLIMB
        return _apply_alt_band(_build(
            case_id=case_id, maneuver=maneuver,
            delta_psi_deg=delta_psi, bearing_rel=bearing_rel,
            delta_h_m=delta_h_m, cpa_trend=cpa_trend,
            same_level=same_level,
        ), own_alt_m, alt_min_m, alt_max_m, alt_margin_m)

    # ------------------------------------------------------------------
    # From here on: co-altitude horizontal classification.
    # Requires both tracks to be well-defined.
    # ------------------------------------------------------------------
    if own_sp <= 0.0 or intr_sp <= 0.0:
        return _build(
            case_id=0, maneuver=M_HOLD_TRACK,
            delta_psi_deg=delta_psi, bearing_rel=bearing_rel,
            delta_h_m=delta_h_m, cpa_trend=cpa_trend,
            same_level=same_level,
        )

    # Case 1 — head-on or near head-on.
    if delta_psi >= (180.0 - float(head_on_band_deg)):
        return _apply_alt_band(_build(
            case_id=1, maneuver=M_TURN_RIGHT,
            delta_psi_deg=delta_psi, bearing_rel=bearing_rel,
            delta_h_m=delta_h_m, cpa_trend=cpa_trend,
            same_level=same_level,
        ), own_alt_m, alt_min_m, alt_max_m, alt_margin_m)

    # Cases 5 / 6 — same-direction overtakes.
    if delta_psi <= float(overtake_band_deg):
        # Overtake direction is decided from the *speed* comparison
        # rather than the intruder bearing: on aligned tracks the
        # faster aircraft is necessarily the one closing from behind,
        # so the slower aircraft is ahead of it.  At CPA the two are
        # abeam (``bearing_rel`` ≈ ±90°), so the old ``abs_brg`` gate
        # rode on ``idx_cpa`` quantisation noise and could drop a true
        # overtake into the crossing-behind branch.  ``bearing_rel`` is
        # still reported for diagnostics.
        if own_sp > intr_sp:
            return _apply_alt_band(_build(
                case_id=5, maneuver=M_TURN_RIGHT_OR_SLOW,
                delta_psi_deg=delta_psi, bearing_rel=bearing_rel,
                delta_h_m=delta_h_m, cpa_trend=cpa_trend,
                same_level=same_level,
            ), own_alt_m, alt_min_m, alt_max_m, alt_margin_m)
        if intr_sp > own_sp:
            return _apply_alt_band(_build(
                case_id=6, maneuver=M_TURN_RIGHT,
                delta_psi_deg=delta_psi, bearing_rel=bearing_rel,
                delta_h_m=delta_h_m, cpa_trend=cpa_trend,
                same_level=same_level,
            ), own_alt_m, alt_min_m, alt_max_m, alt_margin_m)
        # Aligned tracks at equal speed (flying in formation) — fall
        # through to converging / crossing logic below.

    # Cases 2 / 3 — converging band.  The give-way side is decided
    # from the *relative-velocity* lateral sign rather than the
    # intruder bearing: the intruder crossing right→left across the
    # nose (relative velocity pointing to port, ``rel_vel_lat < 0``)
    # is passed astern by turning right (Case 2); left→right
    # (``rel_vel_lat > 0``) by turning left (Case 3).  This is stable
    # against the CPA-index quantisation that makes ``bearing_rel``
    # collapse to ≈±90° in this band.
    if (float(converge_lo_deg) <= delta_psi <= float(converge_hi_deg)):
        if rel_vel_lat < 0.0:
            return _apply_alt_band(_build(
                case_id=2, maneuver=M_TURN_RIGHT,
                delta_psi_deg=delta_psi, bearing_rel=bearing_rel,
                delta_h_m=delta_h_m, cpa_trend=cpa_trend,
                same_level=same_level,
            ), own_alt_m, alt_min_m, alt_max_m, alt_margin_m)
        return _apply_alt_band(_build(
            case_id=3, maneuver=M_TURN_LEFT,
            delta_psi_deg=delta_psi, bearing_rel=bearing_rel,
            delta_h_m=delta_h_m, cpa_trend=cpa_trend,
            same_level=same_level,
        ), own_alt_m, alt_min_m, alt_max_m, alt_margin_m)

    # Cases 12 / 13 — crossing ahead / behind (the remaining
    # co-altitude geometries).  Ahead+closing → 12; otherwise 13.
    if abs(bearing_rel) <= float(ahead_band_deg) and cpa_trend == 'closing':
        return _apply_alt_band(_build(
            case_id=12, maneuver=M_TURN_RIGHT,
            delta_psi_deg=delta_psi, bearing_rel=bearing_rel,
            delta_h_m=delta_h_m, cpa_trend=cpa_trend,
            same_level=same_level,
        ), own_alt_m, alt_min_m, alt_max_m, alt_margin_m)
    return _build(
        case_id=13, maneuver=M_HOLD_TRACK,
        delta_psi_deg=delta_psi, bearing_rel=bearing_rel,
        delta_h_m=delta_h_m, cpa_trend=cpa_trend,
        same_level=same_level,
    )


# ---------------------------------------------------------------------------
# Altitude-band modifier (cases 14 / 15)
# ---------------------------------------------------------------------------

# Manoeuvres that include a climb component; forbidden when the ownship
# is near the VLL ceiling.
_CLIMB_MANEUVERS  = frozenset({M_LATERAL_OR_CLIMB})
# Manoeuvres that include a descent component; forbidden when the
# ownship is near the floor / terrain.
_DESCEND_MANEUVERS = frozenset({M_DESCEND, M_LATERAL_OR_DESCEND})


def _apply_alt_band(result: EncounterClassification,
                    own_alt_m: float,
                    alt_min_m: float,
                    alt_max_m: float,
                    alt_margin_m: float) -> EncounterClassification:
    """Convert the nominal case into Case 14 / 15 when an altitude limit bars it.

    The ownship altitude band is derived from the ownship altitude at
    CPA (``own_alt_m``, m AGL, positive-up) against the flight-
    envelope limits, rather than supplied as a discrete label:

    - ``near_ceiling`` (Case 14): a climb of ``alt_margin_m`` would
      reach or exceed ``alt_max_m``, so any manoeuvre that includes a
      climb is replaced with ``M_LATERAL_OR_DESCEND``.
    - ``near_floor`` (Case 15): a descent of ``alt_margin_m`` would
      reach or drop below ``alt_min_m``, so any manoeuvre that
      includes a descent is replaced with ``M_LATERAL_OR_CLIMB``.

    With the default limits (``alt_max_m = +inf`` / ``alt_min_m =
    -inf``) neither band ever triggers and the nominal case is
    returned unchanged.
    """
    near_ceiling = (own_alt_m + float(alt_margin_m)) >= float(alt_max_m)
    near_floor   = (own_alt_m - float(alt_margin_m)) <= float(alt_min_m)
    if near_ceiling and result.maneuver in _CLIMB_MANEUVERS:
        return _build_result(
            case_id=14, maneuver=M_LATERAL_OR_DESCEND,
            delta_psi_deg=result.delta_psi_deg,
            bearing_rel=result.bearing_rel_deg,
            delta_h_m=result.delta_h_m,
            cpa_trend=result.cpa_trend,
            same_level=result.same_level,
            own_pos_cpa=result.own_pos_cpa,
            intr_pos_cpa=result.intr_pos_cpa,
        )
    if near_floor and result.maneuver in _DESCEND_MANEUVERS:
        return _build_result(
            case_id=15, maneuver=M_LATERAL_OR_CLIMB,
            delta_psi_deg=result.delta_psi_deg,
            bearing_rel=result.bearing_rel_deg,
            delta_h_m=result.delta_h_m,
            cpa_trend=result.cpa_trend,
            same_level=result.same_level,
            own_pos_cpa=result.own_pos_cpa,
            intr_pos_cpa=result.intr_pos_cpa,
        )
    return result
