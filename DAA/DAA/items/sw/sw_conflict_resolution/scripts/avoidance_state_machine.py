#!/usr/bin/env python3
"""
Avoidance state machine.

Encapsulates the decision logic that picks which candidate trajectory
the ownship is flying at each step.  Designed to be agnostic to the
specific set of avoidance maneuvers in use: as long as the generator
list follows the convention

    [baseline, *avoidance_generators, return_to_baseline]

new avoidance maneuver types (left shift, climb, descend, S-turn,
...) can be added by appending more entries to the middle slice
without touching the state machine itself.

Three logical states:

  ``ROUTE``      — following the baseline route.  An alert on the
                   baseline triggers ``AVOIDING``: the state machine
                   picks the best avoidance candidate (per
                   :meth:`AvoidanceStateMachine.select_avoidance`) and
                   commits it.
  ``AVOIDING``   — flying an avoidance maneuver.  Transitions to
                   ``RETURNING`` once the return-to-baseline candidate
                   is conflict-free.
  ``RETURNING``  — flying the return-to-baseline candidate.  Loops
                   back to ``AVOIDING`` if a new conflict appears on
                   the return path, or back to ``ROUTE`` once the
                   ownship is within ``return_close_m`` horizontal
                   metres of the baseline (measured against the
                   simulator-supplied ``track_point``, the foot of the
                   perpendicular from the ownship onto the active
                   route).

Committing a maneuver is a single ``sim.set_route_xf(shift, speed_scale)``
call applying the selected generator's :class:`RouteTransform`; the
simulator freezes that transform and flies it on subsequent
``sim.step`` calls.  The generators are stateless (the committed
transform lives in the simulator), so there is no per-generator
``commit`` / ``reset`` machinery: re-entering a maneuver simply
re-resolves and re-commits its transform from the live ownship state.
A candidate whose :meth:`transform` returns ``None`` (e.g. the
constant-velocity ``maintain``) leaves the active route transform
unchanged when committed.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .candidate_trajectories import IDENTITY_TRANSFORM, compose_route_xf


DEFAULT_RETURN_CLOSE_M = 9.144

# Default temporal hysteresis window (s) applied to the engage FSM
# transition: the alert condition must hold continuously for this long
# before the maneuver commits.
DEFAULT_HYSTERESIS_S = 5.0

# Default temporal hysteresis window (s) applied to the return FSM
# transition: the clearance condition must hold continuously for this
# long before the return-to-route commits.
DEFAULT_RETURN_HYSTERESIS_S = 25.0

# Closed-loop mode identifiers (see ``AvoidanceStateMachine`` /
# ``closed_loop_mode``).
#   ``open``        — legacy open-loop: a committed escape replaces the
#                     active transform and the FSM only waits to return.
#   ``on_conflict`` — closed-loop stacking triggered while the
#                     currently-flown maneuver is *still confirmed in
#                     conflict* (a fresh full ``engage_hysteresis_s`` of
#                     continuous conflict per added layer).
#   ``periodic``    — closed-loop stacking re-evaluated on a fixed wall
#                     cadence; a new escape is composed only when the
#                     anti-flicker rule (see ``_periodic_switch_ok``)
#                     says the re-ranked option is worth switching to.
CLOSED_LOOP_OPEN        = 'open'
CLOSED_LOOP_ON_CONFLICT = 'on_conflict'
CLOSED_LOOP_PERIODIC    = 'periodic'

# Default avoidance re-evaluation policy: closed-loop periodic
# re-checking (re-rank the escape set on a fixed cadence and switch only
# when the anti-flicker rule is met).
DEFAULT_CLOSED_LOOP_MODE = CLOSED_LOOP_PERIODIC

# Default anti-flicker improvement ratio for the periodic closed-loop
# mode: a re-evaluated escape must improve the predicted CPA cylinder
# distance by at least this fraction over the currently-flown maneuver
# before the FSM switches (composes) to it.
DEFAULT_SWITCH_IMPROVE_RATIO = 0.15

# Per-maneuver energy-cost ratios used to rank the escapes that a case
# permits.  At the decision instant the state machine selects the
# compliant escape with the best *cylindrical-separation-per-energy*
# score (``min_cyldist / energy_cost``) among those that clear the
# alert threshold, so a manoeuvre is only preferred over a cheaper one
# when it buys proportionally more separation.
#
# The ratios are dimensionless and only their *relative* magnitude
# matters.  The defaults below encode the rules-of-the-air bias:
# a RIGHT turn is the cheapest escape, a LEFT turn is slightly more
# costly (so right is preferred whenever both clear), and the vertical
# escapes (descend, then climb) are costlier still.  The along-track
# ``slow_down`` escape sits between the lateral and the vertical
# escapes: it keeps the route but bleeds energy.  Callers (and GUI
# presets) override individual entries to activate a specific escape
# branch — e.g. lowering ``climb`` below ``right_shift`` makes a
# ``M_LATERAL_OR_CLIMB`` case climb instead of turning, or lowering
# ``left_shift`` below ``right_shift`` forces a left vacate.
DEFAULT_ENERGY_COST_RATIOS: Dict[str, float] = {
    'maintain':    0.5,
    'right_shift': 1.0,
    'left_shift':  1.3,
    'slow_down':   1.4,
    'descend':     1.5,
    'climb':       2.0,
}

_MIN_ENERGY_COST = 1.0e-9   # guard against divide-by-zero on a 0 ratio


class AvoidanceStateMachine:
    """State machine driving avoidance maneuver selection.

    Parameters
    ----------
    generators:
        Candidate-trajectory generators in the layout
        ``[baseline, *avoidance, return]`` (length >= 3).
    alert_threshold:
        1-sigma cylinder distance threshold below which a candidate is
        considered to be in conflict.
    return_close_m:
        Horizontal distance (m) to the baseline below which the
        ``RETURNING`` state declares the maneuver finished and goes
        back to ``ROUTE``.
    engage_hysteresis_s:
        Temporal hysteresis window (seconds) for *starting* an
        avoidance maneuver.  The alert must persist continuously for at
        least this long before the state machine commits an avoidance
        (both the initial ``ROUTE -> AVOIDING`` engage and a
        ``RETURNING -> AVOIDING`` re-engage on a new conflict).  Any
        single conflict-free step resets the timer, so a transient
        spike (e.g. an unconverged track on the frame it is
        re-initialised) never triggers a maneuver.  ``0.0`` (default)
        reproduces the legacy "engage on the first alerting step"
        behaviour.
    return_hysteresis_s:
        Temporal hysteresis window (seconds) for *starting* the
        return to the baseline.  The return path must stay continuously
        conflict-free for at least this long before the
        ``AVOIDING -> RETURNING`` transition fires.  Any single alerting
        step resets the timer.  ``0.0`` (default) reproduces the legacy
        "return as soon as the path clears" behaviour.
    closed_loop_mode:
        Selects the re-evaluation policy while ``AVOIDING``.
        ``CLOSED_LOOP_OPEN`` (default) is the legacy open-loop
        behaviour: a committed escape *replaces* the active transform
        and the FSM only waits to return.  The two closed-loop modes
        both *compose* each newly selected escape on top of the active
        transform, so several maneuvers stack into a single accumulated
        ``active_xf`` (the return resets it to the identity, back to the
        original route); they differ only in the stacking trigger.
        ``CLOSED_LOOP_ON_CONFLICT`` stacks when the currently-flown
        maneuver is *still confirmed in conflict* (each added layer
        requires a fresh full ``engage_hysteresis_s`` of continuous
        conflict).  ``CLOSED_LOOP_PERIODIC`` re-evaluates on a fixed
        cadence (driven by the caller via the ``periodic_eval`` flag to
        :meth:`step`) and stacks only when the anti-flicker rule
        (:meth:`_periodic_switch_ok`) accepts the re-ranked escape.
    switch_improve_ratio:
        Anti-flicker margin for ``CLOSED_LOOP_PERIODIC``: the minimum
        fractional improvement in the predicted CPA cylinder distance a
        re-ranked escape must show over the currently-flown maneuver
        before the FSM switches to it.
    """

    ROUTE     = 0
    AVOIDING  = 1
    RETURNING = 2

    def __init__(self,
                 generators: Sequence,
                 *,
                 alert_threshold: float,
                 return_close_m: float = DEFAULT_RETURN_CLOSE_M,
                 engage_hysteresis_s: float = DEFAULT_HYSTERESIS_S,
                 return_hysteresis_s: float = DEFAULT_RETURN_HYSTERESIS_S,
                 closed_loop_mode: str = CLOSED_LOOP_OPEN,
                 switch_improve_ratio: float = DEFAULT_SWITCH_IMPROVE_RATIO):
        if len(generators) < 3:
            raise ValueError(
                "AvoidanceStateMachine needs at least 3 generators "
                "(baseline, >=1 avoidance, return).")
        self.generators       = list(generators)
        self.alert_threshold  = float(alert_threshold)
        self.return_close_m  = float(return_close_m)
        self.engage_hysteresis_s = max(0.0, float(engage_hysteresis_s))
        self.return_hysteresis_s = max(0.0, float(return_hysteresis_s))
        # Closed-loop maneuvers: ``closed_loop_mode`` selects the
        # re-evaluation policy while AVOIDING (see the class docstring).
        # Both closed-loop modes *compose* each newly selected escape on
        # top of the active transform (a single accumulated ``active_xf``
        # that the return resets to the identity); they differ only in
        # the stacking trigger.  ``self.closed_loop`` is the derived
        # compose-vs-replace flag consumed by ``_engage_avoidance`` and
        # the core sampler: True for both closed-loop modes, False for
        # open loop.  ``switch_improve_ratio`` is the periodic mode's
        # anti-flicker margin (see ``_periodic_switch_ok``).
        self.closed_loop_mode = str(closed_loop_mode)
        self.closed_loop      = (self.closed_loop_mode != CLOSED_LOOP_OPEN)
        self.switch_improve_ratio = max(0.0, float(switch_improve_ratio))
        # The single accumulated route transform currently flown.  Held
        # so closed-loop commits can compose onto it; in open-loop it
        # simply mirrors the last committed transform.
        self.active_xf        = IDENTITY_TRANSFORM

        K = len(self.generators)
        self.baseline_idx     = 0
        self.return_idx       = K - 1
        self.avoidance_indices: List[int] = list(range(1, K - 1))

        # Map generator name -> avoidance index, for ICAO-aware
        # policy lookups.  Populated once at construction.
        self._name_to_idx = {self.generators[j].name: j
                             for j in self.avoidance_indices}

        # ICAO-compliant action names for the current encounter
        # (populated by the caller after the encounter is classified).
        # If ``None``, the legacy "first-clears / max min-dist" policy
        # is used and all avoidance candidates are treated equally.
        self.compliant_action_names: Optional[Tuple[str, ...]] = None

        # Per-maneuver energy-cost ratios used by the escape ranking
        # (see :data:`DEFAULT_ENERGY_COST_RATIOS`).  Callers may mutate
        # or replace this dict after construction to bias the choice
        # between equally-compliant escapes.
        self.energy_cost: Dict[str, float] = dict(DEFAULT_ENERGY_COST_RATIOS)

        self.state            = self.ROUTE
        self.active_idx       = self.baseline_idx   # currently flown candidate
        self.maneuver_idx     = -1                  # last avoidance committed
        self.maneuver_start   = -1                  # step idx of FIRST commit
        # Count of committed escape maneuvers and their chronological
        # names.  Every ``_engage_avoidance`` is one commit — including
        # closed-loop re-stacks of the *same* maneuver type (each composes
        # a fresh transform), so ``n_commits`` matches the number of
        # distinct ``active_xf`` transitions the run produces.  In open-
        # loop this is normally 1 (plus any RETURNING -> AVOIDING
        # re-engage).
        self.n_commits        = 0
        self.committed_names: List[str] = []

        # Temporal-hysteresis (debounce) state.  ``_alert_since`` /
        # ``_clear_since`` hold the ``t_now`` at which the alert /
        # return-clear condition *began* being continuously true (or
        # ``None`` when the condition is currently false).  Refreshed
        # once per simulation step by :meth:`_refresh_timers`; the
        # ``_timers_t`` guard makes a second call within the same step
        # (e.g. :meth:`update_timers` followed by :meth:`step`) a
        # no-op so the timers advance exactly once per step.
        self._alert_since: Optional[float] = None
        self._clear_since: Optional[float] = None
        self._timers_t:    Optional[float] = None
        self._alert_confirmed  = False
        self._return_confirmed = False
        # Previous step's track validity, used to detect the
        # valid -> invalid transition (track just lost).  Such a
        # tracking discontinuity restarts the return-clear window so the
        # full return hysteresis is measured from the loss of track,
        # never satisfied by clearance accumulated while the intruder
        # was still observed.
        self._track_valid_prev = False

        # ----- FOV-loss safe-point gate ---------------------------------
        # The "safe point" is the last point of the committed avoidance
        # maneuver's lookahead at the instant the maneuver starts, and
        # ``_safe_normal`` is the unit lookahead tangent there (last
        # minus previous-to-last lookahead point).  Together they define
        # the plane the ownship must cross before a return is allowed
        # *while the intruder is not currently tracked* (e.g. it left the
        # camera FOV during the maneuver).  When the intruder is still in
        # view the gate is inactive and the return uses the normal
        # return-clear hysteresis only.  ``_safe_point_reached`` latches
        # True once the plane is crossed and is rearmed on every fresh
        # commit.
        self._safe_point: Optional[np.ndarray]  = None
        self._safe_normal: Optional[np.ndarray] = None
        self._safe_point_reached = False
        # Per-step flag: True only on steps where the safe-point gate is
        # actually holding back the return — i.e. in ``AVOIDING`` with a
        # captured safe point, the intruder out of view and the point
        # not yet crossed.  Refreshed every :meth:`step`; consumed by the
        # visualiser so the safe-point marker is shown only while in use.
        self._safe_point_active = False

    # ------------------------------------------------------------------
    # Energy-aware escape ranking helpers.
    # ------------------------------------------------------------------
    def _energy_cost(self, j: int) -> float:
        """Energy-cost ratio of avoidance candidate ``j`` (>0)."""
        c = float(self.energy_cost.get(self.generators[j].name, 1.0))
        return c if c > _MIN_ENERGY_COST else _MIN_ENERGY_COST

    def _best_by_energy(self, indices: List[int], ds: np.ndarray) -> int:
        """Pick the candidate with the best separation-per-energy score.

        Score is ``ds[j] / energy_cost[j]`` — i.e. the manoeuvre that
        buys the most cylindrical separation per unit of energy spent.
        Ties are resolved by generator-list order (``indices`` is kept
        in that order by the callers), so equal-cost escapes reproduce
        the legacy left-to-right preference.
        """
        best       = indices[0]
        best_score = float(ds[best]) / self._energy_cost(best)
        for j in indices[1:]:
            score = float(ds[j]) / self._energy_cost(j)
            if score > best_score:
                best_score = score
                best = j
        return best

    # ------------------------------------------------------------------
    # Policy hook — pick which avoidance candidate to commit to.
    #
    # When ``compliant_action_names`` has been set by the caller, an
    # ICAO-aware 3-tier policy is applied:
    #
    #   1. Among the **compliant** avoidances that clear the alert
    #      threshold, the one with the best separation-per-energy
    #      score (``min_cyldist / energy_cost``).  When a case admits
    #      several escapes this is what activates one branch over
    #      another: the energy-cost ratios bias the choice, while the
    #      separation term still vetoes a cheap-but-useless manoeuvre.
    #   2. Else, the best-scoring **non-compliant** avoidance that
    #      clears the threshold (only when no compliant option
    #      prevents the conflict — better to break the rule than to
    #      fly into LoWC).
    #   3. Else, the **compliant** candidate with the largest
    #      min-distance — i.e. when nothing clears, fail compliantly
    #      and maximise separation regardless of energy.
    #
    # If ``compliant_action_names`` is ``None`` (legacy / no
    # classification), falls back to the same energy-weighted choice
    # over all avoidance candidates that clear, else best min-distance.
    # ------------------------------------------------------------------
    def select_avoidance(self, ds: np.ndarray) -> int:
        if self.compliant_action_names is None:
            clearing = [j for j in self.avoidance_indices
                       if ds[j] > self.alert_threshold]
            if clearing:
                return self._best_by_energy(clearing, ds)
            return max(self.avoidance_indices, key=lambda j: float(ds[j]))

        # Partition avoidance indices into compliant / non-compliant
        # (preserving the generator-list order in each subset).
        compliant_set = set(
            self._name_to_idx[n] for n in self.compliant_action_names
            if n in self._name_to_idx)
        compliant     = [j for j in self.avoidance_indices if j in compliant_set]
        non_compliant = [j for j in self.avoidance_indices if j not in compliant_set]

        # Defensive: classifier produced no name we recognise.
        if not compliant:
            clearing = [j for j in self.avoidance_indices
                       if ds[j] > self.alert_threshold]
            if clearing:
                return self._best_by_energy(clearing, ds)
            return max(self.avoidance_indices, key=lambda j: float(ds[j]))

        # Tier 1: compliant that clear — best separation-per-energy.
        clearing_c = [j for j in compliant if ds[j] > self.alert_threshold]
        if clearing_c:
            return self._best_by_energy(clearing_c, ds)
        # Tier 2: non-compliant that clear (fall back only if a
        # non-compliant maneuver actually prevents the conflict).
        clearing_n = [j for j in non_compliant if ds[j] > self.alert_threshold]
        if clearing_n:
            return self._best_by_energy(clearing_n, ds)
        # Tier 3: nothing clears — fail compliantly (max separation).
        return max(compliant, key=lambda j: float(ds[j]))

    # ------------------------------------------------------------------
    # Periodic closed-loop anti-flicker switch test.
    # ------------------------------------------------------------------
    def _periodic_switch_ok(self, ds: np.ndarray) -> bool:
        """Anti-flicker test for the periodic closed-loop mode.

        Decides whether, on a periodic re-evaluation step, the best
        re-ranked escape (:meth:`select_avoidance`) is worth switching
        (composing) to over the currently-flown maneuver.  ``ds[0]``
        mirrors the predicted minimum 1-sigma cylinder distance of the
        trajectory being flown right now; ``ds[j]`` is the same metric
        for the best candidate composed on top of the active transform.
        Returns ``True`` when either

          1. the new escape is *safer by at least*
             ``switch_improve_ratio`` (so it is both farther from the
             intruder and "sufficiently different" — the anti-flicker
             margin), or
          2. the current maneuver is predicted to enter conflict
             (``ds[0] < alert_threshold``) and the new escape takes the
             ownship farther from the intruder (``ds[j] > ds[0]``).

        A currently-flown maneuver predicted to stay conflict-free
        (``ds[0]`` not finite) never switches — there is nothing to gain,
        so the ownship holds its committed escape.
        """
        cur_d = float(ds[self.baseline_idx])
        if not np.isfinite(cur_d):
            return False
        j     = self.select_avoidance(ds)
        new_d = float(ds[j])
        cond_better   = new_d >= cur_d * (1.0 + self.switch_improve_ratio)
        cond_conflict = (cur_d < self.alert_threshold) and (new_d > cur_d)
        return bool(cond_better or cond_conflict)

    # ------------------------------------------------------------------
    # Temporal-hysteresis (debounce) timers.
    # ------------------------------------------------------------------
    def _refresh_timers(self, ds: np.ndarray, t_now: float,
                        track_valid: bool = True) -> None:
        """Advance the engage / return debounce timers for this step.

        Idempotent within a single simulation step: a repeated call
        with the same ``t_now`` (e.g. :meth:`update_timers` then
        :meth:`step`) is a no-op so the continuity timers are not
        double-counted.  The alert and return-clear conditions are
        evaluated against the *baseline* and *return* candidate
        distances respectively; either condition going false on any
        step resets its timer, enforcing the "continuous window"
        semantics.

        ``track_valid`` is whether the intruder is currently tracked.
        On the step the track is lost (``True -> False`` transition) the
        return-clear window is restarted, so a full ``return_hysteresis_s``
        of clearance is required *after* the loss of track before the
        return fires — the hysteresis is never satisfied by separation
        accumulated while the intruder was still observed, nor bypassed
        by the loss of track itself.
        """
        if self._timers_t is not None and t_now == self._timers_t:
            return
        self._timers_t = t_now

        track_lost = self._track_valid_prev and not track_valid
        self._track_valid_prev = track_valid
        if track_lost:
            # Tracking discontinuity: restart the return debounce so the
            # full window is measured from the loss of track.
            self._clear_since = None

        alert_now        = bool(ds[self.baseline_idx] < self.alert_threshold)
        return_clear_now = bool(ds[self.return_idx]  >= self.alert_threshold)

        self._alert_since = (
            (t_now if self._alert_since is None else self._alert_since)
            if alert_now else None)
        self._clear_since = (
            (t_now if self._clear_since is None else self._clear_since)
            if return_clear_now else None)

        self._alert_confirmed = (
            self._alert_since is not None
            and (t_now - self._alert_since) >= self.engage_hysteresis_s)
        self._return_confirmed = (
            self._clear_since is not None
            and (t_now - self._clear_since) >= self.return_hysteresis_s)

    def update_timers(self, *, ds: np.ndarray, t_now: float,
                      track_valid: bool = True):
        """Refresh the debounce timers and return the confirmed flags.

        Returns ``(engage_confirmed, return_confirmed)`` — whether the
        alert / return-clear condition has been held continuously for
        at least ``engage_hysteresis_s`` / ``return_hysteresis_s``.
        Exposed so the caller can gate decisions that must precede
        :meth:`step` (e.g. classifying the encounter at the instant the
        maneuver is actually committed rather than on the first raw
        alert).  Calling this before :meth:`step` with the same
        ``t_now`` is safe: the timers advance exactly once per step.

        ``track_valid`` (see :meth:`_refresh_timers`) restarts the
        return-clear window when the track is lost.
        """
        self._refresh_timers(ds, t_now, track_valid)
        return self._alert_confirmed, self._return_confirmed

    # ------------------------------------------------------------------
    # Single-step update.
    # ------------------------------------------------------------------
    def step(self, *,
             t_now: float,
             p0: np.ndarray,
             v0: np.ndarray,
             track_point: np.ndarray,
             ds: np.ndarray,
             step_idx: int,
             sim,
             own_vel_cpa: Optional[np.ndarray] = None,
             cpa_ctx=None,
             track_valid: bool = True,
             cand_positions: Optional[np.ndarray] = None,
             periodic_eval: bool = False) -> int:
        """Advance the state machine by one simulation step.

        ``ds`` is the per-candidate min 1-sigma cylinder distance for
        this step.  The caller must have already arranged ``ds[0]`` to
        reflect the *currently flown* trajectory (the simulator's active
        route transform).  ``sim`` is the :class:`Simulator` driving the
        real flight; committing a maneuver applies the selected
        generator's :class:`RouteTransform` via ``sim.set_route_xf`` (so
        it takes effect on the next ``sim.step``).  ``track_point`` is
        the foot of the perpendicular from the ownship onto the active
        route (the simulator's per-step ``step`` output); it drives the
        ``RETURNING -> ROUTE`` cross-track test.  ``own_vel_cpa`` is the
        ownship velocity at the predicted CPA (NED); it orients the
        committed lateral escape to the starboard / port perpendicular
        of the CPA heading (``v0`` is the live-heading fallback).
        ``track_valid`` (see :meth:`_refresh_timers`) restarts the
        return-clear window when the track is lost.  ``cand_positions``
        is the per-candidate sampled lookahead for this step
        (``(K, M, 3)`` NED, the same buffer the avoidance loop scans);
        when an avoidance is committed this step it is used to snapshot
        the selected maneuver's safe point.  Returns the (possibly new)
        active candidate index.
        """
        # Advance the debounce timers (no-op if ``update_timers`` was
        # already called this step) and act on the *confirmed* signals:
        # the alert / return-clear condition must have persisted for the
        # the full ``engage_hysteresis_s`` / ``return_hysteresis_s`` window.
        self._refresh_timers(ds, t_now, track_valid)
        alert_confirmed  = self._alert_confirmed
        return_confirmed = self._return_confirmed

        # Default the gate to inactive; only the AVOIDING branch may set
        # it True for this step.
        self._safe_point_active = False

        if self.state == self.ROUTE:
            if alert_confirmed:
                self._engage_avoidance(t_now, p0, v0, sim,
                                       ds, step_idx, own_vel_cpa,
                                       cand_positions, cpa_ctx)

        elif self.state == self.AVOIDING:
            # FOV-loss safe-point gate: while the intruder is not
            # currently tracked the return is additionally gated on the
            # ownship having reached the safe point committed at the
            # start of the maneuver.  This prevents a track lost only
            # because the camera pointed away from the intruder (so the
            # return path looks artificially clear) from triggering a
            # premature return into a LoWC.  With the intruder still in
            # view the gate is inactive (``track_valid`` short-circuits).
            if not self._safe_point_reached:
                self._update_safe_point_reached(p0)
            safe_point_ok = track_valid or self._safe_point_reached
            # The gate is "active" (and the marker worth showing) only
            # when it is the thing holding back the return: a captured
            # safe point, the intruder out of view and the point not yet
            # crossed.
            self._safe_point_active = (
                self._safe_point is not None
                and not track_valid
                and not self._safe_point_reached)
            if self.closed_loop_mode == CLOSED_LOOP_PERIODIC:
                # Periodic closed-loop: on a re-evaluation step (the
                # caller raises ``periodic_eval`` on the fixed cadence and
                # has already sampled the full candidate set composed on
                # top of the active transform), switch (compose) to the
                # best candidate only when the anti-flicker rule accepts
                # it.  ``_engage_avoidance`` resets the alert window like
                # any other commit.
                if periodic_eval and self._periodic_switch_ok(ds):
                    self._engage_avoidance(t_now, p0, v0, sim,
                                           ds, step_idx, own_vel_cpa,
                                           cand_positions, cpa_ctx)
                elif return_confirmed and safe_point_ok:
                    self._engage_return(t_now, p0, v0, sim)
            elif self.closed_loop and alert_confirmed:
                # Closed-loop on new conflict: the currently-flown
                # (composed) maneuver is still in conflict, so stack
                # another escape on top of the active transform.
                # ``_engage_avoidance`` resets the alert window, so a
                # fresh full ``engage_hysteresis_s`` of continuous
                # conflict is required before the next layer — rate-
                # limiting the stacking and giving each added layer time
                # to take effect.
                self._engage_avoidance(t_now, p0, v0, sim,
                                       ds, step_idx, own_vel_cpa,
                                       cand_positions, cpa_ctx)
            elif return_confirmed and safe_point_ok:
                self._engage_return(t_now, p0, v0, sim)

        elif self.state == self.RETURNING:
            if alert_confirmed:
                # New conflict on the way back — re-engage avoidance.
                self._engage_avoidance(t_now, p0, v0, sim,
                                       ds, step_idx, own_vel_cpa,
                                       cand_positions, cpa_ctx)
            else:
                # Horizontal cross-track distance to the active route,
                # taken straight from the simulator-supplied
                # ``track_point`` (foot of the perpendicular from the
                # ownship onto the active route segment).
                tp = np.asarray(track_point, dtype=np.float64).reshape(-1)
                dh = float(np.hypot(p0[0] - tp[0], p0[1] - tp[1]))
                if dh < self.return_close_m:
                    self.state      = self.ROUTE
                    self.active_idx = self.baseline_idx
                    self.active_xf  = IDENTITY_TRANSFORM
                    # Back on the route: clear both debounce timers so
                    # the next engage / return starts a fresh window.
                    self._alert_since = None
                    self._clear_since = None

        return self.active_idx

    # ------------------------------------------------------------------
    # Internal transitions
    # ------------------------------------------------------------------
    def _engage_avoidance(self, t_now, p0, v0, sim,
                          ds, step_idx, own_vel_cpa=None,
                          cand_positions=None, cpa_ctx=None):
        j = self.select_avoidance(ds)
        # Resolve the selected maneuver's route transform (a
        # ``HOLD_VELOCITY`` transform for the constant-velocity
        # ``maintain``; an affine shift / speed_scale otherwise).  ``cpa_ctx``
        # sizes the ratio-based lateral / vertical escapes against the
        # intruder covariance at the CPA, frozen here at commit.
        delta = self.generators[j].transform(own_vel_cpa=own_vel_cpa,
                                              fwd_vel=v0,
                                              cpa_ctx=cpa_ctx)
        if self.closed_loop:
            # Closed-loop: stack the selected escape on top of the active
            # transform so successive maneuvers accumulate into a single
            # transform (the return later resets this to the identity).
            if delta is not None:
                self.active_xf = compose_route_xf(self.active_xf, delta)
            xf = self.active_xf
        else:
            # Open-loop (legacy): the selected transform replaces the
            # active one.  A candidate whose ``transform`` returns
            # ``None`` leaves the active transform unchanged.
            xf = delta
            if delta is not None:
                self.active_xf = delta
        if xf is not None:
            sim.set_route_xf(xf.shift, xf.speed_scale,
                             mode=xf.mode, velocity=xf.velocity,
                             track_p0=xf.track_p0, track_p1=xf.track_p1,
                             track_speed=xf.track_speed)
        # Snapshot the FOV-loss safe point from the selected maneuver's
        # lookahead at the start of the maneuver.
        self._capture_safe_point(j, cand_positions)
        self.state        = self.AVOIDING
        self.active_idx   = j
        self.maneuver_idx = j
        # Record this commit (one per ``_engage_avoidance`` call), so the
        # count includes closed-loop re-stacks of the same maneuver type.
        self.n_commits   += 1
        self.committed_names.append(self.generators[j].name)
        if self.maneuver_start < 0:
            self.maneuver_start = step_idx
        # Engaged: restart the return-clear window from scratch so the
        # return hysteresis measures continuous clearance *after* the
        # maneuver began, and restart the alert window so a closed-loop
        # re-stack requires a fresh continuous-conflict window (and a
        # RETURNING -> AVOIDING re-engage requires a fresh alert).
        self._clear_since = None
        self._alert_since = None

    # ------------------------------------------------------------------
    # FOV-loss safe-point helpers.
    # ------------------------------------------------------------------
    def _capture_safe_point(self, j: int,
                            cand_positions: Optional[np.ndarray]) -> None:
        """Snapshot the safe point from avoidance candidate ``j``.

        The safe point is the last lookahead sample of the selected
        maneuver and ``_safe_normal`` is the unit tangent there (last
        minus previous-to-last sample).  Rearms ``_safe_point_reached``.
        A degenerate lookahead (missing buffer, <2 samples or a
        zero-length end segment) leaves no geometry, which
        :meth:`_update_safe_point_reached` treats as already reached so
        the gate can never deadlock the return.
        """
        self._safe_point        = None
        self._safe_normal       = None
        self._safe_point_reached = False
        if cand_positions is None:
            return
        pos = np.asarray(cand_positions[j], dtype=np.float64)
        if pos.ndim != 2 or pos.shape[0] < 2:
            return
        end_seg = pos[-1, :3] - pos[-2, :3]
        seg_len = float(np.linalg.norm(end_seg))
        if seg_len < 1e-9:
            return
        self._safe_point  = pos[-1, :3].copy()
        self._safe_normal = end_seg / seg_len

    def _update_safe_point_reached(self, p0: np.ndarray) -> None:
        """Latch ``_safe_point_reached`` once the ownship crosses the
        plane through the safe point with normal ``_safe_normal``.

        Crossing is the signed projection of ``p0 - safe_point`` onto the
        normal becoming non-negative.  With no usable safe-point geometry
        the point is treated as already reached.
        """
        if self._safe_point is None or self._safe_normal is None:
            self._safe_point_reached = True
            return
        rel = np.asarray(p0, dtype=np.float64).reshape(-1)[:3] - self._safe_point
        if float(np.dot(rel, self._safe_normal)) >= 0.0:
            self._safe_point_reached = True

    def _engage_return(self, t_now, p0, v0, sim):
        # Returning = reset the single accumulated transform to the
        # identity so the simulator tracks the baseline route again from
        # the current (offset) state.  In closed-loop this drops the
        # whole stack of maneuvers at once (back to the original route).
        self.active_xf = IDENTITY_TRANSFORM
        xf = self.generators[self.return_idx].transform()
        if xf is not None:
            sim.set_route_xf(xf.shift, xf.speed_scale,
                             mode=xf.mode, velocity=xf.velocity,
                             track_p0=xf.track_p0, track_p1=xf.track_p1,
                             track_speed=xf.track_speed)
        self.state        = self.RETURNING
        self.active_idx   = self.return_idx
        self.maneuver_idx = self.return_idx
        # Returning: restart the alert window so a re-engage requires a
        # fresh continuous alert on the return path.
        self._alert_since = None
