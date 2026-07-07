#!/usr/bin/env python3
"""
Candidate ownship maneuvers for the avoidance loop.

Each *candidate* describes one option the ownship may take.  In the
``DAA_simulator`` model the airframe's real flight is driven entirely
by the C++ simulator (``DAA_simulator.step``), which flies the
configured route under an active :class:`RouteTransform` (an affine
``shift`` + ``speed_scale`` applied to the route on the fly).  A candidate
is therefore, for the route-following maneuvers, *just a different
RouteTransform*:

  * the baseline / return candidates are the identity transform,
  * the lateral / vertical escapes are a non-zero ``shift``,
  * the speed-reduction escape is a ``speed_scale < 1``.

Evaluating a candidate is a single ``simulator.simulate(shift,
speed_scale, n_out)`` call that projects the look-ahead trajectory the
ownship would fly *from its current state* under that hypothetical
transform — it never mutates the simulator.  Committing a candidate is
``simulator.set_route_xf(shift, speed_scale)``; the simulator then freezes
that transform (so a lateral escape direction resolved once at commit
stays fixed for the rest of the maneuver) and the next
``simulator.step`` flies it.

Because the committed transform lives in the simulator, the generators
are **stateless** — there is no per-generator ``commit`` / ``reset``
machinery any more.

The avoidance contract is:

  * Per step, the avoidance loop calls ``g.sample(simulator=sim,
    n_out=M, own_vel_cpa=..., fwd_vel=..., cpa_ctx=...)`` on the
    candidates it needs and wraps each result in a
    :class:`CandidateTrajectory` (name + ``(M, 3)`` NED positions).
    ``own_vel_cpa`` (ownship velocity, NED, at the predicted CPA)
    orients the lateral escapes; ``fwd_vel`` (current ownship velocity)
    is the fallback heading when no CPA velocity is available;
    ``cpa_ctx`` (:class:`CpaContext`) carries the cylinder dimensions and
    the intruder covariance at the CPA used to size the ratio-based
    escapes.
  * To commit candidate ``g`` the loop / state machine calls
    ``sim.set_route_xf(*g.transform(own_vel_cpa=..., fwd_vel=...,
    cpa_ctx=...))``.

The first generator in the default list is the "do-nothing /
current-route" option (identity) that drives the alert; the remaining
generators are the alternatives, listed in order of preference, with
the return-to-route candidate last.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

import numpy as np


# ---------------------------------------------------------------------------
# Default tuning
# ---------------------------------------------------------------------------

# Escape-shift sizing is expressed as a *ratio* of the targeted
# (uncertainty-aware) protection-cylinder distance at the closest point of
# approach (CPA), not as a fixed number of metres.  The metre offset is
# resolved only where the CPA is computed (see :func:`lateral_shift_m`,
# :func:`vertical_shift_m`), because it depends on the live intruder
# position covariance there.  The scored 1-sigma cylinder-distance metric
# (``State_estimator::min_1sigma_cylinder_distance``) is::
#
#     d_xy = horiz       / (cyl_d/2 + rad_std)
#     d_z  = |rel_down|  / (cyl_h/2 + down_std)
#     cyldist = max(d_xy, d_z)
#
# i.e. the intruder's 1-sigma position uncertainty inflates the
# *denominator*.  The targeted (uncertainty-aware) separation at CPA is::
#
#     target_lat  = ratio * (cyl_d/2 + sigma_lat)   sigma_lat = sqrt(e^T P_xy e)
#     target_vert = ratio * (cyl_h/2 + sigma_down)  sigma_down = sqrt(P_dd)
#
# The escape is applied as a parallel route ``shift`` along an escape
# direction ``e``, so the achieved separation is the *sum* of the
# separation already present along ``e`` at the CPA and the injected
# shift.  Sizing the shift to the full target would therefore overshoot
# whenever the trajectories already pass with some separation in the
# escape direction.  The shift is instead the target reduced by the
# along-escape component of the estimated ownship->intruder separation at
# the CPA, so the *achieved* separation lands on the target (clamped at 0
# so an already-clear geometry commits no shift)::
#
#     d_along = (intr - own)_cpa . e          (signed, < 0 for a good escape)
#     s_lat   = max(0, target_lat  + d_along_h)
#     s_vert  = max(0, target_vert + d_along_z)
#
# For a head-on collision course (the separation along ``e`` is ~0) this
# reduces to ``s = target`` — the previous behaviour.  With no track / no
# covariance / no separation the sigma and d_along terms vanish and the
# offset is the nominal ``ratio * half_dimension`` (cyldist = ratio for a
# perfectly tracked, zero-uncertainty intruder).  ``ratio = 1.0`` just
# grazes the cylinder boundary (cyldist = 1); the 1.5 default keeps a
# 50 % safety margin (cyldist = 1.5) to absorb trajectory-prediction
# error.
DEFAULT_LATERAL_SHIFT_RATIO  = 1.5
DEFAULT_VERTICAL_SHIFT_RATIO = 1.5

# Default protection cylinder (m) used only as a fallback for the
# uncertainty-aware sizing when no :class:`CpaContext` is supplied
# (e.g. a candidate previewed with no active track).
_DEFAULT_CYL_DIAMETER_M = 609.6
_DEFAULT_CYL_HEIGHT_M   = 304.8


@dataclass(frozen=True)
class CpaContext:
    """Per-step geometry needed to size a ratio-based escape at the CPA.

    Carries the protection-cylinder dimensions and the intruder position
    covariance at the predicted closest point of approach, so the
    direction-resolved escape magnitude can be computed where the CPA is
    evaluated (the avoidance loop), then frozen into the committed
    :class:`RouteTransform`.

    Attributes:
        cyl_d:        Protection-cylinder diameter (m).
        cyl_h:        Protection-cylinder height (m).
        intr_cov_cpa: Packed intruder position covariance at the CPA,
                      ``[Pnn, Pne, Pee, Pdd]`` (the horizontal 2x2 block
                      plus the vertical variance, matching the simulator
                      propagation buffer); ``None`` when no track is
                      active (sigma terms then drop to zero).
        rel_cpa:      Estimated ownship->intruder separation vector at the
                      CPA, ``(intr - own)`` NED (m).  Its component along
                      the escape direction is subtracted from the targeted
                      separation so the injected shift adds to — rather
                      than ignores — the separation already present;
                      ``None`` when no track is active (the subtraction
                      then drops to zero, recovering the nominal sizing).
        own_pos:      Current ownship NED position (m) at the moment the
                      escape is built — the start point of the
                      ``min_bearing`` family's straight external-track
                      segment; ``None`` falls the family back to the
                      identity (no segment can be built).
        intr_pos_cpa: Estimated intruder NED position (m) at the
                      predicted CPA — the point the ``min_bearing``
                      family's segment aims to clear (offset by the
                      safety margin); ``None`` falls the family back to
                      the identity.
    """
    cyl_d: float
    cyl_h: float
    intr_cov_cpa: Optional[np.ndarray] = None
    rel_cpa: Optional[np.ndarray] = None
    own_pos: Optional[np.ndarray] = None
    intr_pos_cpa: Optional[np.ndarray] = None


def _ctx_cyl_d(ctx: Optional['CpaContext']) -> float:
    return _DEFAULT_CYL_DIAMETER_M if ctx is None else float(ctx.cyl_d)


def _ctx_cyl_h(ctx: Optional['CpaContext']) -> float:
    return _DEFAULT_CYL_HEIGHT_M if ctx is None else float(ctx.cyl_h)


def _sigma_lateral(ctx: Optional['CpaContext'],
                   u_h: np.ndarray) -> float:
    """1-sigma intruder horizontal position std along the escape unit ``u_h``.

    ``u_h`` is the horizontal ``(N, E)`` escape direction; the projection
    ``sqrt(u_h^T P_xy u_h)`` uses the packed horizontal covariance block
    ``[Pnn, Pne, Pee]``.  Returns ``0.0`` when no covariance is available.
    """
    if ctx is None or ctx.intr_cov_cpa is None:
        return 0.0
    p = np.asarray(ctx.intr_cov_cpa, dtype=np.float64).reshape(-1)
    pnn, pne, pee = float(p[0]), float(p[1]), float(p[2])
    un, ue = float(u_h[0]), float(u_h[1])
    var = un * un * pnn + 2.0 * un * ue * pne + ue * ue * pee
    return float(np.sqrt(max(var, 0.0)))


def _sigma_vertical(ctx: Optional['CpaContext']) -> float:
    """1-sigma intruder vertical (down) position std, ``sqrt(Pdd)``."""
    if ctx is None or ctx.intr_cov_cpa is None:
        return 0.0
    p = np.asarray(ctx.intr_cov_cpa, dtype=np.float64).reshape(-1)
    return float(np.sqrt(max(float(p[3]), 0.0)))


def _rel_along_h(ctx: Optional['CpaContext'], e_h: np.ndarray) -> float:
    """Signed horizontal component of the CPA separation along ``e_h``.

    ``(intr - own)_h . e_h`` from the estimated ownship->intruder
    separation at the CPA (:attr:`CpaContext.rel_cpa`).  Negative for a
    good escape (the intruder lies opposite the escape direction ``e_h``).
    Returns ``0.0`` when no separation is available.
    """
    if ctx is None or ctx.rel_cpa is None:
        return 0.0
    r = np.asarray(ctx.rel_cpa, dtype=np.float64).reshape(-1)
    eh = np.asarray(e_h, dtype=np.float64).reshape(-1)[:2]
    return float(r[0] * eh[0] + r[1] * eh[1])


def _rel_down(ctx: Optional['CpaContext']) -> float:
    """Signed vertical (down) component of the CPA separation, ``(intr-own)_d``.

    Returns ``0.0`` when no separation is available.
    """
    if ctx is None or ctx.rel_cpa is None:
        return 0.0
    return float(np.asarray(ctx.rel_cpa, dtype=np.float64).reshape(-1)[2])


def lateral_target_m(ratio: float, e_h: np.ndarray,
                     ctx: Optional['CpaContext']) -> float:
    """Targeted (uncertainty-aware) lateral separation (m) at the CPA.

    ``ratio * (cyl_d/2 + sigma_lat)`` with ``sigma_lat`` the intruder
    1-sigma horizontal position std along the escape unit ``e_h`` — the
    separation the escape aims to achieve *before* any reduction for the
    separation already present.  The ``min_bearing`` family places its
    straight segment exactly this far from the intruder at the CPA; the
    ``shifted`` family (see :func:`lateral_shift_m`) reduces it by the
    along-escape separation already there.
    """
    return float(ratio) * (0.5 * _ctx_cyl_d(ctx) + _sigma_lateral(ctx, e_h))


def vertical_target_m(ratio: float,
                      ctx: Optional['CpaContext']) -> float:
    """Targeted (uncertainty-aware) vertical separation (m) at the CPA.

    ``ratio * (cyl_h/2 + sigma_down)`` with ``sigma_down`` the intruder
    1-sigma vertical position std — the mirror of :func:`lateral_target_m`
    for the climb / descend axis.
    """
    return float(ratio) * (0.5 * _ctx_cyl_h(ctx) + _sigma_vertical(ctx))


def lateral_shift_m(ratio: float, e_h: np.ndarray,
                    ctx: Optional['CpaContext']) -> float:
    """Lateral escape magnitude (m) landing the achieved cyldist on ``ratio``.

    ``e_h`` is the horizontal ``(N, E)`` unit vector of the *actual*
    escape offset direction (starboard for a right shift, port for a
    left shift).  The targeted separation
    ``ratio * (cyl_d/2 + sigma_lat)`` (:func:`lateral_target_m`) — with
    ``sigma_lat`` the intruder 1-sigma horizontal position std along
    ``e_h`` — is reduced by the separation already present along ``e_h``
    at the CPA (``d_along = (intr - own)_h . e_h``, negative for a good
    escape), so the *achieved* horizontal separation lands on the target
    instead of overshooting it.  Clamped at 0 (an already-clear geometry
    commits no shift).
    """
    return max(0.0, lateral_target_m(ratio, e_h, ctx) + _rel_along_h(ctx, e_h))


def vertical_shift_m(ratio: float,
                     ctx: Optional['CpaContext'],
                     e_down: float) -> float:
    """Vertical escape magnitude (m) landing the achieved cyldist on ``ratio``.

    ``e_down`` is the sign of the escape along the NED down axis: ``-1``
    for a climb (offset up), ``+1`` for a descend (offset down).  The
    targeted separation ``ratio * (cyl_h/2 + sigma_down)``
    (:func:`vertical_target_m`) — with ``sigma_down`` the intruder
    1-sigma vertical position std — is reduced by the vertical separation
    already present in the escape direction at the CPA
    (``(intr - own)_d * e_down``, negative for a good escape), so the
    *achieved* vertical separation lands on the target instead of
    overshooting it.  Clamped at 0.
    """
    return max(0.0,
               vertical_target_m(ratio, ctx) + _rel_down(ctx) * float(e_down))


def lateral_shift_m_nominal(ratio: float, cyl_d: float) -> float:
    """Zero-uncertainty lateral offset (m), ``ratio * (cyl_d/2)``.

    The idealised (perfectly-tracked, zero-covariance) sizing — used for
    the classifier's altitude margin and as a representative value where
    no CPA covariance is available."""
    return float(ratio) * (float(cyl_d) / 2.0)


def vertical_shift_m_nominal(ratio: float, cyl_h: float) -> float:
    """Zero-uncertainty vertical offset (m), ``ratio * (cyl_h/2)``."""
    return float(ratio) * (float(cyl_h) / 2.0)

# Default speed-reduction ratio for the along-track "slow down" escape
# (:func:`speed_reduce`).  During the maneuver the target
# segment speed is reduced to this fraction of the planned route speed,
# realised as a ``speed_scale = ratio`` multiplier on every segment
# speed.  0.6 ≈ a 40 % energy bleed, enough to let a crossing /
# overtaking intruder pass ahead without leaving the route.
DEFAULT_SLOWDOWN_RATIO = 0.6

# Cross-track line-attraction gain (1/m) of the route guidance law.
# The velocity command is the unit segment tangent plus ``k_xt`` times
# the cross-track *distance* vector (clamped so the intercept angle
# stays below ~78.7°), then scaled back to the segment speed — i.e.
# ``k_xt`` is the reciprocal of the guidance look-ahead distance
# (``k_xt = 1/L``).  Larger = sharper transition onto the line.  The
# 0.005 default ≈ a 200 m look-ahead: a 1000 m look-ahead converges
# too slowly onto the offset line, so a shorter one is used for a
# crisper (still acceleration-limited) capture.  In the DAA_simulator
# model the gain is configured once on the simulator, not per
# candidate; kept here so the default generator factory and the
# avoidance core can share the same number.
DEFAULT_K_XT_PER_M = 0.005

# Default ownship flight-envelope limits.  ``a_max_along`` is the
# speed-module (along-track) acceleration cap (m/s²); the lateral
# manoeuvre envelope is now expressed as angular *rates* matching the
# spherical (az/el/d) Virtual_ownship integrator: ``rate_max_azimuth``
# bounds the course-angle rate and ``rate_max_elevation`` the
# flight-path-angle rate (both rad/s).  Configured on the simulator
# (not per candidate); re-exported here for the core's default
# simulator construction.
DEFAULT_A_MAX_ALONG_M_S2        = 3.048
DEFAULT_RATE_MAX_AZIMUTH_RAD_S  = 0.15
DEFAULT_RATE_MAX_ELEVATION_RAD_S = 0.08

# Max integration sub-step (s) for the route simulator.
DEFAULT_SIM_DT_MAX_S = 0.5

# Sentinel "effectively unlimited" for always-on velocity caps.
# A large finite value (rather than +inf or 0) keeps the C side
# branch-free.
_V_UNLIMITED = 1.0E12


# ---------------------------------------------------------------------------
# Route transform — the affine route modifier a candidate represents
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RouteTransform:
    """Guidance modifier applied to the route by the ``DAA_simulator``.

    Attributes:
        shift:    (3,) NED position increment (m) added to every route
                  waypoint (used when ``mode == TRACK_ROUTE``).
        speed_scale: multiplier applied to every segment target speed;
                  ``< 1`` slows the ownship, ``> 1`` speeds it up (used
                  when ``mode == TRACK_ROUTE``).
        mode:     guidance mode — ``TRACK_ROUTE`` (0) follows the route,
                  ``HOLD_VELOCITY`` (1) ignores the route and flies the
                  constant NED ``velocity``.
        velocity: (3,) NED velocity (m/s) to hold when
                  ``mode == HOLD_VELOCITY``; ``None`` means zero.
        track_p0: (3,) NED segment start, track_p1: (3,) NED segment
                  end, track_speed: constant segment speed (m/s) — all
                  used when ``mode == EXTERNAL_TRACK``.
    """
    shift: np.ndarray
    speed_scale: float = 1.0
    mode: int = 0
    velocity: Optional[np.ndarray] = None
    track_p0: Optional[np.ndarray] = None
    track_p1: Optional[np.ndarray] = None
    track_speed: float = 0.0


# Guidance modes — keep in sync with DAA::Guidance_mode (Route_transform.h).
TRACK_ROUTE = 0
HOLD_VELOCITY = 1
EXTERNAL_TRACK = 2

# Modes that ignore the baseline route entirely (they carry their own
# self-contained guidance) and therefore *override* anything composed
# under them rather than stacking onto it.
_EXCLUSIVE_MODES = (HOLD_VELOCITY, EXTERNAL_TRACK)

# Avoidance maneuver families — the geometry used to build the
# right / left / up / down directional escapes.  The maintain and
# speed-reduction escapes are shared and do not depend on the family.
#
#   * ``shifted``     — parallel-route offset (a non-zero ``shift`` that
#                       displaces every route waypoint), the legacy
#                       behaviour.
#   * ``min_bearing`` — "minimal bearing at start": a straight
#                       segment (``EXTERNAL_TRACK``) from the ownship
#                       position at the moment of commit through the
#                       predicted intruder position at the CPA, offset by
#                       the configured safety margin to the right / left /
#                       above / below.  The segment is committed at the
#                       start of the maneuver and flown fixed; in
#                       closed-loop it is recomputed only when the
#                       maneuver re-stacks on a fresh continuous conflict,
#                       not every step.
#   * ``min_const_bearing`` — "minimal constant bearing": the
#                       ``HOLD_VELOCITY`` analogue of ``min_bearing``.
#                       Instead of an external track it commits a single
#                       constant NED velocity, at the current ownship
#                       speed, aimed from the ownship position at the
#                       predicted intruder position at the CPA offset by
#                       the safety margin.  With both aircraft on
#                       constant velocities the line-of-sight bearing
#                       stays (nearly) constant and they pass at the
#                       margin.  No cross-track feedback, so the
#                       acceleration-limited ramp at commit leaves a small
#                       parallel offset that is not recovered.
MANEUVER_FAMILY_SHIFTED = 'shifted'
MANEUVER_FAMILY_MIN_BEARING = 'min_bearing'
MANEUVER_FAMILY_MIN_CONST_BEARING = 'min_const_bearing'
DEFAULT_MANEUVER_FAMILY = MANEUVER_FAMILY_MIN_CONST_BEARING


# The identity transform = fly the baseline route unmodified.
IDENTITY_TRANSFORM = RouteTransform(np.zeros(3, dtype=np.float64), 1.0)


def compose_route_xf(base: RouteTransform,
                     delta: RouteTransform) -> RouteTransform:
    """Stack ``delta`` on top of ``base`` into one accumulated transform.

    Forms the single :class:`RouteTransform` equivalent to applying
    ``base`` and then ``delta``, so a sequence of maneuvers committed
    while already avoiding collapses into one active transform (the
    "closed-loop" stacking model).  ``TRACK_ROUTE`` transforms compose as
    a monoid with :data:`IDENTITY_TRANSFORM` as the unit: the
    lateral/vertical ``shift`` vectors add and the ``speed_scale`` speed
    factors multiply (e.g. a right shift then a climb yields a single
    diagonal offset; two slow-downs multiply their reduction).

    A ``HOLD_VELOCITY`` ``delta`` is exclusive — it ignores the route, so
    it overrides ``base`` entirely; composing anything onto a
    ``HOLD_VELOCITY`` ``base`` likewise yields ``delta`` (the later
    command wins).  ``compose_route_xf(IDENTITY_TRANSFORM, x) == x`` and
    ``compose_route_xf(x, IDENTITY_TRANSFORM) == x`` for any route-mode
    ``x``.
    """
    if delta.mode in _EXCLUSIVE_MODES or base.mode in _EXCLUSIVE_MODES:
        return delta
    shift = (np.asarray(base.shift, dtype=np.float64).reshape(3)
             + np.asarray(delta.shift, dtype=np.float64).reshape(3))
    return RouteTransform(shift, float(base.speed_scale) * float(delta.speed_scale))


# ---------------------------------------------------------------------------
# Public data type emitted to the simulation/visualisation layer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CandidateTrajectory:
    """A single sampled future ownship trajectory option.

    Attributes:
        name:      Generator identifier (e.g. ``"route"``,
                   ``"right_shift"``, ``"return_to_route"``).
        positions: (N, 3) array of NED positions (m) sampled at the
                   same lookahead time grid the caller used.
    """
    name: str
    positions: np.ndarray


# ---------------------------------------------------------------------------
# Math primitives (private)
# ---------------------------------------------------------------------------

def _lateral_avoid_unit(own_vel_cpa: Optional[np.ndarray],
                        fwd_vel: Optional[np.ndarray]) -> Optional[np.ndarray]:
    """Horizontal unit vector of the lateral *right* (starboard) axis (NED).

    Perpendicular, to the right, of the ownship's direction of travel at
    the predicted CPA.  ``own_vel_cpa`` is the ownship velocity (NED) at
    the closest point of approach, so its horizontal unit is the CPA
    heading ``fwd = (fwd_N, fwd_E)`` and the starboard direction is the
    right perpendicular ``[-fwd_E, fwd_N]``.  This is the
    ``lateral_right`` (give-way) direction; ``lateral_left`` is its
    negative (port).  The sign convention matches the encounter
    classifier (positive ``bearing_rel`` = target on the right of
    ``own_vel_cpa``).

    Falls back to the current ownship velocity ``fwd_vel`` (the live
    heading) when no usable CPA velocity is available (``own_vel_cpa is
    None`` or non-finite, or a degenerate horizontal speed), e.g. when
    no track is active.  Returns ``None`` only when neither heading
    yields a usable horizontal direction.
    """
    for v in (own_vel_cpa, fwd_vel):
        if v is None:
            continue
        v_h = np.asarray(v, dtype=np.float64).reshape(-1)[:2]
        if not np.all(np.isfinite(v_h)):
            continue
        sp = float(np.hypot(v_h[0], v_h[1]))
        if sp > 1e-6:
            fwd_n, fwd_e = v_h[0] / sp, v_h[1] / sp
            return np.array([-fwd_e, fwd_n, 0.0])
    return None


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

# A transform function maps the orientation context (CPA velocity, live
# heading) and the per-step CPA geometry (:class:`CpaContext`, carrying
# the cylinder dimensions and the intruder covariance at the CPA) to the
# RouteTransform the candidate commits.  ``None`` for any argument means
# "not available" (the ratio-based escapes then fall back to their
# nominal, zero-uncertainty sizing).
TransformFn = Callable[[Optional[np.ndarray], Optional[np.ndarray],
                        Optional['CpaContext']],
                       RouteTransform]


@dataclass(frozen=True)
class CandidateGenerator:
    """A named candidate maneuver = a name + the route transform it commits.

    In the ``DAA_simulator`` model every route-following candidate is
    *just a different* :class:`RouteTransform`, and they all sample the
    same way (project the look-ahead the simulator would fly under that
    transform).  The only thing that varies between candidates is the
    transform, so a single class parameterised by a ``transform_fn``
    replaces the old subclass hierarchy.

    ``transform_fn`` maps ``(own_vel_cpa, fwd_vel)`` to the
    :class:`RouteTransform`; ``None`` means the identity transform (fly
    the baseline route unmodified — used by the baseline and
    return-to-route candidates).  Stateless: the committed transform
    lives in the simulator (frozen by ``set_route_xf``).

    Build instances with the module-level factories (:func:`baseline`,
    :func:`maintain`, :func:`lateral_right`, :func:`lateral_left`,
    :func:`climb`, :func:`descend`, :func:`speed_reduce`,
    :func:`return_to_route`).
    """
    name: str
    transform_fn: Optional[TransformFn] = None

    def transform(self, *,
                  own_vel_cpa: Optional[np.ndarray] = None,
                  fwd_vel: Optional[np.ndarray] = None,
                  cpa_ctx: Optional['CpaContext'] = None) -> RouteTransform:
        """The :class:`RouteTransform` this candidate commits.

        ``own_vel_cpa`` (ownship velocity at the predicted CPA, NED)
        orients the direction-sensitive (lateral) candidates; ``fwd_vel``
        (the live ownship velocity) is the fallback heading.  ``cpa_ctx``
        (:class:`CpaContext`) carries the cylinder dimensions and the
        intruder covariance at the CPA, used to size the ratio-based
        lateral / vertical escapes; ``None`` selects their nominal,
        zero-uncertainty offset.
        """
        if self.transform_fn is None:
            return IDENTITY_TRANSFORM
        return self.transform_fn(own_vel_cpa, fwd_vel, cpa_ctx)

    def sample(self, *,
               simulator,
               n_out: int,
               own_vel_cpa: Optional[np.ndarray] = None,
               fwd_vel: Optional[np.ndarray] = None,
               cpa_ctx: Optional['CpaContext'] = None,
               out: Optional[np.ndarray] = None) -> np.ndarray:
        """Return ``(n_out, 3)`` NED positions sampled ``dt`` apart.

        Projects the trajectory the ownship would fly from the
        simulator's current state under this candidate's
        :meth:`transform`, without mutating the simulator.  Row ``0`` is
        the current ownship position.  ``out`` is an optional
        pre-allocated ``(n_out, 3)`` C-contiguous float64 buffer written
        in place (zero-copy).
        """
        xf = self.transform(own_vel_cpa=own_vel_cpa, fwd_vel=fwd_vel,
                            cpa_ctx=cpa_ctx)
        return simulator.simulate(int(n_out), shift=xf.shift,
                                  speed_scale=xf.speed_scale, out=out,
                                  mode=xf.mode, velocity=xf.velocity,
                                  track_p0=xf.track_p0, track_p1=xf.track_p1,
                                  track_speed=xf.track_speed)

    def sample_and_score(self, *,
                          simulator,
                          n_out: int,
                          own_vel_cpa: Optional[np.ndarray] = None,
                          fwd_vel: Optional[np.ndarray] = None,
                          cpa_ctx: Optional['CpaContext'] = None,
                          out: Optional[np.ndarray] = None):
        """Fused project + score for this candidate's transform.

        Combines :meth:`sample` with the intruder cylinder-distance scan
        in a single ``simulator`` call (the intruder propagation must
        already be loaded via ``simulator.propagate``).  The protection
        cylinder dimensions come from the simulator configuration.
        ``out`` is an optional ``(n_out, 3)`` buffer receiving the
        projected trajectory; pass ``None`` to score without writing it
        back.

        Returns ``(trajectory_or_None, min_cyldist, idx_cpa)``.
        """
        xf = self.transform(own_vel_cpa=own_vel_cpa, fwd_vel=fwd_vel,
                            cpa_ctx=cpa_ctx)
        return simulator.simulate_and_score(
            int(n_out), shift=xf.shift,
            speed_scale=xf.speed_scale, out=out,
            mode=xf.mode, velocity=xf.velocity,
            track_p0=xf.track_p0, track_p1=xf.track_p1,
            track_speed=xf.track_speed)


# ---------------------------------------------------------------------------
# Candidate factories
# ---------------------------------------------------------------------------

def baseline(name: str = "route") -> CandidateGenerator:
    """Route-following candidate (identity transform) — the trajectory
    the ownship flies if it keeps tracking the planned route."""
    return CandidateGenerator(name)


def return_to_route(name: str = "return_to_route") -> CandidateGenerator:
    """Smooth return onto the baseline route (identity transform): once
    committed the active transform resets to the identity and the
    airframe rejoins the baseline route from its current state."""
    return CandidateGenerator(name)


def maintain(name: str = "maintain") -> CandidateGenerator:
    """ICAO §3.2.2 "maintain heading and speed" candidate.

    Commits a ``HOLD_VELOCITY`` transform carrying the live ownship
    velocity (``fwd_vel``), so the simulator flies that constant NED
    velocity natively and deliberately ignores the baseline route.
    """
    def _xf(own_vel_cpa, fwd_vel, cpa_ctx):
        if fwd_vel is None:
            v = np.zeros(3, dtype=np.float64)
        else:
            v = np.ascontiguousarray(fwd_vel, dtype=np.float64).reshape(3)
        return RouteTransform(np.zeros(3, dtype=np.float64), 1.0,
                              mode=HOLD_VELOCITY, velocity=v)
    return CandidateGenerator(name, _xf)


def shift(offset_ned, name: str = "shift") -> CandidateGenerator:
    """Parallel-route escape with a lateral / vertical offset.

    ``offset_ned`` is either a fixed NED 3-vector (e.g. ``[0, 0, -700]``
    for a 213.36 m climb) or a callable ``f(own_vel_cpa, fwd_vel, cpa_ctx)
    -> (3,) | None`` resolving the offset against the CPA / live heading
    and the per-step CPA geometry.  A ``None`` from the callable ("no
    usable direction") yields the zero offset (identity).
    """
    if callable(offset_ned):
        offset_fn = offset_ned
        static = None
    else:
        offset_fn = None
        static = np.asarray(offset_ned, dtype=np.float64).reshape(3).copy()

    def _xf(own_vel_cpa, fwd_vel, cpa_ctx):
        if static is not None:
            off = static
        else:
            vec = offset_fn(own_vel_cpa, fwd_vel, cpa_ctx)
            off = (np.zeros(3, dtype=np.float64) if vec is None
                   else np.asarray(vec, dtype=np.float64).reshape(3))
        return RouteTransform(off, 1.0)
    return CandidateGenerator(name, _xf)


def _escape_unit(direction: str,
                 own_vel_cpa: Optional[np.ndarray],
                 fwd_vel: Optional[np.ndarray]) -> Optional[np.ndarray]:
    """NED unit vector of the escape offset direction for ``direction``.

    ``'right'`` / ``'left'`` resolve to the starboard / port
    perpendicular of the ownship's direction of travel at the predicted
    CPA (``own_vel_cpa``), falling back to the live heading
    (``fwd_vel``) — the standard ICAO "give way to the right" axis and
    its mirror; ``None`` is returned when neither heading yields a usable
    horizontal direction.  ``'up'`` / ``'down'`` resolve to the vertical
    unit ``(0, 0, -1)`` / ``(0, 0, +1)``.
    """
    if direction in ('up', 'down'):
        return np.array([0.0, 0.0, -1.0 if direction == 'up' else 1.0])
    u = _lateral_avoid_unit(own_vel_cpa, fwd_vel)
    if u is None:
        return None
    return u if direction == 'right' else -u


def _escape_speed(own_vel_cpa: Optional[np.ndarray],
                  fwd_vel: Optional[np.ndarray]) -> float:
    """Ownship cruise speed (m/s) for a constant-velocity escape.

    Prefers the velocity at the predicted CPA (``own_vel_cpa``), falling
    back to the live velocity (``fwd_vel``); returns ``0.0`` when neither
    yields a usable (non-zero) speed.
    """
    speed = 0.0
    for vv in (own_vel_cpa, fwd_vel):
        if vv is not None:
            a = np.ascontiguousarray(vv, dtype=np.float64).reshape(3)
            s = float(np.linalg.norm(a))
            if s > 1.0e-9:
                speed = s
                break
    return speed



# Canonical candidate name per escape direction — identical across
# maneuver families so the avoidance state machine, the energy-cost
# ranking and the visualiser key off the same right / left / up / down
# concept regardless of how the maneuver geometry is built.
_DIRECTION_NAME = {
    'right': 'right_shift',
    'left':  'left_shift',
    'up':    'climb',
    'down':  'descend',
}


def directional_escape(direction: str, *,
                       family: str = DEFAULT_MANEUVER_FAMILY,
                       lateral_ratio: float = DEFAULT_LATERAL_SHIFT_RATIO,
                       vertical_ratio: float = DEFAULT_VERTICAL_SHIFT_RATIO,
                       name: Optional[str] = None) -> CandidateGenerator:
    """Right / left / up / down avoidance escape for a maneuver family.

    ``direction`` is one of ``'right'``, ``'left'``, ``'up'``,
    ``'down'``.  The escape keeps the same right / left / above / below
    *concept* across families (and the same candidate ``name`` —
    ``right_shift`` / ``left_shift`` / ``climb`` / ``descend`` — so the
    state machine and ranking are unaffected); only the route transform
    differs:

      * ``shifted``     — a parallel-route ``shift`` sized so the
                          achieved cylinder distance at the CPA lands on
                          the configured ratio (:func:`lateral_shift_m` /
                          :func:`vertical_shift_m`), reduced by the
                          separation already present.
      * ``min_bearing`` — an ``EXTERNAL_TRACK`` straight segment from the
                          current ownship position
                          (:attr:`CpaContext.own_pos`) to the predicted
                          intruder position at the CPA
                          (:attr:`CpaContext.intr_pos_cpa`) offset by the
                          full targeted safety margin
                          (:func:`lateral_target_m` /
                          :func:`vertical_target_m`) along the escape
                          direction.  Falls back to the identity (track
                          the route) when the CPA geometry is
                          unavailable.
      * ``min_const_bearing`` \u2014 the ``HOLD_VELOCITY`` analogue of
                          ``min_bearing``: a single constant NED velocity,
                          at the current ownship speed, aimed from the
                          ownship position at that same offset target.
                          Falls back to the identity when the CPA
                          geometry or a usable speed is unavailable.

    ``lateral_ratio`` / ``vertical_ratio`` size the horizontal and
    vertical escapes respectively.
    """
    is_vertical = direction in ('up', 'down')
    ratio = float(vertical_ratio if is_vertical else lateral_ratio)
    if name is None:
        name = _DIRECTION_NAME[direction]

    if family == MANEUVER_FAMILY_SHIFTED:
        def _resolver(own_vel_cpa, fwd_vel, cpa_ctx):
            e = _escape_unit(direction, own_vel_cpa, fwd_vel)
            if e is None:
                return None
            if is_vertical:
                mag = vertical_shift_m(ratio, cpa_ctx, float(e[2]))
            else:
                mag = lateral_shift_m(ratio, e[:2], cpa_ctx)
            return mag * e
        return shift(_resolver, name=name)

    def _xf(own_vel_cpa, fwd_vel, cpa_ctx):
        e = _escape_unit(direction, own_vel_cpa, fwd_vel)
        if (e is None or cpa_ctx is None
                or cpa_ctx.own_pos is None
                or cpa_ctx.intr_pos_cpa is None):
            # No usable direction or no CPA geometry to anchor the
            # segment — track the route unmodified.
            return IDENTITY_TRANSFORM
        if is_vertical:
            margin = vertical_target_m(ratio, cpa_ctx)
        else:
            margin = lateral_target_m(ratio, e[:2], cpa_ctx)
        p0 = np.ascontiguousarray(cpa_ctx.own_pos,
                                  dtype=np.float64).reshape(3).copy()
        p1 = (np.ascontiguousarray(cpa_ctx.intr_pos_cpa,
                                   dtype=np.float64).reshape(3)
              + margin * e)
        if family == MANEUVER_FAMILY_MIN_CONST_BEARING:
            # Constant-velocity analogue: hold a single NED velocity, at
            # the current ownship speed, pointing from the ownship at the
            # offset target.  No cross-track feedback (cf. EXTERNAL_TRACK).
            d = p1 - p0
            nrm = float(np.linalg.norm(d))
            speed = _escape_speed(own_vel_cpa, fwd_vel)
            if nrm < 1.0e-9 or speed < 1.0e-9:
                return IDENTITY_TRANSFORM
            v = (speed / nrm) * d
            return RouteTransform(np.zeros(3, dtype=np.float64), 1.0,
                                  mode=HOLD_VELOCITY, velocity=v)
        # min_bearing (EXTERNAL_TRACK): carry the segment speed captured
        # at commit (the current ownship speed) so it is fixed for the
        # whole maneuver, like the maintain mode, instead of being
        # recomputed each step.  The straight segment supplies the
        # direction; ``track_speed`` is its constant module.
        track_speed = _escape_speed(own_vel_cpa, fwd_vel)
        return RouteTransform(np.zeros(3, dtype=np.float64), 1.0,
                              mode=EXTERNAL_TRACK,
                              track_p0=p0, track_p1=p1,
                              track_speed=track_speed)
    return CandidateGenerator(name, _xf)


def speed_reduce(speed_ratio: float = DEFAULT_SLOWDOWN_RATIO,
                 name: str = "slow_down") -> CandidateGenerator:
    """Along-track speed-reduction escape ("reduce speed").

    Follows the baseline route verbatim but scales every segment target
    speed by ``speed_ratio`` (``speed_scale``), so the guidance targets
    a proportionally lower speed — no heading or altitude change.
    """
    ratio = max(float(speed_ratio), 1e-3)

    def _xf(own_vel_cpa, fwd_vel, cpa_ctx):
        return RouteTransform(np.zeros(3, dtype=np.float64), ratio)
    return CandidateGenerator(name, _xf)


# ---------------------------------------------------------------------------
# Factory + sampler helper
# ---------------------------------------------------------------------------

def default_generators(
    lateral_shift_ratio: float = DEFAULT_LATERAL_SHIFT_RATIO,
    vertical_shift_ratio: float = DEFAULT_VERTICAL_SHIFT_RATIO,
    slowdown_ratio: float = DEFAULT_SLOWDOWN_RATIO,
    baseline_name: str = "route",
    maneuver_family: str = DEFAULT_MANEUVER_FAMILY,
) -> List[CandidateGenerator]:
    """Default candidate generator set in order of preference.

    Order::

        0. baseline           — the route the ownship is currently on
                                (identity transform; drives the alert).
        1. maintain           — ICAO §3.2.2 "hold heading and speed"
                                constant-velocity from the current state.
        2. right_shift        — lateral escape to starboard of the CPA
                                heading (ICAO "give way" turn).
        3. left_shift         — lateral escape to port (vacate).
        4. descend
        5. climb
        6. speed_reduce       — along-track speed reduction
                                (``speed_scale = slowdown_ratio``).
        7. return_to_route    — identity transform; returns to the
                                baseline once the conflict passes.

    ``lateral_shift_ratio`` / ``vertical_shift_ratio`` size the lateral
    and climb/descend escapes as a ratio of the targeted
    (uncertainty-aware) cylinder distance at CPA; the metre offset is
    resolved per-step from the :class:`CpaContext` (see
    :func:`lateral_shift_m` / :func:`vertical_shift_m`).

    ``maneuver_family`` selects how the four directional escapes
    (right / left / down / up) are built — ``'shifted'`` (parallel-route
    offset, the default / legacy behaviour), ``'min_bearing'``
    (a fresh straight :data:`EXTERNAL_TRACK` segment that clears the
    predicted intruder CPA position by the safety margin) or
    ``'min_const_bearing'`` (the :data:`HOLD_VELOCITY` constant-velocity
    analogue of ``min_bearing``); see :func:`directional_escape`.  The
    ``maintain`` and ``speed_reduce`` escapes are shared and unaffected
    by the family.

    In the ``DAA_simulator`` model the guidance law (cross-track gain,
    acceleration / velocity envelope) is configured once on the
    simulator, so the generators only need the maneuver *geometry*
    (shift ratios and the speed ratio).
    """
    def _dir(direction):
        return directional_escape(
            direction, family=maneuver_family,
            lateral_ratio=lateral_shift_ratio,
            vertical_ratio=vertical_shift_ratio)

    return [
        baseline(name=baseline_name),
        maintain(),
        _dir('right'),
        _dir('left'),
        _dir('down'),
        _dir('up'),
        speed_reduce(speed_ratio=slowdown_ratio),
        return_to_route(),
    ]


def sample_all(generators: List[CandidateGenerator], *,
               simulator,
               n_out: int,
               own_vel_cpa: Optional[np.ndarray] = None,
               fwd_vel: Optional[np.ndarray] = None,
               cpa_ctx: Optional['CpaContext'] = None,
               out: Optional[np.ndarray] = None) -> List[CandidateTrajectory]:
    """Sample every generator and wrap results in :class:`CandidateTrajectory`.

    All generators emit ``(n_out, 3)`` positions sampled ``dt`` apart on
    the simulator's current state.  ``own_vel_cpa`` / ``fwd_vel`` orient
    the lateral escapes and ``cpa_ctx`` sizes the ratio-based escapes.
    ``out``, when given, is a pre-allocated
    ``(len(generators), n_out, 3)`` C-contiguous float64 buffer;
    generator ``k`` writes into the ``out[k]`` slice (zero-copy).
    """
    return [
        CandidateTrajectory(
            g.name,
            g.sample(simulator=simulator, n_out=n_out,
                     own_vel_cpa=own_vel_cpa, fwd_vel=fwd_vel,
                     cpa_ctx=cpa_ctx,
                     out=(None if out is None else out[k])))
        for k, g in enumerate(generators)
    ]
