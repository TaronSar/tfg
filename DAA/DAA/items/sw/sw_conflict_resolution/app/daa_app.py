#!/usr/bin/env python3
"""
DAA Avoidance — desktop application.

A PySide6 GUI front-end for the avoidance simulator that wraps:
  - ``avoidance_core.run_simulation``         (single encounter)
  - ``batch_avoidance._run_one``              (Monte Carlo batch)
  - ``visualize_avoidance.animate``           (3-D replay)

Designed to be packaged as a standalone Windows executable with
PyInstaller (see daa_app.spec).

Run from source:
    .venv\\Scripts\\python sw_conflict_resolution\\app\\daa_app.py
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# DLL search path (frozen bundle only).  Project modules are real installed
# packages (see pyproject.toml [tool.setuptools]) so no sys.path manipulation
# is needed; in source mode ``daa_dll`` locates the build output itself.
# ---------------------------------------------------------------------------
import multiprocessing
import os
import sys

if (getattr(sys, 'frozen', False) and sys.platform == 'win32'
        and hasattr(os, 'add_dll_directory')):
    _exe_dir = os.path.dirname(sys.executable)
    for _d in {getattr(sys, '_MEIPASS', _exe_dir), _exe_dir}:
        try:
            os.add_dll_directory(_d)
        except (OSError, FileNotFoundError):
            pass


# Force matplotlib onto the Qt backend so the visualiser shares our running
# Qt event loop (otherwise plt.show() can pick TkAgg / be non-blocking, and
# the FuncAnimation gets garbage collected as soon as ``animate`` returns).
import matplotlib  # noqa: E402
matplotlib.use('QtAgg', force=True)
import matplotlib.pyplot as _plt  # noqa: E402,F401  (registers the backend)


# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
import csv  # noqa: E402
import random  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ProcessPoolExecutor, as_completed  # noqa: E402

import numpy as np  # noqa: E402

# PySide6
from PySide6.QtCore import Qt, QThread, Signal, Slot  # noqa: E402
from PySide6.QtGui import QColor, QFont  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QAbstractSpinBox, QCheckBox, QComboBox, QDoubleSpinBox,
    QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QSpinBox, QSplitter, QStyle,
    QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit, QToolButton,
    QVBoxLayout, QWidget,
)

# Project modules
from daa_conflict_resolution.avoidance_core import (  # noqa: E402
    run_simulation, run_simulation_from_spec, make_spec_from_seed,
    LOOKAHEAD_S, DEFAULT_DT_S, CYL_HEIGHT_M, CYL_DIAMETER_M,
    ALERT_THRESHOLD, PROCESS_NOISE_STD, PROCESS_NOISE_OMEGA_STD_CTRA,
    _MEAS_NOISE, RANGE_NOISE_FRACTION,
    DEFAULT_FOV_AZ_MIN_DEG, DEFAULT_FOV_AZ_MAX_DEG,
    DEFAULT_FOV_EL_MIN_DEG, DEFAULT_FOV_EL_MAX_DEG,
    DEFAULT_TRACK_TIMEOUT_S,
    INIT_WINDOW, INIT_VELOCITY_STD, INIT_ACCEL_STD,
    INIT_VELOCITY_STD_VERTICAL, INIT_ACCEL_STD_VERTICAL,
    DEFAULT_ENERGY_COST_RATIOS,
    DEFAULT_HYSTERESIS_S, DEFAULT_RETURN_HYSTERESIS_S,
    CLOSED_LOOP_OPEN, CLOSED_LOOP_ON_CONFLICT, CLOSED_LOOP_PERIODIC,
    DEFAULT_CLOSED_LOOP_MODE,
    DEFAULT_SWITCH_IMPROVE_RATIO,
)
from daa_conflict_resolution.candidate_trajectories import (  # noqa: E402
    default_generators,
    DEFAULT_LATERAL_SHIFT_RATIO, DEFAULT_VERTICAL_SHIFT_RATIO,
    vertical_shift_m_nominal,
    DEFAULT_SLOWDOWN_RATIO,
    DEFAULT_MANEUVER_FAMILY,
    MANEUVER_FAMILY_SHIFTED, MANEUVER_FAMILY_MIN_BEARING,
    MANEUVER_FAMILY_MIN_CONST_BEARING,
    DEFAULT_K_XT_PER_M,
    DEFAULT_A_MAX_ALONG_M_S2,
    DEFAULT_RATE_MAX_AZIMUTH_RAD_S,
    DEFAULT_RATE_MAX_ELEVATION_RAD_S,
)
from daa_conflict_resolution.batch_avoidance import _run_one, CSV_FIELDS  # noqa: E402

from _version import __version__  # noqa: E402


# ---------------------------------------------------------------------------
# Embedded-estimator (UKF) motion-model metadata
# ---------------------------------------------------------------------------
# The process-noise σ changes meaning *and units* between models:
#   * CV  is a white-noise-**acceleration** model — σ is an acceleration
#     spectral density in m/s² (the unmodelled accel acting on the
#     constant-velocity assumption).
#   * CA / CAB are white-noise-**jerk** models — σ is a jerk density in
#     m/s³ (the unmodelled jerk acting on the constant-acceleration
#     assumption).
# Because CA/CAB integrate the noise one extra time, the same numeric σ
# inflates the predicted covariance (and the protection cylinders) far
# more than for CV, so each model carries its own sensible default.
_UKF_MODEL_META = {
    'cv': dict(
        q_default=PROCESS_NOISE_STD,
        q_unit='m/s²',
        q_max=1000.0,
        q_step=0.5,
        q_label='Process-noise σ (accel)',
        q_help=(
            'CV model: standard deviation of the unmodelled acceleration '
            'acting on the constant-velocity assumption (m/s², a white-'
            'noise-acceleration model). Larger values → the filter trusts '
            'the model less and reacts faster to maneuvering intruders, at '
            'the cost of noisier estimates and larger predicted '
            'covariances. Default: 10 m/s².'),
    ),
    'ca': dict(
        q_default=0.1,
        q_unit='m/s³',
        q_max=20.0,
        q_step=0.01,
        q_label='Process-noise σ (jerk)',
        q_help=(
            'CA model: standard deviation of the unmodelled jerk acting on '
            'the constant-acceleration assumption (m/s³, a white-noise-'
            'jerk model). NOTE the different quantity and units versus CV '
            '(acceleration, m/s²): because the jerk noise is integrated '
            'one extra time, the same numeric value inflates the predicted '
            'covariance much more, so both the default and the usable range '
            'are smaller. Default: 0.1 m/s³.'),
    ),
    'cab': dict(
        q_default=0.1,
        q_unit='m/s³',
        q_max=20.0,
        q_step=0.01,
        q_label='Process-noise σ (jerk)',
        q_help=(
            'CAB model: standard deviation of the unmodelled jerk acting on '
            'the constant-acceleration assumption in the intruder body '
            'frame (m/s³, a white-noise-jerk model). NOTE the different '
            'quantity and units versus CV (acceleration, m/s²): because '
            'the jerk noise is integrated one extra time, the same numeric '
            'value inflates the predicted covariance much more, so both the '
            'default and the usable range are smaller. Default: 0.1 m/s³.'),
    ),
    'ctra': dict(
        q_default=0.1,
        q_unit='m/s³',
        q_max=20.0,
        q_step=0.01,
        q_label='Process-noise σ (jerk / ang. accel)',
        q_help=(
            'CTRA model: standard deviation of the unmodelled jerk (m/s³) '
            'driving the tangential-acceleration state. As with CA / CAB '
            'the noise is integrated an extra time versus CV so the usable '
            'range is small. The turn-rate state carries a different '
            'physical quantity (angular acceleration, rad/s²) and is set '
            'with the separate "Turn-rate process-noise σ (CTRA)" knob '
            'below. NOTE: this model has no vertical-acceleration state '
            '(vertical speed is held constant); the initial vertical-'
            'acceleration sigma field is repurposed as the initial turn-'
            'rate sigma. Default: 0.1 m/s³.'),
    ),
}


# Avoidance-maneuver families exposed in the GUI, in display order:
# ``(family-id, label, tooltip)``.  The family selects how the four
# directional escapes (right / left / climb / descend) are constructed;
# the maintain and slow-down escapes are shared and unaffected.
_MANEUVER_FAMILY_META = (
    (MANEUVER_FAMILY_SHIFTED, 'Shifted route',
     'Each directional escape offsets the whole baseline route sideways '
     '(right / left) or vertically (climb / descend) by the configured '
     'shift, sized so the achieved cylinder distance at the CPA lands on '
     'the shift ratio. The ownship parallels its original route at an '
     'offset. This is the legacy behaviour.'),
    (MANEUVER_FAMILY_MIN_BEARING, 'Minimal bearing at start',
     'Each directional escape flies a fresh straight segment from the '
     'ownship current position that passes to the right / left / above / '
     'below the predicted intruder position at the CPA by the configured '
     'safety margin (the shift ratio). Minimises the initial bearing '
     'change; the straight track is committed at the start of the '
     'maneuver and flown fixed. In closed loop it is recomputed only when '
     'the maneuver re-stacks on a fresh continuous conflict, not every '
     'step.'),
    (MANEUVER_FAMILY_MIN_CONST_BEARING, 'Minimal constant bearing',
     'Each directional escape holds a single constant velocity vector, at '
     'the current ownship speed, aimed so the ownship passes to the '
     'right / left / above / below the predicted intruder position at the '
     'CPA by the configured safety margin (the shift ratio). The '
     'HOLD_VELOCITY analogue of "Minimal bearing at start": with both '
     'aircraft on constant velocities the line-of-sight bearing stays '
     'nearly constant. Unlike the external track there is no cross-track '
     'correction, so the acceleration-limited turn at commit leaves a '
     'small parallel offset that is not recovered. This is the default.'),
)


# Closed-loop (avoidance re-evaluation) modes exposed in the GUI, in
# display order: ``(mode-id, label, tooltip)``.  Selects how the FSM
# re-evaluates while flying an avoidance maneuver.
_CLOSED_LOOP_META = (
    (CLOSED_LOOP_OPEN, 'Open loop',
     'Legacy single-maneuver behaviour: the ownship commits one escape '
     'and flies it until the conflict clears, then returns to the route. '
     'No re-evaluation while avoiding.'),
    (CLOSED_LOOP_ON_CONFLICT, 'Closed loop on new conflict',
     'While avoiding, the ownship keeps checking and stacks a fresh '
     'escape on top of the active one whenever the currently-flown '
     'maneuver is still confirmed in conflict (each added layer requires '
     'a fresh continuous-conflict hysteresis window). Successive escapes '
     'compose into one transform that the return resets to the original '
     'route.'),
    (CLOSED_LOOP_PERIODIC, 'Closed loop periodic',
     'While avoiding, the ownship re-evaluates the full escape set on a '
     'fixed cadence (the re-eval interval) and switches (stacks) to a '
     'better escape only when the anti-flicker rule is met: the new '
     'escape is safer by at least the improvement ratio, or the current '
     'maneuver is predicted to enter conflict and the new one is farther '
     'from the intruder. This is the default.'),
)


# The "Init acceleration σ (vertical)" spinner is repurposed by the CTRA
# model as the initial turn-rate σ (the CTRA state carries no vertical
# acceleration).  The two readings have different quantities, units and
# sensible ranges, so the widget is reconfigured when the model changes.
# The vertical-accel seed is small (1.5 m/s²): at first sighting cruise
# is level, so a ~= 0 with a tight initial covariance is the right prior
# (the process noise still tracks a genuine vertical manoeuvre).  Read as
# a turn rate, though, even a few m/s² is several rad/s ≈ hundreds of °/s
# of 1-σ uncertainty — absurd, and it blows the predicted heading (hence
# position) envelope up over the lookahead.  A standard-rate turn is
# ~3 °/s; an aggressive UAV turn ~10–20 °/s.  The seed is the 1-σ
# UNCERTAINTY of the (unknown) initial turn rate, not the turn rate
# itself: the covariance sweep shows a 0.15 rad/s seed fans horizontal
# position out past 600 kft over a 60 s lookahead, 0.05 rad/s is still
# bad, and ≤0.02 rad/s stays bounded (updates then discover any real
# turn), so 0.02 rad/s is the default.
_INIT_ACC_VERT_PROFILE = {
    # quantity              suffix      lo    hi    step  decimals default
    'accel': dict(suffix=' m/s²', lo=0.0, hi=500.0, step=0.5,
                  decimals=2, default=INIT_ACCEL_STD_VERTICAL,
                  label='Init acceleration σ (vertical)',
                  help=(
                      'First-sighting bootstrap: separate 1-σ (m/s²) for '
                      'the vertical (down) acceleration. Used only by the '
                      'CA / CAB motion models. This is the INITIAL '
                      'covariance only — cruise is level, so a tight seed '
                      'encodes that straight-and-level prior; the process '
                      'noise still grows the estimate for a genuine '
                      'vertical manoeuvre, so a small seed does not make '
                      'the tracker sluggish. A wide seed instead integrates '
                      'twice into altitude and fans the envelope out over '
                      'the lookahead. Default: 0.75 m/s².')),
    'turn_rate': dict(suffix=' rad/s', lo=0.0, hi=5.0, step=0.01,
                      decimals=3, default=0.02,
                      label='Init turn-rate σ (CTRA)',
                      help=(
                          'First-sighting bootstrap for the CTRA model: '
                          '1-σ of the initial turn-rate (rad/s). The CTRA '
                          'state has no vertical acceleration, so this '
                          'spinner is repurposed as the turn-rate seed. A '
                          'standard-rate turn is ~3 °/s (0.05 rad/s); an '
                          'aggressive UAV turn ~10–20 °/s. Keep it small — '
                          'an over-large seed fans the predicted heading '
                          '(and hence position) envelope out over the '
                          'lookahead (0.15 rad/s → >600 kft at 60 s). '
                          'Default: 0.02 rad/s (≈1.1 °/s).')),
}


# CTRA carries two manoeuvre states with different physical quantities —
# tangential acceleration (driven by the lumped "Process-noise σ" knob,
# a jerk in m/s³) and turn rate — so the turn-rate channel needs its
# own, much smaller process-noise σ (an angular acceleration, rad/s²).
# This dedicated spinner exposes it; it is enabled only for the CTRA
# model (the CV / CA / CAB models have no turn-rate state and ignore it).
_Q_OMEGA_CTRA = dict(
    default=PROCESS_NOISE_OMEGA_STD_CTRA,
    lo=0.0, hi=1.0, step=0.001, decimals=4, suffix=' rad/s²',
    label='Turn-rate process-noise σ (CTRA)',
    help=(
        'CTRA model only: standard deviation of the unmodelled angular '
        'acceleration driving the turn-rate state (rad/s²). The main '
        '"Process-noise σ" knob above drives the tangential-acceleration '
        '(jerk) channel; the turn-rate channel carries a different '
        'physical quantity and needs its own, much smaller noise, so it '
        'is set separately here. Keep it small — the turn-rate channel '
        'feeds heading and hence position, so an over-large value fans '
        'the predicted envelope out over the lookahead. Disabled for the '
        'CV / CA / CAB models. Default: 0.002 rad/s².'),
)


# ---------------------------------------------------------------------------
# Parameter container
# ---------------------------------------------------------------------------
class ParamSet:
    """Plain container shared between tabs."""
    def __init__(self):
        self.lookahead         = LOOKAHEAD_S
        self.dt                = DEFAULT_DT_S
        self.cyl_h             = CYL_HEIGHT_M
        self.cyl_d             = CYL_DIAMETER_M
        self.alert_threshold   = ALERT_THRESHOLD
        # Temporal hysteresis (s) on the FSM maneuver transitions.
        # The alert must persist continuously for ``engage_hysteresis_s``
        # before an avoidance maneuver is committed; the return path must
        # stay clear continuously for ``return_hysteresis_s`` before the
        # return-to-route starts.  0 = act on the first qualifying step.
        self.engage_hysteresis_s = DEFAULT_HYSTERESIS_S
        self.return_hysteresis_s = DEFAULT_RETURN_HYSTERESIS_S
        # Avoidance re-evaluation policy (closed-loop mode):
        #   'open'        — legacy single-maneuver (open-loop) behaviour.
        #   'on_conflict' — keep checking while avoiding and stack a fresh
        #                   escape whenever the flown maneuver is still
        #                   confirmed in conflict.
        #   'periodic'    — re-check on a fixed cadence
        #                   (``periodic_interval_s``) and switch (stack)
        #                   to a better escape only when the anti-flicker
        #                   margin (``switch_improve_ratio``) is met.
        # The two closed-loop modes both compose successive escapes into
        # one transform that the return resets to the original route.
        self.closed_loop_mode  = DEFAULT_CLOSED_LOOP_MODE
        # Periodic-mode re-evaluation interval (s) and anti-flicker
        # improvement ratio (fractional CPA-distance gain required before
        # switching escapes).  Ignored unless ``closed_loop_mode`` is
        # 'periodic'.
        self.periodic_interval_s   = 1.0
        self.switch_improve_ratio  = float(DEFAULT_SWITCH_IMPROVE_RATIO)
        # Escape-shift sizing expressed as a ratio of the protection-
        # cylinder dimension (plus the intruder uncertainty) targeted at
        # the predicted CPA: a ratio of 1.0 makes the *ideal* scored
        # cylinder distance exactly 1 at CPA (grazing the boundary for a
        # perfectly-flown collision-course escape); the 1.5 default keeps
        # a 50 % safety margin.  Only the ratio is stored — the GUI shows
        # it as a percentage and the metres shift is resolved at the CPA
        # site (against the live cylinder and the intruder covariance)
        # inside the candidate generators.
        self.lateral_shift_ratio  = DEFAULT_LATERAL_SHIFT_RATIO
        self.vertical_shift_ratio = DEFAULT_VERTICAL_SHIFT_RATIO
        self.slowdown_ratio    = DEFAULT_SLOWDOWN_RATIO
        # Avoidance-maneuver family: how the right / left / up / down
        # escapes are constructed.  ``'min_const_bearing'`` (default)
        # holds a single constant velocity aimed to clear the predicted
        # intruder CPA by the safety margin; ``'shifted'`` offsets the
        # whole baseline route; ``'min_bearing'`` flies a fresh straight
        # segment from the current position that clears the predicted
        # intruder CPA by the safety margin.  See
        # candidate_trajectories.directional_escape.
        self.maneuver_family   = DEFAULT_MANEUVER_FAMILY
        self.k_xt              = DEFAULT_K_XT_PER_M
        self.a_max_along       = DEFAULT_A_MAX_ALONG_M_S2
        self.rate_max_azimuth   = DEFAULT_RATE_MAX_AZIMUTH_RAD_S
        self.rate_max_elevation = DEFAULT_RATE_MAX_ELEVATION_RAD_S
        # Velocity envelope (spherical form).
        #
        # ``v_max`` caps the speed module; a large value means
        # "effectively unlimited".  ``v_min`` is a stall guard on the
        # speed module; 0 disables it.  ``el_min`` / ``el_max`` bound
        # the flight-path angle (rad, positive-up climb / negative
        # descent).  Mirrors DAA::Flight_envelope.
        self.v_max  = 91.44    # m/s (~178 kt) speed-module cap
        self.v_min  = 0.0      # m/s stall guard (0 = off)
        self.el_min = -0.2618  # rad (~ -15°) steepest descent
        self.el_max =  0.2618  # rad (~  15°) steepest climb
        # Altitude envelope (m AGL, positive-up).  The encounter
        # classifier derives the ownship altitude band (Cases 14 / 15)
        # from the ownship altitude at CPA against these limits: a
        # climb is barred near ``alt_max`` and a descent near
        # ``alt_min`` (within the vertical-shift margin).  Defaults are
        # wide enough that a nominal cruise (304.8 m AGL) stays in the
        # mid band; set them tighter to exercise the ceiling / floor.
        self.alt_min                = 0.0     # m AGL
        self.alt_max                = 609.6  # m AGL
        self.process_noise_std = PROCESS_NOISE_STD
        # CTRA-only: process-noise std for the turn-rate (angular accel,
        # rad/s²) channel.  The lumped ``process_noise_std`` knob drives
        # the tangential-acceleration channel; the turn-rate channel
        # carries a different physical quantity and needs its own,
        # much smaller noise, so it is exposed separately.  Ignored by
        # the CV / CA / CAB models.
        self.process_noise_omega = float(PROCESS_NOISE_OMEGA_STD_CTRA)
        self.sigma_az          = float(_MEAS_NOISE['azimuth_rad'])
        self.sigma_el          = float(_MEAS_NOISE['elevation_rad'])
        # Range-measurement 1-sigma noise as a percentage of the measured
        # distance: the vision system's range error grows with range, so
        # this is expressed as a fraction of distance rather than a fixed
        # number of metres.
        self.range_noise_pct   = float(RANGE_NOISE_FRACTION * 100.0)
        # Embedded intruder estimator motion model: 'cv' (constant
        # velocity), 'ca' (constant acceleration, NED) or 'cab'
        # (constant acceleration, body frame).
        self.ukf_model         = 'cv'
        # Track-reset timeout (s): how long the intruder may stay out
        # of the camera FOV before its estimate is dropped and must be
        # re-initialised from a fresh sighting.  Lives with the UKF
        # parameters as it governs the estimator lifecycle.
        self.track_timeout     = float(DEFAULT_TRACK_TIMEOUT_S)
        # First-sighting bootstrap seed.  The C++ estimator is
        # initialised straight from the measurement with a zero
        # velocity / acceleration seed; these 1-sigma values size that
        # initial uncertainty, and the track is held back from scoring
        # until ``init_window`` consecutive in-FOV frames have settled
        # the wide bootstrap covariance.
        self.init_window       = int(INIT_WINDOW)
        self.init_velocity_std = float(INIT_VELOCITY_STD)
        # When on, the bootstrap sizes the horizontal velocity covariance
        # per sighting to the two-point finite-difference velocity variance
        # (2 * transverse_pos_var / dt^2), ignoring ``init_velocity_std``.
        self.fd_init_vel = False
        self.init_accel_std    = float(INIT_ACCEL_STD)
        self.init_velocity_std_vertical = float(INIT_VELOCITY_STD_VERTICAL)
        self.init_accel_std_vertical    = float(INIT_ACCEL_STD_VERTICAL)
        self.n_sigma           = 1.0   # only used by the visualiser
        # Camera field of view (deg, body frame).  The ownship can only
        # track the intruder while its bearing lies inside this cone.
        self.fov_az_min        = float(DEFAULT_FOV_AZ_MIN_DEG)
        self.fov_az_max        = float(DEFAULT_FOV_AZ_MAX_DEG)
        self.fov_el_min        = float(DEFAULT_FOV_EL_MIN_DEG)
        self.fov_el_max        = float(DEFAULT_FOV_EL_MAX_DEG)
        # Per-maneuver energy-cost ratios used by the avoidance FSM to
        # rank the escapes a multi-escape case permits.  A copy of the
        # library defaults; the parameter panel edits this in place and
        # Custom-tab presets overwrite individual entries.
        self.energy_cost_ratios = dict(DEFAULT_ENERGY_COST_RATIOS)

    def as_sim_kwargs(self) -> dict:
        return dict(
            lookahead=self.lookahead,
            dt=self.dt,
            cyl_h=self.cyl_h,
            cyl_d=self.cyl_d,
            alert_threshold=self.alert_threshold,
            engage_hysteresis_s=self.engage_hysteresis_s,
            return_hysteresis_s=self.return_hysteresis_s,
            closed_loop_mode=self.closed_loop_mode,
            periodic_interval_s=self.periodic_interval_s,
            switch_improve_ratio=self.switch_improve_ratio,
            k_xt=self.k_xt,
            a_max_along=self.a_max_along,
            rate_max_azimuth=self.rate_max_azimuth,
            rate_max_elevation=self.rate_max_elevation,
            v_max=self.v_max,
            v_min=self.v_min,
            el_min=self.el_min,
            el_max=self.el_max,
            alt_min_m=self.alt_min,
            alt_max_m=self.alt_max,
            alt_margin_m=vertical_shift_m_nominal(self.vertical_shift_ratio,
                                                  self.cyl_h),
            process_noise_std=self.process_noise_std,
            process_noise_omega=self.process_noise_omega,
            meas_noise={
                'azimuth_rad':   self.sigma_az,
                'elevation_rad': self.sigma_el,
            },
            range_noise_fraction=self.range_noise_pct / 100.0,
            ukf_model=self.ukf_model,
            fov_az_min_deg=self.fov_az_min,
            fov_az_max_deg=self.fov_az_max,
            fov_el_min_deg=self.fov_el_min,
            fov_el_max_deg=self.fov_el_max,
            track_timeout_s=self.track_timeout,
            init_window=self.init_window,
            init_velocity_std=self.init_velocity_std,
            finite_difference_init_velocity=self.fd_init_vel,
            init_accel_std=self.init_accel_std,
            init_velocity_std_vertical=self.init_velocity_std_vertical,
            init_accel_std_vertical=self.init_accel_std_vertical,
            energy_cost_ratios=dict(self.energy_cost_ratios),
        )

    def as_batch_kwargs(self) -> dict:
        return dict(
            lookahead=self.lookahead,
            cyl_h=self.cyl_h,
            cyl_d=self.cyl_d,
            lateral_shift_ratio=self.lateral_shift_ratio,
            vertical_shift_ratio=self.vertical_shift_ratio,
            slowdown_ratio=self.slowdown_ratio,
            maneuver_family=self.maneuver_family,
            k_xt=self.k_xt,
            a_max_along=self.a_max_along,
            rate_max_azimuth=self.rate_max_azimuth,
            rate_max_elevation=self.rate_max_elevation,
            v_max=self.v_max,
            v_min=self.v_min,
            el_min=self.el_min,
            el_max=self.el_max,
            alert_threshold=self.alert_threshold,
            engage_hysteresis_s=self.engage_hysteresis_s,
            return_hysteresis_s=self.return_hysteresis_s,
            closed_loop_mode=self.closed_loop_mode,
            periodic_interval_s=self.periodic_interval_s,
            switch_improve_ratio=self.switch_improve_ratio,
            process_noise_std=self.process_noise_std,
            process_noise_omega=self.process_noise_omega,
            ukf_model=self.ukf_model,
            sigma_az=self.sigma_az,
            sigma_el=self.sigma_el,
            range_noise_fraction=self.range_noise_pct / 100.0,
            finite_difference_init_velocity=self.fd_init_vel,
        )

    def make_generators(self):
        return default_generators(
            lateral_shift_ratio=self.lateral_shift_ratio,
            vertical_shift_ratio=self.vertical_shift_ratio,
            slowdown_ratio=self.slowdown_ratio,
            maneuver_family=self.maneuver_family,
        )


# ---------------------------------------------------------------------------
# Worker threads
# ---------------------------------------------------------------------------
def _first_escape_idx(r) -> int:
    """Index of the first genuine avoidance escape committed during a run.

    ``maneuver_idx`` is overwritten with the return-to-route candidate
    once the maneuver completes and the ownship rejoins the route, so it
    cannot be used to report *which* escape was flown.  Recover the real
    escape from the per-step ``flown_idx`` history (route = -1, the last
    candidate = return-to-route).  Falls back to ``maneuver_idx`` when no
    history is available."""
    names = r.candidate_names
    if not len(names):
        return -1
    return_idx = len(names) - 1
    fi = getattr(r, 'flown_idx', None)
    if fi is not None and len(fi):
        for k in fi:
            k = int(k)
            if 1 <= k < return_idx:
                return k
    return int(r.maneuver_idx)


def _format_result_summary(r, seed=None) -> str:
    """Render an ``AvoidanceResult`` as the monospace text shown in the
    Single-seed / Custom tabs.  ``seed`` may be ``None`` (custom mode)."""
    triggered = (r.maneuver_idx >= 0)
    escape_idx = _first_escape_idx(r)
    man_name = (r.candidate_names[escape_idx]
                if triggered and 0 <= escape_idx < len(r.candidate_names)
                else '—')
    # Committed-escape sequence (one entry per commit, so closed-loop
    # re-stacks of the same maneuver type are all counted, not
    # collapsed).  ``n_commits`` matches the route-transform plot.
    committed = tuple(getattr(r, 'committed_names', ()) or ())
    n_commits = int(getattr(r, 'n_commits', len(committed)))
    # Compact run-length-encoded label, e.g. "slow_down → right_shift ×4".
    seq_parts = []
    _prev, _run = None, 0
    for _nm in committed:
        if _nm == _prev:
            _run += 1
        else:
            if _prev is not None:
                seq_parts.append(_prev if _run == 1 else f'{_prev} ×{_run}')
            _prev, _run = _nm, 1
    if _prev is not None:
        seq_parts.append(_prev if _run == 1 else f'{_prev} ×{_run}')
    seq_str = ' → '.join(seq_parts) if seq_parts else '—'
    d_base = r.d_candidates[:, 0]
    d_chosen = (r.d_candidates[:, escape_idx]
                if triggered and 0 <= escape_idx < r.d_candidates.shape[1]
                else np.empty(0))
    ec = r.encounter
    seed_str = '—' if seed is None else str(seed)
    lines = [
        f'Seed:                       {seed_str}',
        f'Steps:                      {len(r.times)}',
        f'Classification:             {r.classification}',
        f'',
        f'Ground-truth without maneuver:',
        f'   min cyl distance (LoWC): {r.cyldist_min_no_maneuver:.4f}',
        f'   loss of well-clear:      {bool(r.lowc_no_maneuver)}',
        f'Ground-truth with maneuver:',
        f'   min cyl distance:        {r.cyldist_min_maneuver:.4f}',
        f'   loss of well-clear:      {bool(r.lowc_maneuver)}',
        f'',
        f'Maneuver triggered:         {triggered}',
        f'   maneuvers committed:     {n_commits}',
        f'   first escape:            {man_name}',
    ]
    if n_commits > 1:
        lines.append(f'   sequence:                {seq_str}')
    lines.append(f'   min 1-σ d, baseline:     {float(d_base.min()):.4f}')
    if d_chosen.size:
        lines.append(f'   min 1-σ d, chosen:       {float(d_chosen.min()):.4f}')
    # Encounter classifications — one per committed maneuver shift (the
    # core re-classifies on every commit, including each closed-loop
    # re-stack), paired with the committed escape.  Falls back to the
    # single ``encounter`` alias for older results.
    encs = tuple(getattr(r, 'encounters', ()) or ())
    if not encs and ec is not None:
        encs = (ec,)
    if encs:
        if len(encs) == 1:
            lines += ['', 'Encounter classification:']
        else:
            lines += ['', f'Encounter classifications ({len(encs)}):']
        for _i, _ec in enumerate(encs):
            if len(encs) > 1:
                _nm = committed[_i] if _i < len(committed) else '—'
                lines.append(f'   [{_i + 1}] commit:             {_nm}')
            lines += [
                f'   case:                    {_ec.case_id} ({_ec.geometry})',
                f'   manoeuvre:               {_ec.maneuver}',
                f'   crossing angle:          {_ec.crossing_angle_deg:.1f}°',
                f'   relative bearing:        {_ec.relative_bearing_deg:.1f}°',
                f'   Δh (intruder − ownship): {_ec.delta_h_m:+.1f} m',
                f'   CPA trend:               {_ec.cpa_trend}',
                f'   own gives way:           {bool(_ec.own_gives_way)}',
                f'   compliant actions:       {", ".join(_ec.compliant_actions) or "—"}',
            ]
            if len(encs) > 1 and _i < len(encs) - 1:
                lines.append('')
    return '\n'.join(lines)


class SingleSimWorker(QThread):
    """Runs ``run_simulation`` for a single seed in a background thread."""
    finished_ok = Signal(object, int)         # (AvoidanceResult, seed)
    failed      = Signal(str)

    def __init__(self, seed: int, params: ParamSet, parent=None):
        super().__init__(parent)
        self.seed = int(seed)
        self.params = params

    def run(self):  # noqa: D401
        try:
            spec = make_spec_from_seed(self.seed)
            result = run_simulation_from_spec(
                spec,
                generators=self.params.make_generators(),
                **self.params.as_sim_kwargs(),
                record_history=True,
            )
            self.finished_ok.emit(result, self.seed)
        except Exception as exc:                                  # noqa: BLE001
            self.failed.emit(f'{type(exc).__name__}: {exc}')


class CustomSimWorker(QThread):
    """Runs ``run_simulation`` for user-supplied waypoints in a
    background thread (mirrors :class:`SingleSimWorker` but feeds the
    waypoints directly, bypassing the seeded generator)."""
    finished_ok = Signal(object)              # AvoidanceResult
    failed      = Signal(str)

    def __init__(self, own_waypoints, own_init_pos, own_init_vel,
                 intr_waypoints, dt: float, params: ParamSet,
                 encounter_meta: dict = None, parent=None):
        super().__init__(parent)
        self.own_waypoints  = own_waypoints
        self.own_init_pos   = own_init_pos
        self.own_init_vel   = own_init_vel
        self.intr_waypoints = intr_waypoints
        # Per-encounter classifier inputs (intruder category,
        # alerting count).  Empty dict ⇒ classifier defaults
        # (single intruder).  The ownship
        # altitude band (Cases 14 / 15) is no longer carried here: it
        # is derived from the ownship altitude vs the flight-envelope
        # altitude limits forwarded via ``as_sim_kwargs``.
        self.encounter_meta = dict(encounter_meta or {})
        # ``dt`` is carried on ``params`` (forwarded via as_sim_kwargs);
        # accept it here for the legacy positional caller and write
        # through to params so a single source of truth wins.
        params.dt           = float(dt)
        self.params         = params

    def run(self):  # noqa: D401
        try:
            result = run_simulation(
                own_waypoints  = self.own_waypoints,
                own_p0         = self.own_init_pos,
                own_init_vel   = self.own_init_vel,
                intr_waypoints = self.intr_waypoints,
                generators=self.params.make_generators(),
                **self.encounter_meta,
                **self.params.as_sim_kwargs(),
                record_history=True,
            )
            self.finished_ok.emit(result)
        except Exception as exc:                                  # noqa: BLE001
            self.failed.emit(f'{type(exc).__name__}: {exc}')


class BatchWorker(QThread):
    """Runs the Monte Carlo batch using a process pool, emitting per-row
    progress so the UI can update a progress bar / table live."""
    row_done = Signal(int, int, dict)         # (done, total, row)
    finished_ok = Signal(list)                # rows
    failed     = Signal(str)

    def __init__(self, seeds, params: ParamSet, workers: int, parent=None):
        super().__init__(parent)
        self.seeds = list(seeds)
        self.params = params
        self.workers = max(1, int(workers))
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):  # noqa: D401
        try:
            rows = []
            total = len(self.seeds)
            sim_kw = self.params.as_batch_kwargs()
            if self.workers == 1:
                for k, s in enumerate(self.seeds, 1):
                    if self._stop:
                        break
                    row = _run_one(s, **sim_kw)
                    rows.append(row)
                    self.row_done.emit(k, total, row)
            else:
                with ProcessPoolExecutor(max_workers=self.workers) as ex:
                    futures = {ex.submit(_run_one, s, **sim_kw): s
                               for s in self.seeds}
                    done = 0
                    for fut in as_completed(futures):
                        if self._stop:
                            for f in futures:
                                f.cancel()
                            break
                        row = fut.result()
                        rows.append(row)
                        done += 1
                        self.row_done.emit(done, total, row)
                rows.sort(key=lambda r: int(r['seed']))
            self.finished_ok.emit(rows)
        except Exception as exc:                                  # noqa: BLE001
            self.failed.emit(f'{type(exc).__name__}: {exc}')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
# Spin boxes / combo boxes that ignore mouse-wheel scrolling so that
# scrolling the parameter panel never accidentally changes a value.  The
# wheel event is ignored (not consumed) so it propagates up to the
# enclosing scroll area, which scrolls as expected.  Values can still be
# edited by typing, the arrow keys, or the spin buttons.
class _NoWheelSpinBox(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)

    def wheelEvent(self, event):
        event.ignore()


class _NoWheelDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)

    def wheelEvent(self, event):
        event.ignore()


class _NoWheelComboBox(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()


def _dspin(value: float, *, lo=0.0, hi=1e6, step=1.0, decimals=2, suffix=''):
    w = _NoWheelDoubleSpinBox()
    w.setRange(lo, hi)
    w.setSingleStep(step)
    w.setDecimals(decimals)
    w.setValue(value)
    if suffix:
        w.setSuffix(' ' + suffix)
    w.setMinimumWidth(140)
    return w


def _with_help(widget: QWidget, help_text,
               title: str = 'Parameter help') -> QWidget:
    """Wrap ``widget`` with a trailing '?' button that pops ``help_text``.

    The same text is also installed as the widget's tool-tip so it shows
    on hover.  ``help_text`` may be a plain string or a zero-argument
    callable returning the current text, so callers can refresh the help
    live (e.g. when a related selector changes).
    """
    def _text():
        return help_text() if callable(help_text) else help_text
    widget.setToolTip(_text())
    btn = QToolButton()
    btn.setText('?')
    btn.setToolTip(_text())
    btn.setAutoRaise(True)
    btn.setFixedWidth(24)
    btn.setCursor(Qt.WhatsThisCursor)
    btn.clicked.connect(
        lambda _=False, ti=title:
        QMessageBox.information(widget.window(), ti, _text()))
    box = QWidget()
    h = QHBoxLayout(box)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(4)
    h.addWidget(widget, 1)
    h.addWidget(btn, 0, Qt.AlignVCenter)
    return box


# ---------------------------------------------------------------------------
# Parameter panel (always visible on the left of the main window)
# ---------------------------------------------------------------------------
class ParameterPanel(QWidget):
    """Persistent left-hand panel holding every simulation parameter.

    Edits apply live: each spinner writes straight through to the
    shared :class:`ParamSet` so the next run on any tab picks up the
    current values without an explicit Apply step.
    """

    def __init__(self, params: ParamSet, parent=None):
        super().__init__(parent)
        self.params = params

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        # Keep the legacy variable name so the group-box body below is
        # unchanged; it now fills the scroll-area content widget.
        outer = QVBoxLayout(content)

        # ---- Detection / alerting ----
        gb_alert = QGroupBox('Conflict detection')
        f1 = QFormLayout(gb_alert)
        self.sb_lookahead = _dspin(params.lookahead, lo=1, hi=600,
                                   step=5, decimals=1, suffix='s')
        self.sb_dt        = _dspin(params.dt, lo=0.01, hi=1.0,
                                   step=0.01, decimals=3, suffix='s')
        self.sb_cyl_d     = _dspin(params.cyl_d, lo=10, hi=20000,
                                   step=100, decimals=1, suffix=' m')
        self.sb_cyl_h     = _dspin(params.cyl_h, lo=10, hi=20000,
                                   step=100, decimals=1, suffix=' m')
        self.sb_alert     = _dspin(params.alert_threshold, lo=0.0, hi=10.0,
                                   step=0.05, decimals=2)
        f1.addRow('Look-ahead time', _with_help(
            self.sb_lookahead,
            'How far ahead, in seconds, each candidate ownship trajectory '
            'is propagated and compared against the intruder prediction. '
            'Longer look-aheads detect conflicts earlier but are more '
            'sensitive to estimator uncertainty. Default: 60 s.'))
        f1.addRow('Time step (dt)', _with_help(
            self.sb_dt,
            'Single time-resolution knob: sets the airframe re-decision '
            'cadence, the UKF predict step, and the spacing of the '
            'lookahead sampling grid. Default: 0.1 s.'))
        f1.addRow('Protection cylinder Ø', _with_help(
            self.sb_cyl_d,
            'Diameter (m) of the cylindrical "well-clear" volume centred '
            'on the ownship. A loss-of-well-clear (LoWC) event is recorded '
            'whenever the intruder lies inside this cylinder. '
            'Default: 609.6 m.'))
        f1.addRow('Protection cylinder H', _with_help(
            self.sb_cyl_h,
            'Total height (m) of the cylindrical well-clear volume '
            '(± H/2 above/below the ownship). Default: 304.8 m.'))
        f1.addRow('Alert threshold (1-σ)', _with_help(
            self.sb_alert,
            'Normalised minimum cylinder distance below which the baseline '
            '("do-nothing") trajectory is flagged as in conflict. The '
            'distance is normalised so 1.0 means the intruder\'s 1-σ '
            'uncertainty volume just touches the protection cylinder; '
            'lower thresholds = fewer / later alerts. Default: 1.0.'))
        outer.addWidget(gb_alert)

        # ---- Maneuver shaping ----
        gb_man = QGroupBox('Avoidance maneuvers')
        f2 = QFormLayout(gb_man)
        # Maneuver-set selector (top of the panel): picks how the four
        # directional escapes are built.  More sets can be appended to
        # _MANEUVER_FAMILY_META.
        self.cb_maneuver_family = _NoWheelComboBox()
        _man_family_help = []
        for _fam_id, _fam_label, _fam_help in _MANEUVER_FAMILY_META:
            self.cb_maneuver_family.addItem(_fam_label, _fam_id)
            _man_family_help.append('• %s — %s' % (_fam_label, _fam_help))
        _man_idx = self.cb_maneuver_family.findData(params.maneuver_family)
        self.cb_maneuver_family.setCurrentIndex(_man_idx if _man_idx >= 0
                                                else 0)
        self.sb_lat   = _dspin(params.lateral_shift_ratio * 100.0,
                               lo=10, hi=1000,
                               step=10, decimals=0, suffix=' %')
        self.sb_vert  = _dspin(params.vertical_shift_ratio * 100.0,
                               lo=10, hi=1000,
                               step=10, decimals=0, suffix=' %')
        self.sb_slow  = _dspin(params.slowdown_ratio, lo=0.05, hi=1.0,
                               step=0.05, decimals=2)
        self.sb_kxt    = _dspin(params.k_xt, lo=0.0001, hi=0.05,
                                step=0.0005, decimals=4, suffix='1/m')
        self.sb_engage_hysteresis = _dspin(params.engage_hysteresis_s,
                                     lo=0.0, hi=60.0,
                                     step=0.5, decimals=2, suffix='s')
        self.sb_return_hysteresis = _dspin(params.return_hysteresis_s,
                                     lo=0.0, hi=60.0,
                                     step=0.5, decimals=2, suffix='s')
        f2.addRow('Maneuver set', _with_help(
            self.cb_maneuver_family,
            'Set of avoidance maneuvers to consider. The right / left / '
            'climb / descend escapes differ between sets; the maintain '
            'and slow-down escapes are shared.\n\n'
            + '\n'.join(_man_family_help)))
        f2.addRow('Lateral shift (right)', _with_help(
            self.sb_lat,
            'Lateral offset of the "shift right" escape route, sized as a '
            'percentage of the protection-cylinder radius (cyl_d/2). 100 % '
            'means a perfectly-flown collision-course escape just grazes the '
            'cylinder (ideal cyldist = 1 at CPA); 150 % keeps a 50 % safety '
            'margin. Default: 150 %.'))
        f2.addRow('Vertical shift (climb/desc)', _with_help(
            self.sb_vert,
            'Vertical offset of the climb and descend escape routes, sized as '
            'a percentage of the protection-cylinder half-height (cyl_h/2). '
            '100 % means a perfectly-flown collision-course escape just grazes '
            'the cylinder (ideal cyldist = 1 at CPA); 150 % keeps a 50 % safety '
            'margin. Default: 150 %.'))
        f2.addRow('Slow-down ratio', _with_help(
            self.sb_slow,
            'Speed-reduction factor of the along-track "slow down" escape. '
            'During the maneuver the horizontal speed is capped at this '
            'fraction of the ownship speed measured when the maneuver '
            'starts, using only the ownship envelope (no heading or '
            'altitude change). 1.0 = no reduction. Default: 0.6.'))
        f2.addRow('Cross-track gain k_xt', _with_help(
            self.sb_kxt,
            'Cross-track line-attraction gain (1/m) of the route guidance '
            'law inside each shift candidate. It is the reciprocal of the '
            'guidance look-ahead distance (k_xt = 1/L), so larger = shorter '
            'look-ahead = sharper transition onto the line (higher peak turn '
            'rate, larger lateral acceleration demand). Default: 0.005 1/m '
            '(a 200 m look-ahead).'))
        f2.addRow('Engage hysteresis', _with_help(
            self.sb_engage_hysteresis,
            'Seconds the collision alert must persist continuously '
            'before an avoidance maneuver is committed (and before the '
            'encounter is classified). Any single conflict-free step '
            'resets the window, so transient spikes (e.g. an unconverged '
            'track on the frame it is re-initialised) never trigger a '
            'maneuver. 0 = act on the first alerting step. Default: 5 s.'))
        f2.addRow('Return hysteresis', _with_help(
            self.sb_return_hysteresis,
            'Seconds the return path must stay continuously clear before '
            'the return-to-route maneuver starts. Any single alerting '
            'step resets the window. 0 = return on the first clear step. '
            'Default: 2 s.'))
        # Closed-loop mode selector.  Picks the avoidance re-evaluation
        # policy (open loop / on new conflict / periodic); more modes can
        # be appended to _CLOSED_LOOP_META.  The two periodic tunables
        # below are only relevant in 'periodic' mode and are enabled /
        # disabled by ``_apply_closed_loop_enabled``.
        self.cb_closed_loop_mode = _NoWheelComboBox()
        _closed_loop_help = []
        for _cl_id, _cl_label, _cl_help in _CLOSED_LOOP_META:
            self.cb_closed_loop_mode.addItem(_cl_label, _cl_id)
            _closed_loop_help.append('• %s — %s' % (_cl_label, _cl_help))
        _cl_idx = self.cb_closed_loop_mode.findData(params.closed_loop_mode)
        self.cb_closed_loop_mode.setCurrentIndex(_cl_idx if _cl_idx >= 0
                                                 else 0)
        self.sb_periodic_interval = _dspin(params.periodic_interval_s,
                                           lo=0.05, hi=60.0,
                                           step=0.5, decimals=2, suffix='s')
        self.sb_switch_ratio = _dspin(params.switch_improve_ratio,
                                      lo=0.0, hi=10.0,
                                      step=0.05, decimals=2)
        f2.addRow('Closed-loop mode', _with_help(
            self.cb_closed_loop_mode,
            'Avoidance re-evaluation policy while flying a maneuver.\n\n'
            + '\n'.join(_closed_loop_help)))
        f2.addRow('Re-eval interval', _with_help(
            self.sb_periodic_interval,
            'Closed-loop "periodic" mode only: how often (seconds) the '
            'full escape set is re-evaluated while avoiding. Default: 1 s.'))
        f2.addRow('Anti-flicker ratio', _with_help(
            self.sb_switch_ratio,
            'Closed-loop "periodic" mode only: minimum fractional '
            'improvement in the predicted CPA cylinder distance a '
            're-ranked escape must show over the current maneuver before '
            'the ownship switches (stacks) to it. 0.15 = require a 15 % '
            'farther CPA. A switch also fires, regardless of this margin, '
            'when the current maneuver is predicted to enter conflict and '
            'the new escape is farther from the intruder. Default: 0.15.'))
        # Per-maneuver energy-cost ratios.  When a case permits more
        # than one escape, the avoidance FSM picks the compliant escape
        # with the best cylindrical-separation-per-energy score, so
        # lowering one value activates that branch.  Defaults encode the
        # rules-of-the-air bias (right cheapest, then left, then the
        # vertical escapes).  Custom-tab presets overwrite these to
        # demonstrate a specific branch.
        self._energy_spins: dict = {}
        _energy_help = (
            'Relative energy cost of each escape maneuver. The avoidance '
            'logic selects the compliant escape that maximises '
            'cylindrical separation per unit energy, so lowering one '
            'value activates that branch for a multi-escape case. '
            'Defaults: right < left < descend < climb (rules of the air).')
        for _name, _label in (('maintain',    'maintain'),
                              ('right_shift', 'right'),
                              ('left_shift',  'left'),
                              ('slow_down',   'slow down'),
                              ('descend',     'descend'),
                              ('climb',       'climb')):
            sb = _NoWheelDoubleSpinBox()
            sb.setRange(0.1, 100.0)
            sb.setDecimals(2)
            sb.setSingleStep(0.1)
            sb.setValue(float(DEFAULT_ENERGY_COST_RATIOS.get(_name, 1.0)))
            sb.setMinimumWidth(58)
            self._energy_spins[_name] = sb
            f2.addRow('Energy-cost · ' + _label,
                      _with_help(sb, _energy_help))
        outer.addWidget(gb_man)

        # ---- Flight envelope ----
        gb_env = QGroupBox('Flight envelope')
        f_env = QFormLayout(gb_env)
        self.sb_a_along = _dspin(params.a_max_along, lo=0.01, hi=50.0,
                                 step=0.01, decimals=2, suffix='m/s²')
        self.sb_rate_az = _dspin(params.rate_max_azimuth, lo=0.001, hi=10.0,
                                 step=0.01, decimals=3, suffix='rad/s')
        self.sb_rate_el = _dspin(params.rate_max_elevation, lo=0.001, hi=10.0,
                                 step=0.01, decimals=3, suffix='rad/s')
        self.sb_v_max  = _dspin(params.v_max, lo=1.0, hi=1.0E6,
                                step=1.0, decimals=2, suffix='m/s')
        self.sb_v_min  = _dspin(params.v_min, lo=0.0, hi=2000.0,
                                step=1.0, decimals=2, suffix='m/s')
        self.sb_el_min = _dspin(params.el_min, lo=-1.5708, hi=0.0,
                                step=0.01, decimals=3, suffix='rad')
        self.sb_el_max = _dspin(params.el_max, lo=0.0, hi=1.5708,
                                step=0.01, decimals=3, suffix='rad')
        self.sb_alt_max = _dspin(params.alt_max, lo=-1000.0, hi=1.0E6,
                                 step=50.0, decimals=1, suffix=' m')
        self.sb_alt_min = _dspin(params.alt_min, lo=-1000.0, hi=1.0E6,
                                 step=50.0, decimals=1, suffix=' m')
        f_env.addRow('Max accel along-track', _with_help(
            self.sb_a_along,
            'Maximum along-track (speed-module) acceleration (m/s²) '
            'applied by the DLL-backed Virtual_ownship integrator when '
            'sampling shift candidates. Default: 3.05 m/s².'))
        f_env.addRow('Max azimuth rate', _with_help(
            self.sb_rate_az,
            'Maximum course-angle (azimuth) rate (rad/s) applied by the '
            'integrator — caps how fast the horizontal heading can slew '
            'during the transition. Default: 0.15 rad/s.'))
        f_env.addRow('Max elevation rate', _with_help(
            self.sb_rate_el,
            'Maximum flight-path-angle (elevation) rate (rad/s) applied '
            'by the integrator — caps how fast the climb/descent angle '
            'can slew. Default: 0.08 rad/s.'))
        f_env.addRow('Max speed', _with_help(
            self.sb_v_max,
            'Upper bound on the speed module |v| (m/s). '
            'Always-on: set to a large value for an effectively '
            'unlimited cap.'))
        f_env.addRow('Min speed (0=off)', _with_help(
            self.sb_v_min,
            'Lower bound on the speed module |v| (m/s, stall guard).  '
            'Set to 0 to disable.  Keeps the airframe from '
            'decelerating through zero speed (where the course '
            'azimuth becomes undefined).'))
        f_env.addRow('Min flight-path angle (descent)', _with_help(
            self.sb_el_min,
            'Lower bound on the flight-path angle (rad, negative = '
            'descent): the steepest descent the airframe may reach. '
            'Use -pi/2 for effectively unlimited.'))
        f_env.addRow('Max flight-path angle (climb)', _with_help(
            self.sb_el_max,
            'Upper bound on the flight-path angle (rad, positive = '
            'climb): the steepest climb the airframe may reach. '
            'Use +pi/2 for effectively unlimited.'))
        f_env.addRow('Max altitude', _with_help(
            self.sb_alt_max,
            'Flight-envelope ceiling (m AGL, positive-up).  The '
            'classifier bars a climb escape (near-ceiling, Case 14) '
            'when a climb of the vertical-shift margin would reach or '
            'exceed this altitude.  Set very high to disable.'))
        f_env.addRow('Min altitude', _with_help(
            self.sb_alt_min,
            'Flight-envelope floor (m AGL, positive-up).  The '
            'classifier bars a descent escape (near-floor, Case 15) '
            'when a descent of the vertical-shift margin would reach '
            'or drop below this altitude.  Set very low to disable.'))
        outer.addWidget(gb_env)

        # ---- Camera (field of view) ----
        gb_cam = QGroupBox('Camera')
        f_cam = QFormLayout(gb_cam)
        self.sb_fov_az_min = _dspin(params.fov_az_min, lo=-180.0, hi=0.0,
                                    step=5.0, decimals=1, suffix='°')
        self.sb_fov_az_max = _dspin(params.fov_az_max, lo=0.0, hi=180.0,
                                    step=5.0, decimals=1, suffix='°')
        self.sb_fov_el_min = _dspin(params.fov_el_min, lo=-90.0, hi=0.0,
                                    step=5.0, decimals=1, suffix='°')
        self.sb_fov_el_max = _dspin(params.fov_el_max, lo=0.0, hi=90.0,
                                    step=5.0, decimals=1, suffix='°')
        f_cam.addRow('FOV azimuth min', _with_help(
            self.sb_fov_az_min,
            'Left edge of the camera field of view (deg, body frame). '
            'The ownship can only see — and therefore track — the '
            'intruder while its azimuth is ≥ this value.  Default: '
            '−60°.'))
        f_cam.addRow('FOV azimuth max', _with_help(
            self.sb_fov_az_max,
            'Right edge of the camera field of view (deg, body frame). '
            'Default: +60°.'))
        f_cam.addRow('FOV elevation min', _with_help(
            self.sb_fov_el_min,
            'Lower edge of the camera field of view (deg, body frame). '
            'Default: −15°.'))
        f_cam.addRow('FOV elevation max', _with_help(
            self.sb_fov_el_max,
            'Upper edge of the camera field of view (deg, body frame). '
            'Default: +15°.'))
        outer.addWidget(gb_cam)

        # ---- Estimator (UKF) ----
        gb_est = QGroupBox('Intruder estimator (UKF)')
        f_est = QFormLayout(gb_est)
        # Motion-model selector — the first estimator parameter.  The
        # display label carries the short code ('cv'/'ca'/'cab') as user
        # data so _sync can forward it straight to the simulator.
        self.cb_ukf_model = _NoWheelComboBox()
        self.cb_ukf_model.addItem('Constant velocity (CV)', 'cv')
        self.cb_ukf_model.addItem('Constant acceleration, NED (CA)', 'ca')
        self.cb_ukf_model.addItem('Constant acceleration, body (CAB)', 'cab')
        self.cb_ukf_model.addItem('Constant turn-rate + accel (CTRA)', 'ctra')
        _ukf_idx = self.cb_ukf_model.findData(params.ukf_model)
        self.cb_ukf_model.setCurrentIndex(_ukf_idx if _ukf_idx >= 0 else 0)
        f_est.addRow('Motion model', _with_help(
            self.cb_ukf_model,
            'Kinematic model the Unscented Kalman Filter uses to track '
            'and predict the intruder. CV assumes constant velocity '
            '(6-state); CA adds a constant-acceleration term in the NED '
            'frame (9-state); CAB models acceleration in the intruder '
            'body frame (tangential / normal / vertical, 9-state). CA / '
            'CAB react faster to manoeuvring intruders at the cost of '
            'noisier estimates. NOTE the process-noise σ below changes '
            'meaning and units with the model (acceleration m/s² for CV, '
            'jerk m/s³ for CA / CAB). Default: CV.'))
        # Process-noise spinner.  Its quantity, units, default and help
        # all depend on the selected motion model, so the row keeps an
        # explicit label and a callable help text that _on_ukf_model_changed
        # refreshes live.  Seeded from the current model's metadata.
        _q_meta = _UKF_MODEL_META.get(params.ukf_model,
                                      _UKF_MODEL_META['cv'])
        self.sb_q     = _dspin(params.process_noise_std, lo=0.001,
                               hi=_q_meta['q_max'], step=_q_meta['q_step'],
                               decimals=3, suffix=_q_meta['q_unit'])
        self.lbl_q    = QLabel(_q_meta['q_label'])
        # CTRA-only turn-rate process-noise σ (angular accel, rad/s²).
        # Enabled only when the CTRA model is active (see
        # _on_ukf_model_changed); other models have no turn-rate state.
        self.sb_q_omega = _dspin(params.process_noise_omega,
                                 lo=_Q_OMEGA_CTRA['lo'], hi=_Q_OMEGA_CTRA['hi'],
                                 step=_Q_OMEGA_CTRA['step'],
                                 decimals=_Q_OMEGA_CTRA['decimals'],
                                 suffix=_Q_OMEGA_CTRA['suffix'])
        self.sb_q_omega.setToolTip(_Q_OMEGA_CTRA['help'])
        self.lbl_q_omega = QLabel(_Q_OMEGA_CTRA['label'])
        # Angle sigmas are stored internally in radians but shown to the
        # user in degrees (converted on read/write in _sync / _reset).
        self.sb_s_az  = _dspin(np.degrees(params.sigma_az), lo=1e-3, hi=60.0,
                               step=0.1, decimals=3, suffix='°')
        self.sb_s_el  = _dspin(np.degrees(params.sigma_el), lo=1e-3, hi=60.0,
                               step=0.1, decimals=3, suffix='°')
        self.sb_s_rng = _dspin(params.range_noise_pct, lo=0.1,  hi=100.0,
                               step=1.0,  decimals=2, suffix='%')
        self.sb_timeout = _dspin(params.track_timeout, lo=0.0, hi=600.0,
                                 step=0.5, decimals=2, suffix='s')
        # First-sighting bootstrap seed (velocity / acceleration 1-σ) and
        # the warm-up window before the track is allowed to drive scoring.
        self.sb_init_vel = _dspin(params.init_velocity_std, lo=0.0,
                                  hi=10000.0, step=10.0, decimals=1,
                                  suffix='m/s')
        # Finite-difference horizontal velocity seed toggle.  When checked
        # the bootstrap computes P0v per sighting from the measurement
        # geometry (see _apply_fd_init_vel_enabled), so the manual
        # ``Init velocity σ`` spinner above is greyed out and ignored.
        self.cb_fd_init_vel = QCheckBox()
        self.cb_fd_init_vel.setChecked(params.fd_init_vel)
        self.sb_init_acc = _dspin(params.init_accel_std, lo=0.0, hi=500.0,
                                  step=0.5, decimals=2, suffix='m/s²')
        self.sb_init_vel_vert = _dspin(params.init_velocity_std_vertical,
                                       lo=0.0, hi=10000.0, step=10.0,
                                       decimals=1, suffix='m/s')
        self.sb_init_acc_vert = _dspin(params.init_accel_std_vertical,
                                       lo=0.0, hi=500.0, step=0.5,
                                       decimals=2, suffix='m/s²')
        self.sb_init_window = _NoWheelSpinBox()
        self.sb_init_window.setRange(1, 100)
        self.sb_init_window.setValue(int(params.init_window))
        self.sb_init_window.setSuffix(' frames')
        self.sb_init_window.setMinimumWidth(140)
        self.sb_q.setToolTip(_q_meta['q_help'])
        f_est.addRow(self.lbl_q, _with_help(
            self.sb_q,
            lambda: _UKF_MODEL_META.get(
                self.cb_ukf_model.currentData(),
                _UKF_MODEL_META['cv'])['q_help']))
        f_est.addRow(self.lbl_q_omega, _with_help(
            self.sb_q_omega, _Q_OMEGA_CTRA['help']))
        f_est.addRow('Sensor σ azimuth',   _with_help(
            self.sb_s_az,
            'Standard deviation of the sensor azimuth measurement '
            '(degrees, 1-σ; stored internally in radians). Sets the '
            'R-matrix entry the UKF uses to weigh azimuth updates. '
            'Default: 2°.'))
        f_est.addRow('Sensor σ elevation', _with_help(
            self.sb_s_el,
            'Standard deviation of the sensor elevation measurement '
            '(degrees, 1-σ; stored internally in radians). '
            'Default: 2°.'))
        f_est.addRow('Sensor σ range',     _with_help(
            self.sb_s_rng,
            'Sensor range measurement 1-σ noise, as a percentage of the '
            'measured distance (the range error grows with range). '
            'Applied per frame as this fraction of the current range. '
            'Default: 15%.'))
        f_est.addRow('Track-reset timeout', _with_help(
            self.sb_timeout,
            'How long the intruder may stay outside the camera field '
            'of view before its estimate is dropped (seconds).  While '
            'out of view the filter coasts on the constant-velocity '
            'model; past this timeout the track is reset, so a later '
            'sighting re-initialises the estimate from scratch.  '
            'Default: 5 s.'))
        self.lbl_init_vel = QLabel('Init velocity σ')
        f_est.addRow(self.lbl_init_vel, _with_help(
            self.sb_init_vel,
            'First-sighting bootstrap: the intruder velocity is seeded '
            'at zero and this 1-σ value (m/s) sizes its initial '
            'uncertainty. It bounds the plausible intruder speed so the '
            'in-FOV measurement stream can pull the velocity in without '
            'a tightly-trusted finite-difference seed. Default: 300 m/s.'))
        f_est.addRow('Finite-difference init σ_v', _with_help(
            self.cb_fd_init_vel,
            'When enabled the horizontal init velocity σ is computed per '
            'first sighting as the two-point finite-difference velocity '
            'variance — the velocity uncertainty a one-frame position '
            'difference actually carries (2·σ_pos²/dt², with σ_pos the '
            'transverse range × angular σ). This is the statistically '
            'consistent track-initiation seed, so the zero-velocity seed '
            'relaxes to the true speed without the warm-up overshoot a '
            'tighter manual seed forces. The manual "Init velocity σ" above '
            'is greyed out and ignored. Note: in this angle-only geometry it '
            'can be large (a single short baseline carries little velocity '
            'information). Vertical seeds are unaffected. Default: off.'))
        # Label kept as a reference so the row can be greyed out for the
        # CV model, which has no acceleration state (see
        # _apply_init_acc_enabled).
        self.lbl_init_acc = QLabel('Init acceleration σ')
        f_est.addRow(self.lbl_init_acc, _with_help(
            self.sb_init_acc,
            'First-sighting bootstrap: the intruder acceleration is '
            'seeded at zero and this 1-σ value (m/s²) sizes its initial '
            'uncertainty. Used only by the CA / CAB / CTRA motion models. '
            'This is the INITIAL covariance only — at first sighting the '
            'prior is straight-and-level flight, so a small seed encodes '
            'that prior; the process-noise σ still lets the filter grow '
            'the acceleration estimate for a genuine manoeuvre, so a tight '
            'seed does not make the tracker sluggish. A wide seed instead '
            'integrates twice into position and fans the predicted '
            'envelope out over the lookahead. Default: 1.5 m/s² '
            '(≈0.05 g cruise jitter).'))
        f_est.addRow('Init velocity σ (vertical)', _with_help(
            self.sb_init_vel_vert,
            'First-sighting bootstrap: separate 1-σ (m/s) for the '
            'vertical (down) velocity. Aircraft fly largely level, so '
            'this is normally tighter than the horizontal seed, which '
            'keeps the predicted altitude envelope from fanning out over '
            'the lookahead and tripping the cylinder on dispersion '
            'alone. Size it to the max climb/descent you must track '
            '(≈30 m/s). Default: 100 m/s.'))
        # Label and help are reconfigured per motion model: the CTRA model
        # repurposes this spinner as the initial turn-rate σ (see
        # _apply_init_acc_vert_profile / _INIT_ACC_VERT_PROFILE).
        self.lbl_init_acc_vert = QLabel(_INIT_ACC_VERT_PROFILE['accel']['label'])
        f_est.addRow(self.lbl_init_acc_vert, _with_help(
            self.sb_init_acc_vert,
            lambda: _INIT_ACC_VERT_PROFILE[
                'turn_rate' if self.cb_ukf_model.currentData() == 'ctra'
                else 'accel']['help']))
        f_est.addRow('Init warm-up window', _with_help(
            self.sb_init_window,
            'Number of consecutive in-FOV frames the freshly bootstrapped '
            'track must ingest before it is allowed to drive propagation, '
            'scoring and alerts. Suppresses false alerts while the wide '
            'bootstrap covariance settles. Default: 3 frames.'))
        outer.addWidget(gb_est)

        # ---- Visualiser ----
        gb_vis = QGroupBox('Visualiser')
        f3 = QFormLayout(gb_vis)
        self.sb_nsig = _dspin(params.n_sigma, lo=0.5, hi=5.0,
                              step=0.1, decimals=1)
        f3.addRow('Covariance n-σ', _with_help(
            self.sb_nsig,
            'Sigma scale used by the 3-D visualiser to draw the intruder '
            'uncertainty volumes (the cyan ellipsoid at t+0 and the '
            'prediction cylinders at t+15/30/45/60 s). 1.0 ≈ 68 % mass, '
            '2.0 ≈ 95 %, 3.0 ≈ 99.7 %. Default: 1.0 to match the alert '
            'threshold\'s 1-σ reference. Does not affect the simulation '
            'logic.'))
        outer.addWidget(gb_vis)

        # ---- Reset ----
        # No "Apply": every spinner writes through to the shared
        # ParamSet live (see _sync), so the next run picks up the
        # current values immediately.
        row = QHBoxLayout()
        self.btn_reset = QPushButton('Reset to defaults')
        row.addWidget(self.btn_reset)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

        self.btn_reset.clicked.connect(self._reset)

        # Wire every spinner to the live sync.
        self._all_spins = [
            self.sb_lookahead, self.sb_dt, self.sb_cyl_d, self.sb_cyl_h,
            self.sb_alert, self.sb_engage_hysteresis, self.sb_return_hysteresis,
            self.sb_periodic_interval, self.sb_switch_ratio,
            self.sb_lat, self.sb_vert, self.sb_slow,
            self.sb_kxt,
            self.sb_a_along, self.sb_rate_az, self.sb_rate_el,
            self.sb_v_max, self.sb_v_min, self.sb_el_min,
            self.sb_el_max,
            self.sb_alt_max, self.sb_alt_min,
            self.sb_fov_az_min, self.sb_fov_az_max,
            self.sb_fov_el_min, self.sb_fov_el_max,
            self.sb_q, self.sb_q_omega, self.sb_s_az, self.sb_s_el,
            self.sb_s_rng, self.sb_timeout,
            self.sb_init_vel, self.sb_init_acc, self.sb_init_window,
            self.sb_init_vel_vert, self.sb_init_acc_vert,
            self.sb_nsig,
            *self._energy_spins.values(),
        ]
        for _sb in self._all_spins:
            _sb.valueChanged.connect(self._sync)
        self.cb_closed_loop_mode.currentIndexChanged.connect(
            self._apply_closed_loop_enabled)
        self.cb_closed_loop_mode.currentIndexChanged.connect(self._sync)
        self.cb_fd_init_vel.toggled.connect(self._apply_fd_init_vel_enabled)
        self.cb_fd_init_vel.toggled.connect(self._sync)
        self.cb_ukf_model.currentIndexChanged.connect(self._on_ukf_model_changed)
        self.cb_maneuver_family.currentIndexChanged.connect(self._sync)

        # Reconfigure the repurposed "Init acceleration σ (vertical)"
        # spinner for the model selected at start-up.  Pre-seed the kind so
        # an accel model keeps the loaded ParamSet value, while a CTRA start
        # snaps it to the turn-rate default (the stored m/s² seed is
        # meaningless as a turn rate).
        self._init_acc_vert_kind = (
            None if self.cb_ukf_model.currentData() == 'ctra' else 'accel')
        self._apply_init_acc_vert_profile()
        self._apply_q_omega_enabled()
        self._apply_init_acc_enabled()
        self._apply_fd_init_vel_enabled()
        self._apply_closed_loop_enabled()
        self._sync()   # seed params from the initial widget state

    @Slot()
    def _on_ukf_model_changed(self):
        """Refresh the process-noise row when the motion model changes.

        The process-noise σ changes both meaning and units between
        models (acceleration m/s² for CV, jerk m/s³ for CA/CAB), so the
        row label, units suffix and tool-tip are updated and the value is
        snapped to the new model's sensible default (a fixed numeric σ
        would mean wildly different physical noise across models)."""
        meta = _UKF_MODEL_META.get(self.cb_ukf_model.currentData(),
                                   _UKF_MODEL_META['cv'])
        self.lbl_q.setText(meta['q_label'])
        # Update value + suffix without retriggering _sync mid-update;
        # the trailing _sync() pushes the final state in one go.
        self.sb_q.blockSignals(True)
        # Widen the range before snapping the value so a smaller new max
        # never clips the default, then tighten it to the model's cap.
        self.sb_q.setRange(0.001, max(meta['q_max'], self.sb_q.value()))
        self.sb_q.setSingleStep(meta['q_step'])
        self.sb_q.setSuffix(' ' + meta['q_unit'])
        self.sb_q.setValue(meta['q_default'])
        self.sb_q.setRange(0.001, meta['q_max'])
        self.sb_q.setToolTip(meta['q_help'])
        self.sb_q.blockSignals(False)
        self._apply_init_acc_vert_profile()
        self._apply_q_omega_enabled()
        self._apply_init_acc_enabled()
        self._sync()

    def _apply_init_acc_enabled(self):
        """Grey out the init-acceleration σ rows for the CV model.

        CV is a constant-velocity (6-state) model with no acceleration
        state, so its first-sighting acceleration seeds are unused; the
        two "Init acceleration σ" rows are disabled (but kept visible so
        the layout is stable) when CV is active.  CA / CAB carry NED /
        body acceleration and CTRA carries a tangential acceleration, so
        all three keep the rows enabled.  (The vertical row is repurposed
        as the turn-rate seed for CTRA, which is also a used state.)"""
        has_accel = (self.cb_ukf_model.currentData() != 'cv')
        self.sb_init_acc.setEnabled(has_accel)
        self.lbl_init_acc.setEnabled(has_accel)
        self.sb_init_acc_vert.setEnabled(has_accel)
        self.lbl_init_acc_vert.setEnabled(has_accel)

    def _apply_fd_init_vel_enabled(self):
        """Grey out the manual init-velocity σ when the finite-difference
        seed is enabled.

        With the option on, the bootstrap derives P0v per sighting from the
        measurement geometry, so the manual spinner is unused; it is
        disabled (but kept visible so the layout is stable)."""
        fd = self.cb_fd_init_vel.isChecked()
        self.sb_init_vel.setEnabled(not fd)
        self.lbl_init_vel.setEnabled(not fd)

    def _apply_closed_loop_enabled(self):
        """Grey out the periodic-mode tunables unless 'periodic' is active.

        The re-eval interval and anti-flicker ratio only affect the
        ``CLOSED_LOOP_PERIODIC`` mode, so they are disabled (but kept
        visible so the layout is stable) for the open and on-conflict
        modes."""
        is_periodic = (self.cb_closed_loop_mode.currentData()
                       == CLOSED_LOOP_PERIODIC)
        self.sb_periodic_interval.setEnabled(is_periodic)
        self.sb_switch_ratio.setEnabled(is_periodic)

    def _apply_q_omega_enabled(self):
        """Enable the turn-rate process-noise spinner only for CTRA.

        The CV / CA / CAB models have no turn-rate state, so the angular-
        acceleration noise is meaningless for them; the row is greyed out
        (but kept visible so the layout is stable) when they are active."""
        is_ctra = (self.cb_ukf_model.currentData() == 'ctra')
        self.sb_q_omega.setEnabled(is_ctra)
        self.lbl_q_omega.setEnabled(is_ctra)

    def _apply_init_acc_vert_profile(self):
        """Reconfigure the "Init acceleration σ (vertical)" spinner.

        The CTRA model has no vertical-acceleration state and instead
        carries the horizontal turn rate, so this spinner is repurposed as
        the initial turn-rate σ for that model.  The quantity, units and
        sensible range differ from the CA / CAB vertical-acceleration seed,
        so the label, suffix, range and tool-tip are swapped here.  The
        value is snapped to the new profile's default only when crossing
        between the two interpretations (mirroring how the process-noise
        spinner snaps on a model change), so switching among the
        acceleration models never disturbs a user-entered seed."""
        kind = ('turn_rate'
                if self.cb_ukf_model.currentData() == 'ctra' else 'accel')
        prof = _INIT_ACC_VERT_PROFILE[kind]
        sb = self.sb_init_acc_vert
        sb.blockSignals(True)
        # Widen the range before snapping so a smaller new cap never clips
        # the default, then tighten it to the profile's bounds.
        sb.setRange(prof['lo'], max(prof['hi'], sb.value()))
        sb.setDecimals(prof['decimals'])
        sb.setSingleStep(prof['step'])
        sb.setSuffix(prof['suffix'])
        if kind != self._init_acc_vert_kind:
            sb.setValue(prof['default'])
            self._init_acc_vert_kind = kind
        sb.setRange(prof['lo'], prof['hi'])
        sb.setToolTip(prof['help'])
        sb.blockSignals(False)
        self.lbl_init_acc_vert.setText(prof['label'])


    @Slot()
    def _sync(self):
        """Write the current widget state through to the shared
        ParamSet.  Invoked on every spinner change (live apply)."""
        p = self.params
        p.lookahead       = self.sb_lookahead.value()
        p.dt              = self.sb_dt.value()
        p.cyl_d           = self.sb_cyl_d.value()
        p.cyl_h           = self.sb_cyl_h.value()
        p.alert_threshold = self.sb_alert.value()
        p.engage_hysteresis_s = self.sb_engage_hysteresis.value()
        p.return_hysteresis_s = self.sb_return_hysteresis.value()
        p.closed_loop_mode = self.cb_closed_loop_mode.currentData()
        p.periodic_interval_s  = self.sb_periodic_interval.value()
        p.switch_improve_ratio = self.sb_switch_ratio.value()
        p.lateral_shift_ratio  = self.sb_lat.value() / 100.0
        p.vertical_shift_ratio = self.sb_vert.value() / 100.0
        p.slowdown_ratio  = self.sb_slow.value()
        p.maneuver_family = self.cb_maneuver_family.currentData()
        p.k_xt            = self.sb_kxt.value()
        p.a_max_along     = self.sb_a_along.value()
        p.rate_max_azimuth   = self.sb_rate_az.value()
        p.rate_max_elevation = self.sb_rate_el.value()
        p.v_max  = self.sb_v_max.value()
        p.v_min  = self.sb_v_min.value()
        p.el_min = self.sb_el_min.value()
        p.el_max = self.sb_el_max.value()
        p.alt_max         = self.sb_alt_max.value()
        p.alt_min         = self.sb_alt_min.value()
        p.fov_az_min      = self.sb_fov_az_min.value()
        p.fov_az_max      = self.sb_fov_az_max.value()
        p.fov_el_min      = self.sb_fov_el_min.value()
        p.fov_el_max      = self.sb_fov_el_max.value()
        p.process_noise_std = self.sb_q.value()
        p.process_noise_omega = self.sb_q_omega.value()
        p.ukf_model         = self.cb_ukf_model.currentData()
        # Angle sigmas are entered in degrees; store them in radians.
        p.sigma_az          = float(np.radians(self.sb_s_az.value()))
        p.sigma_el          = float(np.radians(self.sb_s_el.value()))
        p.range_noise_pct   = self.sb_s_rng.value()
        p.track_timeout     = self.sb_timeout.value()
        p.init_velocity_std = self.sb_init_vel.value()
        p.fd_init_vel = self.cb_fd_init_vel.isChecked()
        p.init_accel_std    = self.sb_init_acc.value()
        p.init_velocity_std_vertical = self.sb_init_vel_vert.value()
        p.init_accel_std_vertical    = self.sb_init_acc_vert.value()
        p.init_window       = int(self.sb_init_window.value())
        p.n_sigma           = self.sb_nsig.value()
        p.energy_cost_ratios = {name: float(sb.value())
                                for name, sb in self._energy_spins.items()}

    @Slot()
    def _reset(self):
        d = ParamSet()
        self.sb_lookahead.setValue(d.lookahead)
        self.sb_dt.setValue(d.dt)
        self.sb_cyl_d.setValue(d.cyl_d)
        self.sb_cyl_h.setValue(d.cyl_h)
        self.sb_alert.setValue(d.alert_threshold)
        self.sb_engage_hysteresis.setValue(d.engage_hysteresis_s)
        self.sb_return_hysteresis.setValue(d.return_hysteresis_s)
        _cl_idx = self.cb_closed_loop_mode.findData(d.closed_loop_mode)
        self.cb_closed_loop_mode.setCurrentIndex(_cl_idx if _cl_idx >= 0
                                                 else 0)
        self.sb_periodic_interval.setValue(d.periodic_interval_s)
        self.sb_switch_ratio.setValue(d.switch_improve_ratio)
        self.sb_lat.setValue(d.lateral_shift_ratio * 100.0)
        self.sb_vert.setValue(d.vertical_shift_ratio * 100.0)
        self.sb_slow.setValue(d.slowdown_ratio)
        _man_idx = self.cb_maneuver_family.findData(d.maneuver_family)
        self.cb_maneuver_family.setCurrentIndex(_man_idx if _man_idx >= 0
                                                else 0)
        self.sb_kxt.setValue(d.k_xt)
        self.sb_a_along.setValue(d.a_max_along)
        self.sb_rate_az.setValue(d.rate_max_azimuth)
        self.sb_rate_el.setValue(d.rate_max_elevation)
        self.sb_v_max.setValue(d.v_max)
        self.sb_v_min.setValue(d.v_min)
        self.sb_el_min.setValue(d.el_min)
        self.sb_el_max.setValue(d.el_max)
        self.sb_alt_max.setValue(d.alt_max)
        self.sb_alt_min.setValue(d.alt_min)
        self.sb_fov_az_min.setValue(d.fov_az_min)
        self.sb_fov_az_max.setValue(d.fov_az_max)
        self.sb_fov_el_min.setValue(d.fov_el_min)
        self.sb_fov_el_max.setValue(d.fov_el_max)
        self.sb_q.setValue(d.process_noise_std)
        self.sb_q_omega.setValue(d.process_noise_omega)
        _ukf_idx = self.cb_ukf_model.findData(d.ukf_model)
        self.cb_ukf_model.setCurrentIndex(_ukf_idx if _ukf_idx >= 0 else 0)
        self.sb_s_az.setValue(np.degrees(d.sigma_az))
        self.sb_s_el.setValue(np.degrees(d.sigma_el))
        self.sb_s_rng.setValue(d.range_noise_pct)
        self.sb_timeout.setValue(d.track_timeout)
        self.sb_init_vel.setValue(d.init_velocity_std)
        self.cb_fd_init_vel.setChecked(d.fd_init_vel)
        self.sb_init_acc.setValue(d.init_accel_std)
        self.sb_init_vel_vert.setValue(d.init_velocity_std_vertical)
        self.sb_init_acc_vert.setValue(d.init_accel_std_vertical)
        self.sb_init_window.setValue(int(d.init_window))
        self.sb_nsig.setValue(d.n_sigma)
        for name, sb in self._energy_spins.items():
            sb.setValue(float(d.energy_cost_ratios.get(name, 1.0)))
        self._apply_fd_init_vel_enabled()
        self._apply_closed_loop_enabled()
        self._sync()


# ---------------------------------------------------------------------------
# Single-seed tab
# ---------------------------------------------------------------------------
class SingleSeedTab(QWidget):
    def __init__(self, params: ParamSet, parent=None):
        super().__init__(parent)
        self.params = params
        self.worker: SingleSimWorker | None = None
        self.last_result = None
        self.last_seed = None
        self._anims: list = []           # keep refs to live FuncAnimations

        outer = QVBoxLayout(self)

        # Top row: seed input + run buttons
        row = QHBoxLayout()
        row.addWidget(QLabel('Seed:'))
        self.sb_seed = _NoWheelSpinBox()
        self.sb_seed.setRange(0, 2_147_483_647)
        self.sb_seed.setValue(42)
        self.sb_seed.setMinimumWidth(140)
        row.addWidget(self.sb_seed)
        self.btn_random = QPushButton('Random seed')
        row.addWidget(self.btn_random)
        row.addStretch(1)
        self.btn_run = QPushButton('Run simulation')
        self.btn_view = QPushButton('Visualize 3-D')
        self.btn_view.setEnabled(False)
        row.addWidget(self.btn_run)
        row.addWidget(self.btn_view)
        outer.addLayout(row)

        # Result summary panel
        gb = QGroupBox('Result summary')
        v = QVBoxLayout(gb)
        self.txt = QTextEdit(); self.txt.setReadOnly(True)
        f = QFont('Consolas'); f.setStyleHint(QFont.Monospace)
        self.txt.setFont(f)
        v.addWidget(self.txt)
        outer.addWidget(gb, 1)

        self.btn_run.clicked.connect(self._on_run)
        self.btn_view.clicked.connect(self._on_view)
        self.btn_random.clicked.connect(self._on_random)

    @Slot()
    def _on_random(self):
        self.sb_seed.setValue(random.randint(0, 1_000_000))

    @Slot()
    def _on_run(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self.btn_run.setEnabled(False)
        self.btn_view.setEnabled(False)
        self.last_result = None
        seed = self.sb_seed.value()
        self.txt.setPlainText(f'Running seed {seed} ...')
        self.worker = SingleSimWorker(seed, self.params, self)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_fail)
        self.worker.start()

    @Slot(object, int)
    def _on_done(self, result, seed):
        self.btn_run.setEnabled(True)
        self.btn_view.setEnabled(True)
        self.last_result = result
        self.last_seed = seed
        self.txt.setPlainText(self._format_summary(result, seed))

    @Slot(str)
    def _on_fail(self, msg):
        self.btn_run.setEnabled(True)
        self.btn_view.setEnabled(False)
        self.txt.setPlainText(f'ERROR: {msg}')

    def _format_summary(self, r, seed) -> str:
        return _format_result_summary(r, seed=seed)

    @Slot()
    def _on_view(self):
        if self.last_result is None:
            return
        # Import lazily — pulls in matplotlib + axes3d which are heavy.
        from daa_conflict_resolution.visualize_avoidance import animate
        try:
            anim = animate(self.last_result, n_sigma=self.params.n_sigma,
                           stride=10, seed=self.last_seed)
            # Hold a strong reference so the FuncAnimation isn't GC'd
            # the moment this slot returns.
            if anim is not None:
                self._anims.append(anim)
        except Exception as exc:                                  # noqa: BLE001
            QMessageBox.critical(self, 'Visualiser error',
                                 f'{type(exc).__name__}: {exc}')


# ---------------------------------------------------------------------------
# Monte Carlo tab
# ---------------------------------------------------------------------------
class _NumericTableItem(QTableWidgetItem):
    """Table item that sorts numerically when the cell holds a number,
    falling back to case-insensitive text comparison otherwise."""

    def __lt__(self, other: QTableWidgetItem) -> bool:
        a, b = self.text(), other.text()
        try:
            return float(a) < float(b)
        except (TypeError, ValueError):
            return a.lower() < b.lower()


def _mc_item(value) -> QTableWidgetItem:
    """Build a non-editable, numeric-aware table item from ``value``."""
    item = _NumericTableItem(str(value))
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item


class MonteCarloTab(QWidget):
    def __init__(self, params: ParamSet, parent=None):
        super().__init__(parent)
        self.params = params
        self.worker: BatchWorker | None = None
        self.rows: list[dict] = []
        self.t0 = 0.0

        outer = QVBoxLayout(self)

        # ---- Top: seed selection ----
        gb_in = QGroupBox('Batch input')
        f = QFormLayout(gb_in)
        self.cb_mode = _NoWheelComboBox()
        self.cb_mode.addItems(['Range (start + N)', 'Random'])
        f.addRow('Seed mode', self.cb_mode)

        self.sb_n = _NoWheelSpinBox(); self.sb_n.setRange(1, 100_000); self.sb_n.setValue(100)
        f.addRow('Number of seeds', self.sb_n)

        self.sb_start = _NoWheelSpinBox(); self.sb_start.setRange(0, 2_147_483_647); self.sb_start.setValue(0)
        f.addRow('First seed (range mode)', self.sb_start)

        self.sb_step = _NoWheelSpinBox(); self.sb_step.setRange(1, 1_000_000); self.sb_step.setValue(1)
        f.addRow('Step (range mode)', self.sb_step)

        self.sb_rand_seed = _NoWheelSpinBox(); self.sb_rand_seed.setRange(0, 2_147_483_647); self.sb_rand_seed.setValue(0)
        f.addRow('RNG seed (random mode)', self.sb_rand_seed)

        try:
            cpu = os.cpu_count() or 1
        except Exception:                                         # noqa: BLE001
            cpu = 1
        self.sb_workers = _NoWheelSpinBox(); self.sb_workers.setRange(1, max(1, cpu))
        self.sb_workers.setValue(max(1, cpu // 2))
        f.addRow(f'Workers (1..{cpu})', self.sb_workers)

        outer.addWidget(gb_in)

        # ---- Controls ----
        row = QHBoxLayout()
        self.btn_run = QPushButton('Run batch')
        self.btn_stop = QPushButton('Stop'); self.btn_stop.setEnabled(False)
        self.btn_save = QPushButton('Save CSV…'); self.btn_save.setEnabled(False)
        row.addWidget(self.btn_run); row.addWidget(self.btn_stop)
        row.addStretch(1); row.addWidget(self.btn_save)
        outer.addLayout(row)

        # ---- Progress + summary ----
        self.bar = QProgressBar(); self.bar.setRange(0, 100)
        outer.addWidget(self.bar)
        self.lbl_summary = QLabel('No batch run yet.')
        f2 = QFont('Consolas'); f2.setStyleHint(QFont.Monospace)
        self.lbl_summary.setFont(f2)
        outer.addWidget(self.lbl_summary)

        # ---- Results table ----
        self.table = QTableWidget(0, len(CSV_FIELDS))
        self.table.setHorizontalHeaderLabels(CSV_FIELDS)
        self.table.horizontalHeader().setStretchLastSection(True)
        # Column sorting is enabled only once a batch finishes (see
        # ``_on_done``); during a run rows stay in arrival order.
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        outer.addWidget(self.table, 1)

        self.btn_run.clicked.connect(self._on_run)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_save.clicked.connect(self._on_save)

    def _build_seeds(self) -> list[int]:
        n = self.sb_n.value()
        if self.cb_mode.currentIndex() == 0:
            start = self.sb_start.value()
            step = self.sb_step.value()
            return [start + k * step for k in range(n)]
        rng = random.Random(self.sb_rand_seed.value())
        return [rng.randint(0, 2_000_000_000) for _ in range(n)]

    @Slot()
    def _on_run(self):
        if self.worker is not None and self.worker.isRunning():
            return
        seeds = self._build_seeds()
        self.rows = []
        # Disable sorting while the batch runs; re-enabled in ``_on_done``.
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.bar.setRange(0, len(seeds))
        self.bar.setValue(0)
        self.lbl_summary.setText('Running...')
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_save.setEnabled(False)
        self.t0 = time.perf_counter()
        self.worker = BatchWorker(seeds, self.params,
                                  self.sb_workers.value(), self)
        self.worker.row_done.connect(self._on_row)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_fail)
        self.worker.start()

    @Slot()
    def _on_stop(self):
        if self.worker is not None:
            self.worker.stop()
            self.lbl_summary.setText('Stopping...')

    @Slot(int, int, dict)
    def _on_row(self, done, total, row):
        self.rows.append(row)
        self.bar.setValue(done)
        # Sorting is disabled during the run, so rows simply append in
        # arrival order.
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, key in enumerate(CSV_FIELDS):
            self.table.setItem(r, c, _mc_item(row.get(key, '')))
        if done % max(1, total // 50) == 0 or done == total:
            self.lbl_summary.setText(self._summary(partial=True))

    @Slot(list)
    def _on_done(self, rows):
        self.rows = sorted(rows, key=lambda r: int(r['seed']))
        # Repopulate in seed order, then enable interactive column sorting
        # now that the batch has finished.
        self.table.setRowCount(0)
        for row in self.rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, key in enumerate(CSV_FIELDS):
                self.table.setItem(r, c, _mc_item(row.get(key, '')))
        # Default to ascending order by the ``seed`` column (index 0).
        # Set the indicator first, then enable sorting so the table is
        # sorted exactly once (enabling sorting sorts by the current
        # indicator).
        self.table.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)
        self.table.setSortingEnabled(True)
        self.lbl_summary.setText(self._summary(partial=False))
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_save.setEnabled(bool(self.rows))

    @Slot(str)
    def _on_fail(self, msg):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_summary.setText(f'ERROR: {msg}')

    def _summary(self, *, partial: bool) -> str:
        n = len(self.rows)
        counts = {k: 0 for k in ('TP', 'FP', 'TN', 'FN_M', 'FN_NM', 'ERROR')}
        comp_yes = comp_no = comp_na = 0
        for r in self.rows:
            counts[r.get('classification', '')] = counts.get(r.get('classification', ''), 0) + 1
            ca = r.get('all_actions_compliant', '')
            if ca == 1 or ca == '1':
                comp_yes += 1
            elif ca == 0 or ca == '0':
                comp_no += 1
            else:
                comp_na += 1
        valid = n - counts['ERROR']
        # Classical FN is the sum of both maneuver modes.
        fn = counts['FN_M'] + counts['FN_NM']
        tp, fp = counts['TP'], counts['FP']
        recall = tp / (tp + fn) if (tp + fn) else float('nan')
        prec   = tp / (tp + fp) if (tp + fp) else float('nan')
        wall = time.perf_counter() - self.t0
        tag = 'partial' if partial else 'final'
        return (f'[{tag}] rows={n}  TP={counts["TP"]}  FP={counts["FP"]}  '
                f'TN={counts["TN"]}  FN={fn} (M={counts["FN_M"]}/NM={counts["FN_NM"]})  '
                f'ERR={counts["ERROR"]}   '
                f'recall={recall:.3f}  precision={prec:.3f}   '
                f'compliant={comp_yes}/non-compliant={comp_no}/no-maneuver={comp_na}   '
                f'wall={wall:.1f}s')

    @Slot()
    def _on_save(self):
        if not self.rows:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save batch CSV', 'batch_results.csv', 'CSV (*.csv)')
        if not path:
            return
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            w.writeheader()
            w.writerows(self.rows)
        QMessageBox.information(self, 'Saved', f'Wrote {len(self.rows)} rows to:\n{path}')


# ---------------------------------------------------------------------------
# Custom-trajectory tab
# ---------------------------------------------------------------------------
class _WaypointTable(QWidget):
    """Compact (t, N, E, D) table editor with +/- row buttons.

    Times are entered in seconds, positions in metres (NED, positive
    down).  Cells store plain text and are parsed to ``float`` on
    demand; invalid rows raise ``ValueError`` from :meth:`rows`.
    """

    HEADERS = ['t [s]', 'N [m]', 'E [m]', 'D [m]']

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        v.addWidget(self.table)
        h = QHBoxLayout()
        self.btn_add = QPushButton('+ Add row')
        self.btn_del = QPushButton('− Remove row')
        h.addWidget(self.btn_add); h.addWidget(self.btn_del); h.addStretch(1)
        v.addLayout(h)
        # Wrap in lambdas so the bool from QPushButton.clicked doesn't
        # get passed as the ``values`` arg to ``_add_row``.
        self.btn_add.clicked.connect(lambda: self._add_row())
        self.btn_del.clicked.connect(lambda: self._del_row())

    def _add_row(self, values=None):
        r = self.table.rowCount()
        self.table.insertRow(r)
        vals = values if values is not None else ('', '', '', '')
        for c, val in enumerate(vals):
            self.table.setItem(r, c, QTableWidgetItem(str(val)))

    def _del_row(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()},
                      reverse=True)
        if not rows:
            r = self.table.rowCount() - 1
            if r >= 0:
                self.table.removeRow(r)
            return
        for r in rows:
            self.table.removeRow(r)

    def set_rows(self, rows):
        self.table.setRowCount(0)
        for row in rows:
            self._add_row(row)

    def rows(self) -> list[tuple]:
        out = []
        for r in range(self.table.rowCount()):
            cells = []
            for c in range(4):
                item = self.table.item(r, c)
                txt = '' if item is None else item.text().strip()
                if txt == '':
                    # Skip rows that are entirely blank, otherwise
                    # complain on first missing cell.
                    cells = None
                    break
                try:
                    cells.append(float(txt))
                except ValueError as exc:
                    raise ValueError(
                        f'Row {r + 1}, column "{self.HEADERS[c]}": '
                        f'cannot parse "{txt}" as a number.'
                    ) from exc
            if cells is not None:
                out.append(tuple(cells))
        return out


# ---------------------------------------------------------------------------
# Preset encounters
# ---------------------------------------------------------------------------
# Pre-built encounters that exercise the currently supported cases
# catalogued in
# ``sw_conflict_resolution/scripts/encounter_cases.md``.  Each preset
# fixes the four kinematic state vectors (ownship / intruder initial
# position and velocity, NED, m / m·s⁻¹) plus a duration; both
# vehicles fly in straight lines through their waypoint tables so the
# CPA geometry is deterministic.  Cases whose *selection* depends on
# non-kinematic operational metadata (intruder category,
# alerting count) additionally carry an ``encounter_meta``
# dict that is forwarded to the encounter classifier — so those cases
# are activated by setting that metadata rather than by geometry alone.
# The near-ceiling / near-floor cases (14 / 15) instead place the
# ownship close to the default flight-envelope altitude limit so the
# classifier resolves the band from the geometry itself.
#
# Several cases admit more than one valid escape (``M_VACATE_LATERAL``
# = right or left; ``M_LATERAL_OR_CLIMB`` = lateral or climb;
# ``M_LATERAL_OR_DESCEND`` = lateral or descend).  For those, the
# avoidance FSM keeps the full candidate set and commits to the
# *compliant* escape with the best cylindrical-separation-per-energy
# score; the realised branch is therefore steered by the per-maneuver
# energy-cost ratios, not by restricting generators.  Each such case is
# offered as paired "a"/"b" presets that differ only in those ratios so
# every valid escape of the case can be activated and demonstrated.
_PRESET_CRUISE_ALT_M = -304.8   # NED D; positive-down so this is 304.8 m AGL
_PRESET_T_CPA_S       = 80.0
# Ownship altitudes (NED D, positive-down) for the near-ceiling /
# near-floor presets.  Chosen against the default flight envelope
# (alt_max = 609.6 m AGL, alt_min = 0 m AGL) and the default 213.36 m
# vertical-shift margin so the classifier resolves Case 14 / 15:
#   near ceiling: 1500 m AGL + 213.36 m climb ≥ 609.6 m ceiling
#   near floor:    400 m AGL − 213.36 m descent ≤ 0 m floor
_PRESET_NEAR_CEIL_ALT_M  = -457.2   # 1500 m AGL, near the 609.6 m ceiling
_PRESET_NEAR_FLOOR_ALT_M = -121.92    # 400 m AGL, near the 0 m floor
# Vertical separation (m) used by the intruder-above / intruder-below
# presets (Cases 10 / 11 / 14 / 15).  The classifier treats an encounter
# as co-altitude when |Δh| ≤ cyl_h / 2 (half the alert-cylinder height,
# a configurable parameter; the default 304.8 m cylinder gives a ±152.4 m
# band).  The separation must therefore sit *clearly outside* that band
# for the vertical case to be selected, so it is placed 91.44 m beyond the
# default half-height rather than exactly on the 152.4 m boundary.
_PRESET_VERT_SEP_M = 243.84


def _preset(name: str, description: str, *,
            own_v, intr_v,
            intr_extra_d: float = 0.0,
            intr_offset_ne=(0.0, 0.0),
            duration: float = 160.0,
            t_cpa: float = _PRESET_T_CPA_S,
            own_alt_d: float = _PRESET_CRUISE_ALT_M,
            meta: dict = None,
            energy: dict = None) -> dict:
    """Build a preset from CPA-relative velocity vectors.

    The ownship and intruder are placed so they both reach the CPA
    point ``(0, 0, own_alt_d)`` at ``t = t_cpa`` while flying in
    straight lines at the supplied NED velocities.  ``intr_extra_d``
    offsets the intruder's vertical position (positive-down) so
    above / below cases can reuse the same horizontal geometry.
    ``intr_offset_ne`` shifts the *whole* intruder track by ``(dN, dE)`` m so the encounter misses the nominal CPA (used to stage
    a behind-crossing, opening geometry).  ``meta`` is the optional
    per-encounter classifier-input dict (``intr_category`` /
    ``n_alerting``).  The
    near-ceiling / near-floor cases instead set ``own_alt_d`` close to
    a flight-envelope altitude limit so the classifier resolves the
    band from the geometry.  ``energy`` is an optional ``{maneuver: ratio}``
    override of the per-maneuver energy-cost ratios; it is how the
    per-escape variants (e.g. Case 11a vs 11b) activate a specific
    branch of a multi-escape case without restricting the candidate
    generators.  Unspecified maneuvers keep their default ratio.
    """
    own_p0  = (-own_v[0]  * t_cpa,
               -own_v[1]  * t_cpa,
                own_alt_d - own_v[2]  * t_cpa)
    intr_p0 = (intr_offset_ne[0] - intr_v[0] * t_cpa,
               intr_offset_ne[1] - intr_v[1] * t_cpa,
                own_alt_d + intr_extra_d - intr_v[2] * t_cpa)
    return dict(name=name, description=description, duration=duration,
                own_init_pos=own_p0, own_init_vel=own_v,
                intr_init_pos=intr_p0, intr_init_vel=intr_v,
                meta=dict(meta or {}), energy=dict(energy or {}))


# Convenience velocity vectors (NED, m/s).
_V_N100  = (0., 30.48, 0.)            # ownship cruising north at 100 m/s
_V_S150  = (0., -45.72, 0.)           # intruder reciprocal (south) at 150
_V_E150  = (45.72, 0., 0.)           # intruder eastbound (from UAS left→right)
_DIAG    = 45.72 * 0.7071             # 45° component of a 150 m/s track

# Energy-cost-ratio overrides used by the per-escape preset variants.
# A multi-escape case (e.g. M_LATERAL_OR_CLIMB = lateral *or* climb)
# keeps its full compliant candidate set; the FSM then commits to the
# escape with the best cylindrical-separation-per-energy score.  These
# dicts make one branch cheaper so the matching "b" variant activates
# it, while the "a" variant keeps the default ratios (lateral / right
# preferred).  Only the relative magnitude of the ratios matters.
_E_PREFER_LEFT    = {'left_shift': 1.0, 'right_shift': 3.0}
_E_PREFER_CLIMB   = {'climb': 0.5, 'right_shift': 2.0}
_E_PREFER_DESCEND = {'descend': 0.5, 'right_shift': 2.0}
_E_PREFER_SLOW    = {'slow_down': 0.5, 'right_shift': 2.0}
_E_PREFER_RIGHT_OVER_SLOW = {'right_shift': 0.5, 'slow_down': 4.0}

_PRESETS: list[dict] = [
    _preset('Case 1 — Head-on',
            'Reciprocal tracks, co-altitude. Expected: M_TURN_RIGHT.',
            own_v=_V_N100, intr_v=_V_S150),
    _preset('Case 2 — Converging, intruder on right',
            '~90° crossing, intruder in UAS right hemisphere. '
            'Expected: M_TURN_RIGHT (pass behind).',
            own_v=_V_N100, intr_v=(41.91, 0.0, 0.0)),
    _preset('Case 3 — Converging, intruder on left',
            '~90° crossing, intruder in UAS left hemisphere. '
            'Expected: M_TURN_LEFT (turn away from the intruder).',
            own_v=_V_N100, intr_v=(-41.91, 0.0, 0.0)),
    _preset('Case 4 — Low-manoeuvrability intruder',
            'Head-on geometry but intruder is a glider (GLD). '
            'Expected: M_TURN_RIGHT with an enlarged margin (Case 4).',
            own_v=_V_N100, intr_v=_V_S150,
            meta=dict(intr_category='GLD')),
    _preset('Case 5a — UAS overtaking, lateral escape',
            'Same track, UAS faster than intruder ahead. '
            'M_TURN_RIGHT_OR_SLOW realised as a lateral (right) deviation '
            'to pass well clear (energy ratios favour the turn).',
            own_v=(0., 150., 0.), intr_v=(0., 50., 0.),
            t_cpa=60.0, duration=140.0,
            energy=_E_PREFER_RIGHT_OVER_SLOW),
    _preset('Case 5b — UAS overtaking, slow-down escape',
            'Same overtaking geometry, but the energy ratios make the '
            'speed reduction cheaper so M_TURN_RIGHT_OR_SLOW is realised '
            'as a slow_down: the UAS bleeds airspeed and abandons the '
            'overtake, letting the slower aircraft ahead pull clear '
            'without a heading change.',
            own_v=(0., 150., 0.), intr_v=(0., 50., 0.),
            t_cpa=60.0, duration=140.0,
            energy=_E_PREFER_SLOW),
    _preset('Case 6 — Intruder overtaking UAS',
            'Same track, intruder faster behind UAS. '
            'Expected: M_TURN_RIGHT (step aside).',
            own_v=(0., 50., 0.),  intr_v=(0., 150., 0.),
            t_cpa=60.0, duration=140.0),
    _preset('Case 10 — Intruder above (243.84 m)',
            'Head-on at co-track, intruder 243.84 m above (clear of the '
            'co-altitude band). Expected: M_DESCEND.',
            own_v=_V_N100, intr_v=_V_S150,
            intr_extra_d=-_PRESET_VERT_SEP_M),
    _preset('Case 11a — Intruder below, lateral escape',
            'Head-on at co-track, intruder 243.84 m below. '
            'M_LATERAL_OR_CLIMB realised as a lateral (right) turn '
            '(default energy bias; descent is barred).',
            own_v=_V_N100, intr_v=_V_S150,
            intr_extra_d=+_PRESET_VERT_SEP_M),
    _preset('Case 11b — Intruder below, climb escape',
            'Same intruder-below geometry, but the energy ratios make '
            'the climb cheaper so M_LATERAL_OR_CLIMB is realised as a '
            'climb instead of a lateral turn.',
            own_v=_V_N100, intr_v=_V_S150,
            intr_extra_d=+_PRESET_VERT_SEP_M,
            energy=_E_PREFER_CLIMB),
    _preset('Case 12 — Crossing ahead (135°)',
            'Intruder crossing UAS track from ahead-left to '
            'ahead-right at a non-converging angle. '
            'Expected: M_TURN_RIGHT (route behind).',
            own_v=_V_N100, intr_v=(-_DIAG, -_DIAG, 0.)),
    _preset('Case 13 — Crossing behind (opening)',
            'Intruder crosses the UAS ground track well behind the tail '
            'with separation already opening. Expected: M_HOLD_TRACK — '
            'the geometry stays clear of the alert threshold, so no '
            'manoeuvre is commanded and the UAS holds its route.',
            own_v=_V_N100, intr_v=_V_E150,
            intr_offset_ne=(-4000.0, 0.0), duration=120.0),
    _preset('Case 14a — Near VLL ceiling, lateral escape',
            'Intruder below while the UAS cruises near the flight-'
            'envelope ceiling, so climbing is barred. '
            'M_LATERAL_OR_DESCEND realised as a '
            'lateral (right) turn (default energy bias).',
            own_v=_V_N100, intr_v=_V_S150, intr_extra_d=+_PRESET_VERT_SEP_M,
            own_alt_d=_PRESET_NEAR_CEIL_ALT_M),
    _preset('Case 14b — Near VLL ceiling, descend escape',
            'Same near-ceiling geometry, energy ratios make the '
            'descent cheaper so M_LATERAL_OR_DESCEND is realised as a '
            'controlled descent.',
            own_v=_V_N100, intr_v=_V_S150, intr_extra_d=+_PRESET_VERT_SEP_M,
            own_alt_d=_PRESET_NEAR_CEIL_ALT_M,
            energy=_E_PREFER_DESCEND),
    _preset('Case 15a — Near floor / terrain, lateral escape',
            'Intruder above while the UAS cruises near the flight-'
            'envelope floor, so descending is barred. '
            'M_LATERAL_OR_CLIMB realised as a '
            'lateral (right) turn (default energy bias).',
            own_v=_V_N100, intr_v=_V_S150, intr_extra_d=-_PRESET_VERT_SEP_M,
            own_alt_d=_PRESET_NEAR_FLOOR_ALT_M),
    _preset('Case 15b — Near floor / terrain, climb escape',
            'Same near-floor geometry, energy ratios make the climb '
            'cheaper so M_LATERAL_OR_CLIMB is realised as a climb.',
            own_v=_V_N100, intr_v=_V_S150, intr_extra_d=-_PRESET_VERT_SEP_M,
            own_alt_d=_PRESET_NEAR_FLOOR_ALT_M,
            energy=_E_PREFER_CLIMB),
    _preset('Case 16a — Multiple intruders, vacate right',
            'Two or more intruders alerting simultaneously. '
            'M_VACATE_LATERAL realised as a RIGHT global separation '
            '(default energy bias). Only the first intruder is '
            'simulated; n_alerting≥2 drives the classification.',
            own_v=_V_N100, intr_v=_V_S150,
            meta=dict(n_alerting=2)),
    _preset('Case 16b — Multiple intruders, vacate left',
            'Same multi-intruder classification, energy ratios favour '
            'the LEFT global separation so M_VACATE_LATERAL is realised '
            'to the left.',
            own_v=_V_N100, intr_v=_V_S150,
            meta=dict(n_alerting=2),
            energy=_E_PREFER_LEFT),
]


class CustomTrajectoryTab(QWidget):
    """Run the avoidance pipeline against a hand-crafted encounter
    defined by an explicit ownship initial state plus ownship and
    intruder waypoint tables.

    Bypasses the seeded encounter generator by feeding a pre-built
    ``true_df`` directly into :func:`run_simulation` via its
    ``true_df`` kwarg, so the simulation, recorder and visualiser are
    shared with the Single-seed tab.
    """

    def __init__(self, params: ParamSet, panel: 'ParameterPanel', parent=None):
        super().__init__(parent)
        self.params = params
        # The energy-cost ratios live in the shared parameter panel; the
        # Custom tab drives those spinners when a preset is selected.
        self.panel = panel
        self.worker: CustomSimWorker | None = None
        self.last_result = None
        self._anims: list = []

        outer = QVBoxLayout(self)

        # ---- Preset selector --------------------------------------
        # Reproducible geometries from
        # sw_conflict_resolution/scripts/encounter_cases.md.  Loading
        # a preset overwrites every widget in the tab; the user can
        # still tweak the spinners / tables afterwards.
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel('Preset encounter:'))
        self.cb_preset = _NoWheelComboBox()
        self.cb_preset.addItem('(custom — leave fields as-is)')
        for p in _PRESETS:
            self.cb_preset.addItem(p['name'], p)
        self.cb_preset.setToolTip(
            'Pick one of the encounter cases catalogued in '
            'encounter_cases.md to populate the initial-state '
            'spinners and the ownship/intruder waypoint tables '
            'with a deterministic geometry.  Selecting '
            '"(custom …)" leaves all fields as-is.')
        preset_row.addWidget(self.cb_preset, 1)
        outer.addLayout(preset_row)
        self.lbl_preset_desc = QLabel('')
        self.lbl_preset_desc.setWordWrap(True)
        self.lbl_preset_desc.setStyleSheet('color: #888;')
        outer.addWidget(self.lbl_preset_desc)

        # ---- Top row: duration ------------------------------------
        # (time step ``dt`` now lives in the Parameters panel, right
        # below "Look-ahead time".)
        top = QHBoxLayout()
        top.addWidget(QLabel('Duration:'))
        self.sb_duration = _NoWheelDoubleSpinBox()
        self.sb_duration.setRange(0.5, 3600.0)
        self.sb_duration.setDecimals(2)
        self.sb_duration.setValue(400.0)
        self.sb_duration.setSuffix(' s')
        top.addWidget(self.sb_duration)
        top.addStretch(1)
        self.btn_run  = QPushButton('Run simulation')
        self.btn_view = QPushButton('Visualize 3-D')
        self.btn_view.setEnabled(False)
        top.addWidget(self.btn_run)
        top.addWidget(self.btn_view)
        outer.addLayout(top)

        # ---- Ownship initial state ---------------------------------
        gb_init = QGroupBox('Ownship initial state (NED, m / m·s⁻¹)')
        fi = QFormLayout(gb_init)
        self.sb_n0  = self._mk_spin(-1e7, 1e7, 0.0, ' m')
        self.sb_e0  = self._mk_spin(-1e7, 1e7, -1219.2, ' m')
        self.sb_d0  = self._mk_spin(-1e6, 1e6, 0.0, ' m')
        self.sb_vn0 = self._mk_spin(-2000.0, 2000.0, 0.0,  ' m/s')
        self.sb_ve0 = self._mk_spin(-2000.0, 2000.0, 20.0, ' m/s')
        self.sb_vd0 = self._mk_spin(-1000.0, 1000.0, 0.0,  ' m/s')
        rp = QHBoxLayout()
        rp.addWidget(QLabel('N:')); rp.addWidget(self.sb_n0)
        rp.addWidget(QLabel('E:')); rp.addWidget(self.sb_e0)
        rp.addWidget(QLabel('D:')); rp.addWidget(self.sb_d0)
        wrp = QWidget(); wrp.setLayout(rp)
        fi.addRow('Position:', wrp)
        rv = QHBoxLayout()
        rv.addWidget(QLabel('vN:')); rv.addWidget(self.sb_vn0)
        rv.addWidget(QLabel('vE:')); rv.addWidget(self.sb_ve0)
        rv.addWidget(QLabel('vD:')); rv.addWidget(self.sb_vd0)
        wrv = QWidget(); wrv.setLayout(rv)
        fi.addRow('Velocity:', wrv)
        outer.addWidget(gb_init)

        # ---- Encounter classifier inputs ---------------------------
        # Non-kinematic operational metadata forwarded to the encounter
        # classifier.  These select the cases that geometry alone
        # cannot reach (intruder category → Case 4;
        # ownship altitude band → Cases 14/15;
        # alerting count ≥ 2 → Case 16).  Defaults reproduce the
        # nominal mid-band / single-intruder behaviour.
        gb_meta = QGroupBox('Encounter metadata (classifier inputs)')
        fm = QFormLayout(gb_meta)
        self.cb_intr_category = _NoWheelComboBox()
        self.cb_intr_category.addItem('(powered HTA — normal)', '')
        for _code, _label in (('GLD', 'GLD — glider'),
                              ('BAL', 'BAL — balloon'),
                              ('ARS', 'ARS — airship'),
                              ('SLG', 'SLG — slung load'),
                              ('TOW', 'TOW — towing')):
            self.cb_intr_category.addItem(_label, _code)
        self.cb_intr_category.setToolTip(
            'Reduced-manoeuvrability intruder categories select '
            'Case 4 (wider, earlier right turn).')
        fm.addRow('Intruder category:', self.cb_intr_category)

        meta_flags = QHBoxLayout()
        meta_flags.addWidget(QLabel('Alerting intruders:'))
        self.sb_n_alerting = _NoWheelSpinBox()
        self.sb_n_alerting.setRange(1, 16)
        self.sb_n_alerting.setValue(1)
        self.sb_n_alerting.setToolTip(
            '≥ 2 selects Case 16 (global lateral separation). Only the '
            'first intruder is physically simulated.')
        meta_flags.addWidget(self.sb_n_alerting)
        meta_flags.addStretch(1)
        wmf = QWidget(); wmf.setLayout(meta_flags)
        fm.addRow('Flags:', wmf)
        outer.addWidget(gb_meta)

        # ---- Waypoint tables ---------------------------------------
        tables_row = QHBoxLayout()
        gb_own = QGroupBox('Ownship waypoints (optional — leave empty '
                           'for straight-line propagation)')
        vo = QVBoxLayout(gb_own)
        self.tbl_own = _WaypointTable()
        self.tbl_own.set_rows([
            (0.0,   0.0, -4000.0, 0.0),
            (400.0, 0.0,  4000.0, 0.0),
        ])
        vo.addWidget(self.tbl_own)
        tables_row.addWidget(gb_own, 1)

        gb_int = QGroupBox('Intruder waypoints (≥ 2 required)')
        vi = QVBoxLayout(gb_int)
        self.tbl_int = _WaypointTable()
        # Pre-populate a sensible head-on encounter so the user has
        # something to "Run" immediately.
        self.tbl_int.set_rows([
            (0.0,   0.0,  4000.0, 0.0),
            (400.0, 0.0, -4000.0, 0.0),
        ])
        vi.addWidget(self.tbl_int)
        tables_row.addWidget(gb_int, 1)
        outer.addLayout(tables_row, 1)

        # ---- Result summary ----------------------------------------
        gb_res = QGroupBox('Result summary')
        vr = QVBoxLayout(gb_res)
        self.txt = QTextEdit(); self.txt.setReadOnly(True)
        f = QFont('Consolas'); f.setStyleHint(QFont.Monospace)
        self.txt.setFont(f)
        vr.addWidget(self.txt)
        outer.addWidget(gb_res, 1)

        self.btn_run.clicked.connect(self._on_run)
        self.btn_view.clicked.connect(self._on_view)
        self.cb_preset.currentIndexChanged.connect(self._on_preset_changed)

    @staticmethod
    def _mk_spin(lo, hi, val, suffix):
        sb = _NoWheelDoubleSpinBox()
        sb.setRange(lo, hi)
        sb.setDecimals(2)
        sb.setValue(val)
        sb.setSuffix(suffix)
        sb.setMinimumWidth(110)
        return sb

    @Slot(int)
    def _on_preset_changed(self, idx: int):
        """Update the description and immediately apply the preset to
        the initial-state spinners and waypoint tables.  Selecting the
        first entry (``(custom …)``) leaves all fields untouched so
        the user can return to manual editing without losing work.
        """
        p = self.cb_preset.itemData(idx)
        self.lbl_preset_desc.setText(p['description'] if p else '')
        if p is None:
            return
        op = p['own_init_pos']; ov = p['own_init_vel']
        ip = p['intr_init_pos']; iv = p['intr_init_vel']
        T  = float(p['duration'])
        self.sb_duration.setValue(T)
        self.sb_n0.setValue(op[0]);  self.sb_e0.setValue(op[1])
        self.sb_d0.setValue(op[2])
        self.sb_vn0.setValue(ov[0]); self.sb_ve0.setValue(ov[1])
        self.sb_vd0.setValue(ov[2])
        self.tbl_own.set_rows([
            (0.0, op[0],           op[1],           op[2]),
            (T,   op[0] + ov[0]*T, op[1] + ov[1]*T, op[2] + ov[2]*T),
        ])
        self.tbl_int.set_rows([
            (0.0, ip[0],           ip[1],           ip[2]),
            (T,   ip[0] + iv[0]*T, ip[1] + iv[1]*T, ip[2] + iv[2]*T),
        ])
        # Apply the preset's classifier metadata (resetting any field
        # the preset does not specify to its nominal default).
        meta = p.get('meta', {})
        self._set_combo_data(self.cb_intr_category,
                             meta.get('intr_category', ''))
        self.sb_n_alerting.setValue(int(meta.get('n_alerting', 1)))
        # Apply the preset's energy-cost-ratio overrides to the shared
        # parameter panel, resetting any maneuver the preset does not
        # mention to its default ratio.  Writing the panel spinners
        # live-syncs the values into the shared ParamSet.
        energy = p.get('energy', {})
        for _name, _sb in self.panel._energy_spins.items():
            _sb.setValue(float(energy.get(
                _name, DEFAULT_ENERGY_COST_RATIOS.get(_name, 1.0))))

    @staticmethod
    def _set_combo_data(combo, data):
        """Select the combo entry whose userData equals ``data``."""
        idx = combo.findData(data)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _collect_encounter_meta(self) -> dict:
        """Read the encounter-metadata widgets into the classifier
        kwargs forwarded to :func:`run_simulation`.

        Energy-cost ratios are *not* included here: they live in the
        shared parameter panel and reach :func:`run_simulation` through
        ``ParamSet.as_sim_kwargs`` instead, so passing them again would
        collide with that kwarg."""
        return dict(
            intr_category=str(self.cb_intr_category.currentData() or ''),
            n_alerting=int(self.sb_n_alerting.value()),
        )

    def _collect_sim_inputs(self):
        """Collect widget state → route + initial state.

        Returns ``(own_waypoints, own_init_pos, own_init_vel,
        intr_waypoints, dt)`` suitable for direct injection into
        :class:`CustomSimWorker`.  The initial position and velocity
        spinboxes define the *actual* ownship starting pose; the
        ownship waypoint table is the *desired route* the controller
        tries to follow and may start off the initial position
        (the cross-track law will re-acquire it).  When the table is
        empty a straight-line route is synthesised from the initial
        state along the initial velocity, so the airframe just flies
        forward.
        """
        own_init_pos = (float(self.sb_n0.value()),
                        float(self.sb_e0.value()),
                        float(self.sb_d0.value()))
        own_init_vel = (float(self.sb_vn0.value()),
                        float(self.sb_ve0.value()),
                        float(self.sb_vd0.value()))
        # Desired route from the table, as-is.  The first row
        # supplies the route geometry independent of the airframe's
        # actual starting position.
        own_wps  = list(self.tbl_own.rows())
        intr_wps = self.tbl_int.rows()
        if len(own_wps) < 2:
            # No (or insufficient) user route: synthesise a straight
            # line from the initial state along the initial velocity
            # so the controller has at least two points to track.
            T = float(self.sb_duration.value())
            own_wps = [(0.0, own_init_pos[0],
                              own_init_pos[1],
                              own_init_pos[2]),
                       (T,   own_init_pos[0] + own_init_vel[0] * T,
                              own_init_pos[1] + own_init_vel[1] * T,
                              own_init_pos[2] + own_init_vel[2] * T)]
        return own_wps, own_init_pos, own_init_vel, intr_wps, float(self.params.dt)

    @Slot()
    def _on_run(self):
        if self.worker is not None and self.worker.isRunning():
            return
        try:
            own_wps, own_init_pos, own_init_vel, intr_wps, dt = \
                self._collect_sim_inputs()
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Invalid trajectory', str(exc))
            return
        self.btn_run.setEnabled(False)
        self.btn_view.setEnabled(False)
        self.last_result = None
        self.txt.setPlainText('Running custom trajectory ...')
        self.worker = CustomSimWorker(own_wps, own_init_pos, own_init_vel,
                                      intr_wps, dt, self.params,
                                      self._collect_encounter_meta(), self)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_fail)
        self.worker.start()

    @Slot(object)
    def _on_done(self, result):
        self.btn_run.setEnabled(True)
        self.btn_view.setEnabled(True)
        self.last_result = result
        self.txt.setPlainText(_format_result_summary(result, seed=None))

    @Slot(str)
    def _on_fail(self, msg):
        self.btn_run.setEnabled(True)
        self.btn_view.setEnabled(False)
        self.txt.setPlainText(f'ERROR: {msg}')

    @Slot()
    def _on_view(self):
        if self.last_result is None:
            return
        from daa_conflict_resolution.visualize_avoidance import animate
        try:
            anim = animate(self.last_result,
                           n_sigma=self.params.n_sigma,
                           stride=10, seed=None)
            if anim is not None:
                self._anims.append(anim)
        except Exception as exc:                                  # noqa: BLE001
            QMessageBox.critical(self, 'Visualiser error',
                                 f'{type(exc).__name__}: {exc}')


# ---------------------------------------------------------------------------
# Tests tab — runs every built-in preset as a regression smoke test
# ---------------------------------------------------------------------------
def _preset_expected_case(name: str):
    """Parse the expected classifier case id from a preset name such as
    ``'Case 11a — ...'`` → ``11``.  Returns ``None`` if the name does
    not start with a ``Case N`` tag."""
    import re
    m = re.match(r'\s*Case\s+(\d+)', name)
    return int(m.group(1)) if m else None


# Presets whose faithful expected outcome is *no alert* (M_HOLD_TRACK):
# the classifier returns no encounter and no maneuver is flown.
_NO_ALERT_CASES = frozenset({13})


class TestsWorker(QThread):
    """Runs every entry in ``_PRESETS`` through ``run_simulation`` on a
    background thread, emitting one row per preset so the Tests tab can
    fill its table live.  Uses the current :class:`ParamSet` so the
    smoke test reflects the parameters configured on the Parameters
    tab."""
    row_done     = Signal(int, int, dict)     # (done, total, row)
    finished_all = Signal(int, int)           # (passed, total)
    failed       = Signal(str)

    def __init__(self, params: ParamSet, parent=None):
        super().__init__(parent)
        self.params = params

    def run(self):  # noqa: D401
        try:
            presets = _PRESETS
            total   = len(presets)
            passed  = 0
            for i, p in enumerate(presets):
                row = self._run_one(p)
                if row['status'] == 'PASS':
                    passed += 1
                self.row_done.emit(i + 1, total, row)
            self.finished_all.emit(passed, total)
        except Exception as exc:                                  # noqa: BLE001
            self.failed.emit(f'{type(exc).__name__}: {exc}')

    def _run_one(self, p: dict) -> dict:
        name     = p['name']
        expected = _preset_expected_case(name)
        op, ov   = p['own_init_pos'], p['own_init_vel']
        ip, iv   = p['intr_init_pos'], p['intr_init_vel']
        T        = p['duration']
        own_wps  = [(0.0, *op),
                    (T, op[0] + ov[0] * T, op[1] + ov[1] * T, op[2] + ov[2] * T)]
        intr_wps = [(0.0, *ip),
                    (T, ip[0] + iv[0] * T, ip[1] + iv[1] * T, ip[2] + iv[2] * T)]
        try:
            # The panel's energy ratios reach run_simulation via
            # as_sim_kwargs; override them with the preset's own ratios
            # (or None ⇒ library defaults) so each regression case is
            # judged against its declared expectation, independent of
            # whatever the user has set in the panel.
            sim_kw = self.params.as_sim_kwargs()
            sim_kw['energy_cost_ratios'] = p['energy'] or None
            r = run_simulation(
                own_waypoints  = own_wps,
                own_p0         = op,
                own_init_vel   = ov,
                intr_waypoints = intr_wps,
                generators     = self.params.make_generators(),
                record_history = True,
                **p['meta'],
                **sim_kw,
            )
        except Exception as exc:                                  # noqa: BLE001
            return dict(name=name, expected=expected, classified='—',
                        maneuver='—', compliant='—', escape='—',
                        status='ERROR', detail=f'{type(exc).__name__}: {exc}')

        ec = r.encounter
        esc_idx = _first_escape_idx(r)
        escape  = (r.candidate_names[esc_idx]
                   if 0 <= esc_idx < len(r.candidate_names) else '—')
        if ec is None:
            classified = 'no-alert'
            ok = expected in _NO_ALERT_CASES
            return dict(name=name, expected=expected, classified=classified,
                        maneuver='M_HOLD_TRACK', compliant='—', escape=escape,
                        status='PASS' if ok else 'FAIL', detail='')
        ok = (expected is None) or (ec.case_id == expected)
        return dict(name=name, expected=expected, classified=str(ec.case_id),
                    maneuver=ec.maneuver,
                    compliant=', '.join(ec.compliant_actions) or '—',
                    escape=escape, status='PASS' if ok else 'FAIL', detail='')


class TestsTab(QWidget):
    """Regression smoke test for the built-in encounter presets.

    Runs every preset that the Custom-trajectory tab exposes and checks
    that the classifier still assigns the expected case, reporting which
    escape the avoidance FSM actually committed (so per-escape variants
    such as Case 11a vs 11b can be eyeballed at a glance)."""

    _COLS = ('Preset', 'Expected', 'Classified', 'Maneuver',
             'Compliant actions', 'Escape flown', 'Status')

    def __init__(self, params: ParamSet, parent=None):
        super().__init__(parent)
        self.params = params
        self._worker = None

        root = QVBoxLayout(self)

        intro = QLabel(
            'Runs every built-in encounter preset through the full '
            'avoidance pipeline and verifies the classifier still '
            'assigns the expected case.  The "Escape flown" column shows '
            'which maneuver the FSM committed — use it to confirm the '
            'per-escape (a / b) variants pick the intended branch.\n'
            'Tests use the parameters currently set on the Parameters tab.')
        intro.setWordWrap(True)
        root.addWidget(intro)

        ctl = QHBoxLayout()
        self.btn_run = QPushButton('Run all preset tests')
        self.btn_run.clicked.connect(self._on_run)
        ctl.addWidget(self.btn_run)
        self.progress = QProgressBar()
        self.progress.setRange(0, len(_PRESETS))
        self.progress.setValue(0)
        ctl.addWidget(self.progress, 1)
        self.lbl_summary = QLabel('—')
        ctl.addWidget(self.lbl_summary)
        root.addLayout(ctl)

        self.table = QTableWidget(0, len(self._COLS))
        self.table.setHorizontalHeaderLabels(self._COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(False)
        root.addWidget(self.table, 1)

    # ------------------------------------------------------------------
    @Slot()
    def _on_run(self):
        self.btn_run.setEnabled(False)
        self.lbl_summary.setText('running…')
        self.progress.setRange(0, len(_PRESETS))
        self.progress.setValue(0)
        self.table.setRowCount(0)
        self._worker = TestsWorker(self.params, parent=self)
        self._worker.row_done.connect(self._on_row)
        self._worker.finished_all.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    @Slot(int, int, dict)
    def _on_row(self, done, total, row):
        self.progress.setValue(done)
        r = self.table.rowCount()
        self.table.insertRow(r)
        exp = '—' if row['expected'] is None else str(row['expected'])
        values = (row['name'], exp, row['classified'], row['maneuver'],
                  row['compliant'], row['escape'], row['status'])
        status = row['status']
        if status == 'PASS':
            colour = QColor(200, 240, 200)
        elif status == 'FAIL':
            colour = QColor(245, 205, 205)
        else:                                       # ERROR
            colour = QColor(245, 225, 180)
        for c, val in enumerate(values):
            item = QTableWidgetItem(str(val))
            item.setBackground(colour)
            if row.get('detail') and c == len(values) - 1:
                item.setToolTip(row['detail'])
            self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()

    @Slot(int, int)
    def _on_done(self, passed, total):
        self.btn_run.setEnabled(True)
        failed = total - passed
        self.lbl_summary.setText(
            f'{passed}/{total} passed'
            + ('' if failed == 0 else f'  ·  {failed} failed'))

    @Slot(str)
    def _on_fail(self, msg):
        self.btn_run.setEnabled(True)
        self.lbl_summary.setText(f'ERROR: {msg}')


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'DAA Avoidance Simulator v{__version__}')
        self.resize(1320, 760)

        self.params = ParamSet()

        # Persistent parameter panel on the left, action tabs on the
        # right, split by a draggable handle.
        self.panel = ParameterPanel(self.params)
        self.panel.setMinimumWidth(440)

        tabs = QTabWidget()
        self.single_tab = SingleSeedTab(self.params)
        self.custom_tab = CustomTrajectoryTab(self.params, self.panel)
        self.mc_tab     = MonteCarloTab(self.params)
        self.tests_tab  = TestsTab(self.params)
        tabs.addTab(self.single_tab, 'Single seed')
        tabs.addTab(self.mc_tab,     'Monte Carlo')
        tabs.addTab(self.custom_tab, 'Custom trajectory')
        tabs.addTab(self.tests_tab,  'Tests')

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.panel)
        split.addWidget(tabs)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([460, 860])
        self.setCentralWidget(split)


def main():
    # PyInstaller / multiprocessing requirement on Windows.
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
