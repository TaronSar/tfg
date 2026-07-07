#!/usr/bin/env python3
"""
Live 3D visualisation of the avoidance simulation.

Runs ``avoidance_core.run_simulation`` for a fixed seed and animates a
3D NEU view (x=East, y=North, z=Up) showing:
  - past true ownship + intruder trajectories (solid lines),
  - past estimated intruder trajectory (dashed),
  - the would-have-flown original ownship route (faint dashed),
  - the extrapolated candidate ownship trajectories (dotted, one per
    candidate returned by the trajectory generator),
  - the ownship protection cylinder (3D surface),
  - the intruder 1-sigma uncertainty ellipsoid,
  - an ``ALERT`` banner when the baseline candidate's min distance
    drops below the alert threshold and an ``AVOIDING`` banner once a
    maneuver is committed,
  - a side panel with the active route transform (route_xf): shift
    components, velocity scale and the maintain (hold-velocity) mode over
    time -- or, for the constant-bearing family, the maneuver azimuth /
    elevation over time.
"""

from __future__ import annotations

import argparse

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 -- registers 3d projection

from .avoidance_core import (
    run_simulation_from_spec,
    make_spec_from_seed,
    LOOKAHEAD_S,
    CYL_HEIGHT_M,
    CYL_DIAMETER_M,
    LATERAL_SHIFT_RATIO,
    ALERT_THRESHOLD,
    DEFAULT_HYSTERESIS_S,
    DEFAULT_RETURN_HYSTERESIS_S,
    CLOSED_LOOP_OPEN,
    CLOSED_LOOP_ON_CONFLICT,
    CLOSED_LOOP_PERIODIC,
    DEFAULT_CLOSED_LOOP_MODE,
    DEFAULT_SWITCH_IMPROVE_RATIO,
    DEFAULT_FOV_AZ_MIN_DEG,
    DEFAULT_FOV_AZ_MAX_DEG,
    DEFAULT_FOV_EL_MIN_DEG,
    DEFAULT_FOV_EL_MAX_DEG,
)
from .candidate_trajectories import (
    default_generators,
    MANEUVER_FAMILY_MIN_CONST_BEARING,
    DEFAULT_K_XT_PER_M,
    DEFAULT_A_MAX_ALONG_M_S2,
    DEFAULT_RATE_MAX_AZIMUTH_RAD_S,
    DEFAULT_RATE_MAX_ELEVATION_RAD_S,
)


# ---------------------------------------------------------------------------
# Lookahead horizons for the predicted intruder uncertainty cylinders
# (mirrors ``visualize_trajectories.py``).
# ---------------------------------------------------------------------------
LOOKAHEAD_HORIZONS_S = (15.0, 30.0, 45.0, 60.0)
LOOKAHEAD_COLORS    = ('#2ca02c', '#bcbd22', '#ff7f0e', '#d62728')

# Palette used to colour the candidate ownship trajectories. Index 0
# is reserved for the baseline ("do-nothing") candidate.
CANDIDATE_COLORS = ('#7f7f7f', '#2ca02c', '#9467bd', '#17becf',
                    '#e377c2', '#bcbd22', '#8c564b', '#1f77b4')


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _to_neu(arr_ned):
    """Map (..., 3) NED array to NEU columns (east, north, up)."""
    out = np.empty_like(arr_ned)
    out[..., 0] = arr_ned[..., 1]
    out[..., 1] = arr_ned[..., 0]
    out[..., 2] = -arr_ned[..., 2]
    return out


def _body_az_el_deg(intr_pos, own_pos, own_att):
    """Body-frame azimuth / elevation (deg) of the intruder per step.

    Vectorised counterpart of ``avoidance_core._ned_to_measurement``:
    rotates the NED relative position (intruder - ownship) into the
    ownship body frame using the recorded (roll, pitch, yaw) attitude,
    then returns ``(az_deg, el_deg)`` arrays.  These are exactly the
    angles the camera FOV gates on.
    """
    rel = (np.asarray(intr_pos, dtype=np.float64)
           - np.asarray(own_pos, dtype=np.float64))
    rel_n, rel_e, rel_d = rel[:, 0], rel[:, 1], rel[:, 2]
    roll, pitch, yaw = own_att[:, 0], own_att[:, 1], own_att[:, 2]
    cp, sp = np.cos(yaw),   np.sin(yaw)
    ct, st = np.cos(pitch), np.sin(pitch)
    cr, sr = np.cos(roll),  np.sin(roll)
    x_b = cp * ct * rel_n + sp * ct * rel_e - st * rel_d
    y_b = ((-sp * cr + cp * st * sr) * rel_n
           + (cp * cr + sp * st * sr) * rel_e
           + ct * sr * rel_d)
    z_b = ((sp * sr + cp * st * cr) * rel_n
           + (-cp * sr + sp * st * cr) * rel_e
           + ct * cr * rel_d)
    az = np.degrees(np.arctan2(y_b, x_b))
    el = np.degrees(np.arctan2(-z_b, np.sqrt(x_b * x_b + y_b * y_b)))
    return az, el


def _global_bounds_3d(result):
    """Return (xmin, xmax, ymin, ymax, zmin, zmax) in NEU coordinates."""
    pts = [
        _to_neu(result.own_pos),
        _to_neu(result.intr_true_pos),
        _to_neu(result.intr_est_pos),
    ]
    if result.cand_positions and len(result.cand_positions) > 0:
        pts.append(_to_neu(np.vstack([arr.reshape(-1, 3)
                                      for arr in result.cand_positions])))
    if result.cf_own_pos is not None:
        pts.append(_to_neu(result.cf_own_pos))
    if result.target_own_pos is not None:
        pts.append(_to_neu(result.target_own_pos))
    if result.cf_intr_pos is not None:
        pts.append(_to_neu(result.cf_intr_pos))
    all_pts = np.vstack(pts)
    # ``intr_est_pos`` (and other estimate-derived arrays) carry NaN
    # rows for frames where the camera could not see the intruder, so
    # use NaN-aware reductions to keep those gaps from poisoning the
    # axis limits.  Fall back to a unit box if every point is non-finite.
    finite = all_pts[np.isfinite(all_pts).all(axis=1)]
    if finite.size == 0:
        return (0.0, 1.0, 0.0, 1.0, 0.0, 1.0)
    return (finite[:, 0].min(), finite[:, 0].max(),
            finite[:, 1].min(), finite[:, 1].max(),
            finite[:, 2].min(), finite[:, 2].max())


def _set_equal_3d_bounds(ax, bounds, pad_m=152.4):
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    cx = 0.5 * (xmin + xmax); cy = 0.5 * (ymin + ymax); cz = 0.5 * (zmin + zmax)
    span = max(xmax - xmin, ymax - ymin, zmax - zmin) + 2 * pad_m
    half = span * 0.5
    ax.set_xlim(cx - half, cx + half)
    ax.set_ylim(cy - half, cy + half)
    ax.set_zlim(cz - half, cz + half)
    try:
        ax.set_box_aspect((1.0, 1.0, 1.0))
    except Exception:
        pass


def _cylinder_mesh(center_neu, radius, height, n_theta=24):
    """Vertical cylinder surface in NEU coordinates, centred at ``center_neu``."""
    cx, cy, cz = center_neu
    theta = np.linspace(0.0, 2 * np.pi, n_theta)
    z = np.array([cz - height * 0.5, cz + height * 0.5])
    T, Z = np.meshgrid(theta, z)
    X = cx + radius * np.cos(T)
    Y = cy + radius * np.sin(T)
    return X, Y, Z


def _ellipsoid_mesh(center_neu, cov_ned, n_sigma=1.0, n_u=18, n_v=10):
    """1-sigma ellipsoid surface for a 3x3 NED position covariance.

    The covariance is converted from NED to a (N, E, U) basis via
    ``D = diag(1, 1, -1)``; eigenvectors are then reordered to the
    (E, N, U) plotting axes.
    """
    D = np.diag([1.0, 1.0, -1.0])
    cov_neu = D @ cov_ned @ D  # axes still (N, E, U)
    vals, vecs = np.linalg.eigh(0.5 * (cov_neu + cov_neu.T))
    vals = np.clip(vals, 1e-9, None)
    radii = n_sigma * np.sqrt(vals)

    u = np.linspace(0.0, 2 * np.pi, n_u)
    v = np.linspace(0.0, np.pi, n_v)
    xs = np.outer(np.cos(u), np.sin(v))
    ys = np.outer(np.sin(u), np.sin(v))
    zs = np.outer(np.ones_like(u), np.cos(v))
    pts = np.vstack([xs.ravel(), ys.ravel(), zs.ravel()])
    pts = vecs @ np.diag(radii) @ pts  # in (N, E, U)

    # Reorder rows (N, E, U) -> (E, N, U) and translate
    e = pts[1].reshape(xs.shape) + center_neu[0]
    n = pts[0].reshape(xs.shape) + center_neu[1]
    u_ = pts[2].reshape(xs.shape) + center_neu[2]
    return e, n, u_


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

def animate(result, *, interval_ms=60, stride=10, save=None, n_sigma=2.0,
            seed=None):
    fig = plt.figure(figsize=(16, 9))
    gs = fig.add_gridspec(4, 2, width_ratios=[1.4, 1.0], hspace=0.55,
                          wspace=0.20)
    ax3d = fig.add_subplot(gs[:, 0], projection='3d')
    # Split the top-right cell into two side-by-side panels: ownship
    # velocity / acceleration on the left and the intruder az/el on the
    # right (the latter now narrower to make room).
    gs_top = gs[0, 1].subgridspec(1, 2, wspace=0.55)
    ax_va = fig.add_subplot(gs_top[0, 0])
    ax_ae = fig.add_subplot(gs_top[0, 1])
    # FOV / UKF track-state + uncertainty timeline, sitting directly on
    # top of the active-route-transform panel.
    ax_trk = fig.add_subplot(gs[1, 1])
    ax_d = fig.add_subplot(gs[2, 1])
    ax_sep = fig.add_subplot(gs[3, 1])
    # Reserve a strip at the bottom of the figure for the transport
    # controls (slider + play / step buttons) added at the end.
    fig.subplots_adjust(bottom=0.13)

    # ---- 3D map ----
    ax3d.set_xlabel('East (m)')
    ax3d.set_ylabel('North (m)')
    ax3d.set_zlabel('Up (m)')
    seed_tag = '' if seed is None else f'  —  seed {seed}'
    ax3d.set_title(f'Avoidance simulation — NEU 3D{seed_tag}')
    # Top-down view: look straight down along -Up, with North pointing up on screen.
    ax3d.view_init(elev=90, azim=-90)
    _set_equal_3d_bounds(ax3d, _global_bounds_3d(result))

    # Original (would-have-flown) ownship + full intruder route
    if result.cf_own_pos is not None:
        own_cf_neu  = _to_neu(result.cf_own_pos)
        intr_cf_neu = _to_neu(result.cf_intr_pos)
        ax3d.plot(own_cf_neu[:, 0], own_cf_neu[:, 1], own_cf_neu[:, 2],
                  '--', color='#1f77b4', lw=1.0, alpha=0.45,
                  label='Ownship (would-have-flown)')
        ax3d.plot(intr_cf_neu[:, 0], intr_cf_neu[:, 1], intr_cf_neu[:, 2],
                  '--', color='#d62728', lw=1.0, alpha=0.35,
                  label='Intruder (full route)')
    if result.target_own_pos is not None:
        own_tgt_neu = _to_neu(result.target_own_pos)
        ax3d.plot(own_tgt_neu[:, 0], own_tgt_neu[:, 1], own_tgt_neu[:, 2],
                  ':', color='#1f77b4', lw=0.9, alpha=0.55,
                  label='Ownship (target waypoints)')

    own_neu  = _to_neu(result.own_pos)
    intr_neu = _to_neu(result.intr_true_pos)
    est_neu  = _to_neu(result.intr_est_pos)

    (ln_own_true,) = ax3d.plot([], [], [], '-', color='#1f77b4', lw=2.0,
                               label='Ownship (true)')
    (ln_int_true,) = ax3d.plot([], [], [], '-', color='#d62728', lw=2.0,
                               label='Intruder (true)')
    (ln_int_est,)  = ax3d.plot([], [], [], '--', color='#ff7f0e', lw=1.4,
                               label='Intruder (estimated)')
    (mk_own,) = ax3d.plot([], [], [], 'o', color='#1f77b4', ms=6)
    (mk_int,) = ax3d.plot([], [], [], 's', color='#d62728', ms=6)
    # Tracker projection of the ownship onto the upcoming route
    # segment (from the C++ Route_tracker via daa_track_project).
    (mk_track,) = ax3d.plot([], [], [], 'x', color='#1f77b4', ms=8,
                            mew=2.0, label='Route track point')

    # Per-candidate dotted extrapolation lines (one per candidate, in
    # the order returned by the trajectory generator).
    K = len(result.candidate_names)
    cand_colors = [CANDIDATE_COLORS[k % len(CANDIDATE_COLORS)] for k in range(K)]
    cand_lines = []
    for k, name in enumerate(result.candidate_names):
        (ln,) = ax3d.plot([], [], [], ':', color=cand_colors[k], lw=1.5,
                          label=f'Extrap.: {name}')
        cand_lines.append(ln)

    # Per-step lookahead-horizon indices are computed inside the
    # animate() closure since result.sweep_taus is now a per-step
    # list of arrays (variable length from the C++ Route_tracker).

    # Predicted-intruder polyline (connects t, t+15, t+30, t+45, t+60)
    (ln_int_pred,) = ax3d.plot([], [], [], '-', color='#ff7f0e', lw=1.2,
                               alpha=0.7,
                               label='Intruder prediction (t+15/30/45/60)')
    pred_markers = []
    for h, color in zip(LOOKAHEAD_HORIZONS_S, LOOKAHEAD_COLORS):
        (mk,) = ax3d.plot([], [], [], 'o', color=color, ms=5,
                          label=f't+{int(h)} s')
        pred_markers.append(mk)

    # Per-step CPA markers — predicted closest-point-of-approach of
    # ownship and intruder *at the current step's lookahead window*.
    # These come straight from the C++ side (idx_cpa over the route
    # candidate's sweep) and are recomputed every step, so they move
    # as the lookahead window slides.  Drawn as moving stars + a
    # connecting segment.
    (mk_own_cpa,) = ax3d.plot([], [], [], marker='*', color='#1f77b4',
                              ms=14, mec='black', mew=1.0,
                              linestyle='None', label='Ownship CPA (predicted)')
    (mk_int_cpa,) = ax3d.plot([], [], [], marker='*', color='#d62728',
                              ms=14, mec='black', mew=1.0,
                              linestyle='None', label='Intruder CPA (predicted)')
    (ln_cpa_sep,) = ax3d.plot([], [], [], color='black', lw=1.0,
                              ls='--', alpha=0.6,
                              label='CPA separation (predicted)')

    # FOV-loss safe point — the last lookahead sample of the committed
    # avoidance maneuver.  Fixed in space at the start of the maneuver,
    # but only shown on the steps where the gate is actually holding back
    # the return (intruder out of the camera FOV, point not yet crossed),
    # so the marker appears only while it is in use.
    (mk_safe_point,) = ax3d.plot([], [], [], marker='P', color='#17becf',
                                 ms=14, mec='black', mew=1.2,
                                 linestyle='None',
                                 label='Safe point (FOV-loss gate)')

    ax3d.legend(loc='upper right', bbox_to_anchor=(-0.02, 1.0),
                fontsize=8, framealpha=0.85)

    # Mutable handles for surfaces redrawn per frame.
    surfaces = {'cyl': None, 'cyl_wf': None, 'ell': None}
    lookahead_surfaces = []  # list of (surface, wireframe) per horizon

    banner = fig.text(0.30, 0.95, '', ha='center', va='top',
                      fontsize=14, fontweight='bold')

    # Simulation-time read-out, refreshed every frame.  Boxed in the
    # top-left corner of the figure so it stays put while the 3D view
    # is rotated / panned.
    time_box = fig.text(0.015, 0.975, '', ha='left', va='top',
                        fontsize=12, fontweight='bold', family='monospace',
                        bbox=dict(boxstyle='round,pad=0.4',
                                  facecolor='#fffbe6', edgecolor='#888888',
                                  alpha=0.95))

    # ---- Right panel (top): intruder azimuth / elevation (ownship body frame) ----
    # Body-frame line-of-sight to the *true* intruder, in degrees, with
    # the camera FOV drawn as a box.  While the intruder is inside the box
    # the ownship can see (and therefore track) it.
    az_deg, el_deg = _body_az_el_deg(result.intr_true_pos,
                                     result.own_pos, result.own_att)
    ax_ae.set_title('Intruder azimuth / elevation (ownship body frame)')
    ax_ae.set_xlabel('azimuth (deg)')
    ax_ae.set_ylabel('elevation (deg)')
    ax_ae.grid(True, alpha=0.3)
    ax_ae.axhline(0.0, color='#999999', lw=0.8)
    ax_ae.axvline(0.0, color='#999999', lw=0.8)

    # Camera FOV box.
    fov_w = DEFAULT_FOV_AZ_MAX_DEG - DEFAULT_FOV_AZ_MIN_DEG
    fov_h = DEFAULT_FOV_EL_MAX_DEG - DEFAULT_FOV_EL_MIN_DEG
    ax_ae.add_patch(Rectangle(
        (DEFAULT_FOV_AZ_MIN_DEG, DEFAULT_FOV_EL_MIN_DEG), fov_w, fov_h,
        fill=False, edgecolor='#d62728', lw=1.6, ls='--', label='camera FOV'))

    # Full line-of-sight track (faint) + animated trail and current marker.
    ax_ae.plot(az_deg, el_deg, '-', color='#cccccc', lw=0.8, alpha=0.7,
               label='LOS (full)')
    (ln_ae_trail,) = ax_ae.plot([], [], '-', color='#ff7f0e', lw=1.4,
                                label='LOS (so far)')
    (mk_ae_now,) = ax_ae.plot([], [], 'o', color='#d62728', ms=7, mec='black',
                              mew=0.8, label='intruder now')

    # Axis limits: encompass both the FOV box and the LOS track, padded.
    finite = np.isfinite(az_deg) & np.isfinite(el_deg)
    az_lo = min(DEFAULT_FOV_AZ_MIN_DEG,
                float(np.min(az_deg[finite])) if np.any(finite) else 0.0)
    az_hi = max(DEFAULT_FOV_AZ_MAX_DEG,
                float(np.max(az_deg[finite])) if np.any(finite) else 0.0)
    el_lo = min(DEFAULT_FOV_EL_MIN_DEG,
                float(np.min(el_deg[finite])) if np.any(finite) else 0.0)
    el_hi = max(DEFAULT_FOV_EL_MAX_DEG,
                float(np.max(el_deg[finite])) if np.any(finite) else 0.0)
    az_pad = max(5.0, 0.05 * (az_hi - az_lo))
    el_pad = max(5.0, 0.05 * (el_hi - el_lo))
    ax_ae.set_xlim(az_lo - az_pad, az_hi + az_pad)
    ax_ae.set_ylim(el_lo - el_pad, el_hi + el_pad)
    ax_ae.legend(loc='upper right', fontsize=7)

    # ---- Right panel: active route transform (route_xf) ----
    T = len(result.times)
    t = result.times - result.times[0]

    # ---- Top-right (left half): ownship + intruder speed ----
    # Ownship speed = |own_vel|; the intruder carries no velocity state,
    # so its real / estimated speeds are finite-differenced from the
    # recorded true / estimated NED position tracks over the time grid.
    # All three are drawn as trails growing to the current step.
    own_speed = np.linalg.norm(result.own_vel, axis=1)
    if T > 1:
        int_true_speed = np.linalg.norm(
            np.gradient(result.intr_true_pos, t, axis=0), axis=1)
        int_est_speed = np.linalg.norm(
            np.gradient(result.intr_est_pos, t, axis=0), axis=1)
    else:
        int_true_speed = np.zeros(T)
        int_est_speed = np.zeros(T)
    ax_va.set_title('Ownship / intruder speed')
    ax_va.set_xlabel('Time (s)')
    ax_va.set_ylabel('speed (m/s)')
    ax_va.grid(True, alpha=0.3)
    ax_va.plot(t, own_speed, color='#1f77b4', lw=0.8, alpha=0.4)
    ax_va.plot(t, int_true_speed, color='#d62728', lw=0.8, alpha=0.4)
    ax_va.plot(t, int_est_speed, color='#ff7f0e', lw=0.8, alpha=0.4, ls='--')
    (ln_speed,) = ax_va.plot([], [], color='#1f77b4', lw=1.6,
                             label='ownship')
    (ln_int_true_spd,) = ax_va.plot([], [], color='#d62728', lw=1.6,
                                    label='intruder (true)')
    (ln_int_est_spd,) = ax_va.plot([], [], color='#ff7f0e', lw=1.6, ls='--',
                                   label='intruder (est.)')

    mk_now_va = ax_va.axvline(0.0, color='k', ls=':', lw=0.8)

    ax_va.set_xlim(t.min(), t.max() if t.max() > t.min() else t.min() + 1.0)
    smax_v = float(np.nanmax(np.concatenate([
        own_speed, int_true_speed, int_est_speed])))
    if not np.isfinite(smax_v) or smax_v <= 0.0:
        smax_v = 1.0
    ax_va.set_ylim(0.0, smax_v * 1.1)
    ax_va.legend(loc='upper right', fontsize=7)

    # ---- Right panel (row 1): FOV / UKF track state + uncertainty ----
    # A single timeline combining the estimator lifecycle (background
    # shading: intruder in the camera FOV, track bootstrapped/warming up,
    # track active) with the 1-sigma magnitude of the position / velocity
    # / acceleration uncertainty.  position σ (m) is on the left
    # axis; velocity sigma (m/s) and acceleration sigma (m/s^2) share
    # the twin right axis (both are rate uncertainties of comparable
    # scale).  All sigma lines are NaN on steps without an active track,
    # so they show gaps rather than fabricated values.
    in_fov_s      = np.asarray(getattr(result, 'in_fov',
                                       np.zeros(T, bool)), dtype=bool)
    est_started_s = np.asarray(getattr(result, 'est_started',
                                       np.zeros(T, bool)), dtype=bool)
    tracking_s    = np.asarray(getattr(result, 'tracking',
                                       np.zeros(T, bool)), dtype=bool)

    est_P_s = np.asarray(getattr(result, 'intr_est_P',
                                 np.empty((0, 3, 3))), dtype=np.float64)
    vel_var_s = np.asarray(getattr(result, 'intr_est_vel_var',
                                   np.empty((0, 3))), dtype=np.float64)
    acc_var_s = np.asarray(getattr(result, 'intr_est_acc_var',
                                   np.empty((0, 3))), dtype=np.float64)
    if est_P_s.ndim == 3 and est_P_s.shape[0] == T:
        pos_sigma_mag = np.sqrt(np.sum(np.einsum('tii->ti', est_P_s), axis=1))
    else:
        pos_sigma_mag = np.full(T, np.nan)
    vel_sigma_mag = (np.sqrt(np.sum(vel_var_s, axis=1))
                     if vel_var_s.shape == (T, 3) else np.full(T, np.nan))
    acc_sigma_mag = (np.sqrt(np.sum(acc_var_s, axis=1))
                     if acc_var_s.shape == (T, 3) else np.full(T, np.nan))

    ax_trk.set_ylabel('position σ (m)')
    ax_trk.set_title('FOV / UKF track state and 1σ uncertainty')
    ax_trk.grid(True, alpha=0.3)

    # Background state bands (drawn once over the full run).
    if np.any(in_fov_s):
        ax_trk.fill_between(t, 0.0, 1.0, where=in_fov_s, step='pre',
                            transform=ax_trk.get_xaxis_transform(),
                            color='#aec7e8', alpha=0.25, label='in FOV')
    warming = est_started_s & ~tracking_s
    if np.any(warming):
        ax_trk.fill_between(t, 0.0, 1.0, where=warming, step='pre',
                            transform=ax_trk.get_xaxis_transform(),
                            color='#ffbb78', alpha=0.35,
                            label='track warming up')
    if np.any(tracking_s):
        ax_trk.fill_between(t, 0.0, 1.0, where=tracking_s, step='pre',
                            transform=ax_trk.get_xaxis_transform(),
                            color='#98df8a', alpha=0.35, label='track active')

    # Position σ on the left axis; velocity / acceleration σ on the twin.
    ax_trk.plot(t, pos_sigma_mag, color='#1f77b4', lw=0.8, alpha=0.4)
    (ln_pos_sig,) = ax_trk.plot([], [], color='#1f77b4', lw=1.6,
                                label='position σ')

    ax_trk_r = ax_trk.twinx()
    ax_trk_r.set_ylabel('velocity σ (m/s) / accel σ (m/s²)')
    ax_trk_r.plot(t, vel_sigma_mag, color='#ff7f0e', lw=0.8, alpha=0.4,
                  ls='--')
    ax_trk_r.plot(t, acc_sigma_mag, color='#2ca02c', lw=0.8, alpha=0.4,
                  ls=':')
    (ln_vel_sig,) = ax_trk_r.plot([], [], color='#ff7f0e', lw=1.6, ls='--',
                                  label='velocity σ')
    (ln_acc_sig,) = ax_trk_r.plot([], [], color='#2ca02c', lw=1.6, ls=':',
                                  label='accel σ')

    mk_now_trk = ax_trk.axvline(0.0, color='k', ls=':', lw=0.8)

    ax_trk.set_xlim(t.min(), t.max() if t.max() > t.min() else t.min() + 1.0)
    pmax = (float(np.nanmax(pos_sigma_mag))
            if np.any(np.isfinite(pos_sigma_mag)) else 0.0)
    if not np.isfinite(pmax) or pmax <= 0.0:
        pmax = 1.0
    ax_trk.set_ylim(0.0, pmax * 1.1)
    rvals = np.concatenate([vel_sigma_mag, acc_sigma_mag])
    rmax = float(np.nanmax(rvals)) if np.any(np.isfinite(rvals)) else 0.0
    if not np.isfinite(rmax) or rmax <= 0.0:
        rmax = 1.0
    ax_trk_r.set_ylim(0.0, rmax * 1.1)

    h1, l1 = ax_trk.get_legend_handles_labels()
    h2, l2 = ax_trk_r.get_legend_handles_labels()
    ax_trk.legend(h1 + h2, l1 + l2, loc='upper right', fontsize=7)

    ax_d.set_xlabel('Time (s)')
    ax_d.grid(True, alpha=0.3)
    ax_d.axhline(0.0, color='#999999', lw=0.8)

    # route_xf series (visualiser-only): [shift_n, shift_e, shift_d,
    # speed_scale, mode, vel_n, vel_e, vel_d].  The velocity columns are
    # NaN except while the transform holds a constant velocity.  Empty
    # when history was not recorded.
    rxf = np.asarray(getattr(result, 'route_xf', np.empty((0, 8))),
                     dtype=np.float64)
    has_xf = rxf.size > 0
    if has_xf:
        shift_n, shift_e, shift_d = rxf[:, 0], rxf[:, 1], rxf[:, 2]
        speed_scale_s = rxf[:, 3]
        mode_s     = rxf[:, 4]
        vel_n, vel_e, vel_d = rxf[:, 5], rxf[:, 6], rxf[:, 7]
    else:
        shift_n = shift_e = shift_d = np.zeros(T)
        speed_scale_s = np.ones(T)
        mode_s     = np.zeros(T)
        vel_n = vel_e = vel_d = np.full(T, np.nan)

    # The route transform stores the segment target-speed scale directly,
    # so it *is* the commanded velocity scale (a slow-down is < 1, a
    # speed-up > 1).  Display it as-is so the panel reads in the same
    # units as the guidance command.
    vel_scale_s = np.where(np.isfinite(speed_scale_s), speed_scale_s, 1.0)

    # The constant-bearing family flies a held velocity vector rather than
    # a shifted route, so its meaningful per-step quantity is the
    # *direction* of that vector, not a shift in metres.  Show the maneuver
    # azimuth / elevation (deg) on the left axis for that family; every
    # other family keeps the shift-in-metres representation.
    angle_mode = (getattr(result, 'maneuver_family', '')
                  == MANEUVER_FAMILY_MIN_CONST_BEARING)

    # Shade the spans where the transform holds a constant velocity, so it
    # is visible at a glance when the ownship is holding its velocity
    # rather than tracking the (shifted) route.
    hold_mask = mode_s >= 0.5      # HOLD_VELOCITY == 1
    _hold_label = ('maneuver (hold velocity)' if angle_mode
                   else 'maintain (hold velocity)')
    if np.any(hold_mask):
        ax_d.fill_between(t, 0.0, 1.0, where=hold_mask, step='pre',
                          transform=ax_d.get_xaxis_transform(),
                          color='#ffcc66', alpha=0.25, label=_hold_label)

    mk_now = ax_d.axvline(0.0, color='k', ls=':', lw=0.8)

    if angle_mode:
        # Azimuth (course) and elevation (flight-path) of the held
        # maneuver velocity.  NaN on steps without a held velocity so the
        # trace shows gaps rather than fabricated angles.
        vh = np.hypot(vel_n, vel_e)
        az_deg = np.degrees(np.arctan2(vel_e, vel_n))
        el_deg = np.degrees(np.arctan2(-vel_d, vh))

        ax_d.set_ylabel('maneuver angle (deg)')
        ax_d.set_title('Active maneuver azimuth / elevation over time')

        (ln_az,) = ax_d.plot([], [], color='#1f77b4', lw=1.6,
                             label='azimuth')
        (ln_el,) = ax_d.plot([], [], color='#2ca02c', lw=1.6,
                             label='elevation')

        # Faint "ghost" traces of the full simulation.
        ax_d.plot(t, az_deg, color='#1f77b4', lw=0.8, alpha=0.4)
        ax_d.plot(t, el_deg, color='#2ca02c', lw=0.8, alpha=0.4)

        ax_d.set_xlim(t.min(),
                      t.max() if t.max() > t.min() else t.min() + 1.0)
        _ang = np.concatenate([az_deg, el_deg])
        _ang = _ang[np.isfinite(_ang)]
        if _ang.size:
            a_lo, a_hi = float(np.min(_ang)), float(np.max(_ang))
            a_pad = max(5.0, 0.1 * (a_hi - a_lo))
            ax_d.set_ylim(a_lo - a_pad, a_hi + a_pad)
        else:
            ax_d.set_ylim(-180.0, 180.0)

        h1, l1 = ax_d.get_legend_handles_labels()
        ax_d.legend(h1, l1, loc='upper right', fontsize=8)

        # Unused in angle mode; kept so the shared update path can guard.
        ln_sn = ln_se = ln_sd = ln_dt = None
        xf_lines = (ln_az, ln_el)
    else:
        ax_d.set_ylabel('shift (m)')
        ax_d.set_title('Active route transform (route_xf) over time')
        # Unused in shift mode.
        az_deg = el_deg = np.full(T, np.nan)
        ln_az = ln_el = None

        (ln_sn,) = ax_d.plot([], [], color='#1f77b4', lw=1.6, label='shift N')
        (ln_se,) = ax_d.plot([], [], color='#ff7f0e', lw=1.6, label='shift E')
        (ln_sd,) = ax_d.plot([], [], color='#2ca02c', lw=1.6, label='shift D')

        # Faint "ghost" traces of the full simulation (matching the other
        # 2D panels): the animated trails above grow over these.
        ax_d.plot(t, shift_n, color='#1f77b4', lw=0.8, alpha=0.4)
        ax_d.plot(t, shift_e, color='#ff7f0e', lw=0.8, alpha=0.4)
        ax_d.plot(t, shift_d, color='#2ca02c', lw=0.8, alpha=0.4)

        # velocity_scale lives on a twin axis (dimensionless, ~0.5..1) so
        # it is not crushed by the foot-scale shift axis.
        ax_dt = ax_d.twinx()
        ax_dt.set_ylabel('velocity scale')
        (ln_dt,) = ax_dt.plot([], [], color='#9467bd', lw=1.6, ls='--',
                              label='velocity scale')
        ax_dt.plot(t, vel_scale_s, color='#9467bd', lw=0.8, alpha=0.4,
                   ls='--')

        # y-limits: pad the shift range symmetrically around zero;
        # velocity scale is bounded above by ~1.
        smax = (float(np.nanmax(np.abs(
                    np.concatenate([shift_n, shift_e, shift_d]))))
                if has_xf else 1.0)
        if not np.isfinite(smax) or smax <= 0.0:
            smax = 1.0
        ax_d.set_xlim(t.min(),
                      t.max() if t.max() > t.min() else t.min() + 1.0)
        ax_d.set_ylim(-smax * 1.1, smax * 1.1)
        vmax = float(np.nanmax(vel_scale_s)) if has_xf else 1.0
        if not np.isfinite(vmax):
            vmax = 1.0
        ax_dt.set_ylim(0.0, max(1.5, vmax * 1.1))

        # One combined legend covering both the shift axis and the twin
        # dt-scale axis (plus the maintain-mode shading, if present).
        h1, l1 = ax_d.get_legend_handles_labels()
        h2, l2 = ax_dt.get_legend_handles_labels()
        ax_d.legend(h1 + h2, l1 + l2, loc='upper right', fontsize=8)
        xf_lines = (ln_sn, ln_se, ln_sd, ln_dt)

    txt_d = ax_d.text(0.02, 0.02, '', transform=ax_d.transAxes,
                      fontsize=10, family='monospace',
                      bbox=dict(facecolor='white', alpha=0.75, edgecolor='none'))

    # ---- Counterfactual: cylinder-distance vs ground truth ----
    t_full = result.cf_times - result.times[0]
    lowc_nm_mask = result.cyldist_no_maneuver < 1.0
    # Shade LoWC regions for the no-maneuver counterfactual.
    if np.any(lowc_nm_mask):
        ax_sep.fill_between(t_full, 0.0, 1.0, where=lowc_nm_mask,
                            transform=ax_sep.get_xaxis_transform(),
                            color='red', alpha=0.15,
                            label='LoWC (no maneuver)')
    ax_sep.plot(t_full, result.cyldist_no_maneuver,
                color='#888888', ls='--', lw=1.4,
                label=f'no maneuver (min={result.cyldist_min_no_maneuver:.2f})')
    (ln_sep_m,) = ax_sep.plot([], [], color='#1f77b4', lw=1.8,
                              label=f'flown (min={result.cyldist_min_maneuver:.2f})')
    ax_sep.axhline(1.0, color='red', ls=':', lw=1.0,
                   label='LoWC threshold (= 1)')
    ax_sep.set_xlabel('Time (s)')
    ax_sep.set_ylabel('true cylinder distance (norm.)')
    ax_sep.set_title('Ground-truth cylinder distance: maneuver vs counterfactual')
    ax_sep.grid(True, alpha=0.3)
    cyl_ymax = float(max(
        result.cyldist_no_maneuver.max(),
        result.cyldist_maneuver.max() if result.cyldist_maneuver.size else 0.0))
    ax_sep.set_xlim(t_full.min(), t_full.max())
    ax_sep.set_ylim(0.0, max(1.5, cyl_ymax * 1.05))
    ax_sep.legend(loc='upper right', fontsize=7)
    mk_now_sep = ax_sep.axvline(0.0, color='k', ls=':', lw=0.8)

    # ---- Top banner: classification + min separations ----
    cls = result.classification
    cls_colors = {'TP': '#2ca02c', 'FP': '#ff7f0e',
                  'TN': '#1f77b4',
                  'FN_M': '#d62728', 'FN_NM': '#d62728'}
    cls_text = {
        'TP': 'TP — real conflict averted',
        'FP': 'FP — nuisance alert (no LoWC without maneuver)',
        'TN': 'TN — no conflict, no maneuver',
        'FN_M': 'FN — LoWC NOT prevented (maneuvered)',
        'FN_NM': 'FN — LoWC NOT prevented (no maneuver)',
    }
    fig.text(0.72, 0.965,
             f"{cls_text.get(cls, cls)}   |   "
             f"min cyldist no-man = {result.cyldist_min_no_maneuver:.2f}   "
             f"min cyldist flown = {result.cyldist_min_maneuver:.2f}",
             ha='center', va='top', fontsize=11, fontweight='bold',
             color=cls_colors.get(cls, 'black'),
             bbox=dict(facecolor='white', alpha=0.85,
                       edgecolor=cls_colors.get(cls, 'black')))

    frames = list(range(0, T, max(1, stride)))
    if frames[-1] != T - 1:
        frames.append(T - 1)

    cyl_radius = result.cyl_d * 0.5

    def _remove_surfaces():
        for k in ('cyl', 'cyl_wf', 'ell'):
            if surfaces[k] is not None:
                try:
                    surfaces[k].remove()
                except Exception:
                    pass
                surfaces[k] = None
        while lookahead_surfaces:
            art = lookahead_surfaces.pop()
            try:
                art.remove()
            except Exception:
                pass

    def init():
        for ln in (ln_own_true, ln_int_true, ln_int_est,
                   ln_int_pred, *cand_lines, *pred_markers):
            ln.set_data([], [])
            ln.set_3d_properties([])
        for ln in xf_lines:
            ln.set_data([], [])
        for ln in (ln_pos_sig, ln_vel_sig, ln_acc_sig):
            ln.set_data([], [])
        ln_speed.set_data([], [])
        ln_int_true_spd.set_data([], [])
        ln_int_est_spd.set_data([], [])
        ln_ae_trail.set_data([], [])
        mk_ae_now.set_data([], [])
        mk_safe_point.set_data([], [])
        mk_safe_point.set_3d_properties([])
        banner.set_text('')
        txt_d.set_text('')
        time_box.set_text('')
        return ()

    def update(i):
        # Past 3D trails
        ln_own_true.set_data(own_neu[:i + 1, 0], own_neu[:i + 1, 1])
        ln_own_true.set_3d_properties(own_neu[:i + 1, 2])
        ln_int_true.set_data(intr_neu[:i + 1, 0], intr_neu[:i + 1, 1])
        ln_int_true.set_3d_properties(intr_neu[:i + 1, 2])
        ln_int_est.set_data(est_neu[:i + 1, 0], est_neu[:i + 1, 1])
        ln_int_est.set_3d_properties(est_neu[:i + 1, 2])

        # Current markers
        mk_own.set_data([own_neu[i, 0]], [own_neu[i, 1]])
        mk_own.set_3d_properties([own_neu[i, 2]])
        mk_int.set_data([intr_neu[i, 0]], [intr_neu[i, 1]])
        mk_int.set_3d_properties([intr_neu[i, 2]])

        # Tracker projection of the ownship onto the route.
        tp_neu = _to_neu(result.track_point[i])
        mk_track.set_data([tp_neu[0]], [tp_neu[1]])
        mk_track.set_3d_properties([tp_neu[2]])

        # Predicted CPA markers (route candidate's idx_cpa at this step).
        cpa_own_neu = _to_neu(result.cpa_own_pos[i])
        cpa_int_neu = _to_neu(result.cpa_intr_pos[i])
        mk_own_cpa.set_data([cpa_own_neu[0]], [cpa_own_neu[1]])
        mk_own_cpa.set_3d_properties([cpa_own_neu[2]])
        mk_int_cpa.set_data([cpa_int_neu[0]], [cpa_int_neu[1]])
        mk_int_cpa.set_3d_properties([cpa_int_neu[2]])
        ln_cpa_sep.set_data([cpa_own_neu[0], cpa_int_neu[0]],
                            [cpa_own_neu[1], cpa_int_neu[1]])
        ln_cpa_sep.set_3d_properties([cpa_own_neu[2], cpa_int_neu[2]])

        # FOV-loss safe point — shown only on steps where the gate is
        # active (intruder out of view, point not yet crossed).
        sp = result.safe_point_series
        if (sp is not None and sp.shape[0] > i
                and np.all(np.isfinite(sp[i]))):
            sp_neu = _to_neu(sp[i])
            mk_safe_point.set_data([sp_neu[0]], [sp_neu[1]])
            mk_safe_point.set_3d_properties([sp_neu[2]])
        else:
            mk_safe_point.set_data([], [])
            mk_safe_point.set_3d_properties([])

        # Extrapolated candidate lines.  The intermediate alternative
        # candidates (0 < k < K-1) are a snapshot taken at the last
        # decision point (fixed in place), so a slot is NaN until the
        # first evaluation — skip those.  Slot 0 is the currently-flown
        # trajectory and slot K-1 is the return-to-route candidate; both
        # are recomputed live each step, so they are drawn from
        # ``flown_lookahead`` / ``return_lookahead``.
        flown_la = getattr(result, 'flown_lookahead', None)
        return_la = getattr(result, 'return_lookahead', None)
        for k, ln in enumerate(cand_lines):
            if k == 0 and flown_la:
                arr = flown_la[i]
            elif k == K - 1 and return_la:
                arr = return_la[i]
            else:
                arr = result.cand_positions[i][k]
            if not np.all(np.isfinite(arr)):
                ln.set_data([], [])
                ln.set_3d_properties([])
                continue
            neu = _to_neu(arr)
            ln.set_data(neu[:, 0], neu[:, 1])
            ln.set_3d_properties(neu[:, 2])

        # Refresh 3D surfaces
        _remove_surfaces()
        cx_own = (own_neu[i, 0], own_neu[i, 1], own_neu[i, 2])
        Xc, Yc, Zc = _cylinder_mesh(cx_own, cyl_radius, result.cyl_h)
        surfaces['cyl'] = ax3d.plot_surface(
            Xc, Yc, Zc, color='#1f77b4', alpha=0.10, linewidth=0, shade=False)
        surfaces['cyl_wf'] = ax3d.plot_wireframe(
            Xc, Yc, Zc, color='#1f77b4', alpha=0.45,
            linewidth=0.6, rcount=2, ccount=12)

        # Protection cylinder at the lookahead endpoint of each candidate.
        # Slot 0 uses the live currently-flown trajectory and slot K-1 the
        # live return-to-route candidate; the remaining candidates use the
        # (carried) decision-point snapshot.
        for k in range(K):
            if k == 0 and flown_la:
                arr = flown_la[i]
            elif k == K - 1 and return_la:
                arr = return_la[i]
            else:
                arr = result.cand_positions[i][k]
            end_ned = arr[-1]
            if not np.all(np.isfinite(end_ned)):
                continue
            cx_end = (end_ned[1], end_ned[0], -end_ned[2])
            Xe2, Ye2, Ze2 = _cylinder_mesh(cx_end, cyl_radius, result.cyl_h)
            wf = ax3d.plot_wireframe(
                Xe2, Ye2, Ze2, color=cand_colors[k], alpha=0.55,
                linewidth=0.7, rcount=2, ccount=12)
            lookahead_surfaces.append(wf)

        cx_int = (est_neu[i, 0], est_neu[i, 1], est_neu[i, 2])
        P0 = result.intr_est_P[i]
        # When the camera could not see the intruder this step the
        # estimate (and its covariance) is recorded as NaN; skip the
        # uncertainty ellipsoid / cylinder so ``eigh`` is never handed a
        # non-finite matrix (which raises "Eigenvalues did not
        # converge").
        have_est = bool(np.all(np.isfinite(cx_int)) and np.all(np.isfinite(P0)))
        if have_est:
            Xe, Ye, Ze = _ellipsoid_mesh(cx_int, P0, n_sigma=n_sigma)
            surfaces['ell'] = ax3d.plot_surface(
                Xe, Ye, Ze, color='cyan', alpha=0.30, linewidth=0,
                edgecolor='none', shade=True)

            # Current-step uncertainty cylinder (t+0), matching the
            # t+15/30/45/60 styling.
            radial_std0 = float(np.sqrt(max(0.5 * (P0[0, 0] + P0[1, 1]), 0.0)))
            down_std0   = float(np.sqrt(max(P0[2, 2], 0.0)))
            r0 = n_sigma * radial_std0
            h0 = n_sigma * 2.0 * down_std0
            if r0 > 0.0 and h0 > 0.0:
                X0, Y0, Z0 = _cylinder_mesh(cx_int, r0, h0)
                wf0 = ax3d.plot_wireframe(
                    X0, Y0, Z0, color='cyan', alpha=0.55,
                    linewidth=0.7, rcount=2, ccount=12)
                lookahead_surfaces.append(wf0)

        # Predicted-intruder polyline + per-horizon uncertainty cylinders
        line_e = [est_neu[i, 0]]
        line_n = [est_neu[i, 1]]
        line_u = [est_neu[i, 2]]
        # Per-step sweep grid (variable length) — pick the sample
        # closest to each fixed lookahead horizon for this step.
        taus_i = result.sweep_taus[i]
        lookahead_idx = [int(np.argmin(np.abs(taus_i - h)))
                         for h in LOOKAHEAD_HORIZONS_S]
        for k_idx, (s_idx, color, mk) in enumerate(
                zip(lookahead_idx, LOOKAHEAD_COLORS, pred_markers)):
            pred_ned = result.int_pred_pos[i][s_idx]
            pred_P   = result.int_pred_P[i][s_idx]
            pe, pn, pu = pred_ned[1], pred_ned[0], -pred_ned[2]
            line_e.append(pe); line_n.append(pn); line_u.append(pu)
            mk.set_data([pe], [pn]); mk.set_3d_properties([pu])

            # pred_P is the packed position covariance [Pnn, Pne, Pee, Pdd];
            # the display cylinder uses an isotropic horizontal radius.
            radial_std = float(np.sqrt(
                max(0.5 * (pred_P[0] + pred_P[2]), 0.0)))
            down_std   = float(np.sqrt(max(pred_P[3], 0.0)))
            r = n_sigma * radial_std
            h = n_sigma * 2.0 * down_std
            if r > 0.0 and h > 0.0:
                Xl, Yl, Zl = _cylinder_mesh((pe, pn, pu), r, h)
                wf = ax3d.plot_wireframe(
                    Xl, Yl, Zl, color=color, alpha=0.55,
                    linewidth=0.7, rcount=2, ccount=12)
                lookahead_surfaces.append(wf)
        ln_int_pred.set_data(line_e, line_n)
        ln_int_pred.set_3d_properties(line_u)

        # Banners
        msg = []
        if result.alert[i]:
            msg.append(f'⚠  COLLISION ALERT ({result.candidate_names[0]})')
        if result.in_maneuver[i]:
            cur = int(result.flown_idx[i])
            if cur >= 0:
                msg.append(f'AVOIDING — {result.candidate_names[cur]}')
        # Append the case tag once the encounter has been classified
        # (i.e. from the first-alert step onward).
        if msg and result.encounter is not None:
            ec_ = result.encounter
            row = 'give way' if ec_.own_gives_way else 'hold'
            msg.append(f'[Case {ec_.case_id}: {ec_.geometry}, ownship {row}]')
        banner.set_text('   '.join(msg))
        banner.set_color('crimson' if msg else 'black')

        # Simulation-time read-out for this frame.
        time_box.set_text(f't = {t[i]:7.2f} s   (frame {i + 1}/{T})')

        # Intruder azimuth / elevation trail (ownship body frame).
        ln_ae_trail.set_data(az_deg[:i + 1], el_deg[:i + 1])
        if np.isfinite(az_deg[i]) and np.isfinite(el_deg[i]):
            mk_ae_now.set_data([az_deg[i]], [el_deg[i]])
        else:
            mk_ae_now.set_data([], [])

        # Ownship / intruder speed trails.
        ln_speed.set_data(t[:i + 1], own_speed[:i + 1])
        ln_int_true_spd.set_data(t[:i + 1], int_true_speed[:i + 1])
        ln_int_est_spd.set_data(t[:i + 1], int_est_speed[:i + 1])
        mk_now_va.set_xdata([t[i], t[i]])

        # FOV / UKF track-state + uncertainty trails.
        ln_pos_sig.set_data(t[:i + 1], pos_sigma_mag[:i + 1])
        ln_vel_sig.set_data(t[:i + 1], vel_sigma_mag[:i + 1])
        ln_acc_sig.set_data(t[:i + 1], acc_sigma_mag[:i + 1])
        mk_now_trk.set_xdata([t[i], t[i]])

        # Active maneuver transform traces.
        if angle_mode:
            ln_az.set_data(t[:i + 1], az_deg[:i + 1])
            ln_el.set_data(t[:i + 1], el_deg[:i + 1])
            mk_now.set_xdata([t[i], t[i]])
            mode_lbl = 'HOLD_VEL' if mode_s[i] >= 0.5 else 'TRACK_RTE'
            if np.isfinite(az_deg[i]):
                txt_d.set_text(
                    f't={t[i]:6.2f} s\n'
                    f' azimuth  = {az_deg[i]:8.1f}°\n'
                    f' elevation= {el_deg[i]:8.1f}°\n'
                    f' mode    = {mode_lbl}')
            else:
                txt_d.set_text(
                    f't={t[i]:6.2f} s\n'
                    f' (no held velocity)\n'
                    f' mode    = {mode_lbl}')
        else:
            ln_sn.set_data(t[:i + 1], shift_n[:i + 1])
            ln_se.set_data(t[:i + 1], shift_e[:i + 1])
            ln_sd.set_data(t[:i + 1], shift_d[:i + 1])
            ln_dt.set_data(t[:i + 1], vel_scale_s[:i + 1])
            mk_now.set_xdata([t[i], t[i]])
            mode_lbl = 'HOLD_VEL' if mode_s[i] >= 0.5 else 'TRACK_RTE'
            txt_d.set_text(
                f't={t[i]:6.2f} s\n'
                f' shift N = {shift_n[i]:8.1f} m\n'
                f' shift E = {shift_e[i]:8.1f} m\n'
                f' shift D = {shift_d[i]:8.1f} m\n'
                f' vel scale= {vel_scale_s[i]:8.3f}\n'
                f' mode    = {mode_lbl}')
        # Counterfactual panel — grow the flown cyl-distance curve and move cursor.
        ln_sep_m.set_data(t[:i + 1], result.cyldist_maneuver[:i + 1])
        mk_now_sep.set_xdata([t[i], t[i]])
        return ()

    # ------------------------------------------------------------------
    # Transport controls: a frame slider + play/pause and single-step
    # buttons.  The animation is driven from a shared mutable cursor
    # (``ctrl``) so the slider, the step buttons and the auto-play all
    # manipulate the same frame index.  ``render(idx)`` is the single
    # entry point that draws frame ``idx`` and keeps the slider in sync.
    # ------------------------------------------------------------------
    n_frames = len(frames)
    ctrl = {'idx': 0, 'playing': save is None}

    # Widget axes live in the reserved bottom strip (figure coords).
    ax_slider = fig.add_axes([0.13, 0.055, 0.52, 0.03])
    ax_prev   = fig.add_axes([0.69, 0.045, 0.06, 0.045])
    ax_play   = fig.add_axes([0.76, 0.045, 0.08, 0.045])
    ax_next   = fig.add_axes([0.85, 0.045, 0.06, 0.045])

    slider = Slider(ax_slider, 'Frame', 0, max(n_frames - 1, 1),
                    valinit=0, valstep=1)
    btn_prev = Button(ax_prev, '< Prev')
    btn_play = Button(ax_play, 'Pause')
    btn_next = Button(ax_next, 'Next >')

    def render(idx):
        idx = int(np.clip(idx, 0, n_frames - 1))
        ctrl['idx'] = idx
        # Keep the slider thumb in step with auto-play without
        # re-triggering its ``on_changed`` callback.
        if abs(slider.val - idx) >= 0.5:
            slider.eventson = False
            slider.set_val(idx)
            slider.eventson = True
        update(frames[idx])
        fig.canvas.draw_idle()
        return ()

    def _frame_source():
        # First tick renders the current cursor; subsequent ticks
        # advance it only while playing, halting at the last frame.
        yield ctrl['idx']
        while True:
            if ctrl['playing'] and ctrl['idx'] < n_frames - 1:
                ctrl['idx'] += 1
            elif ctrl['playing']:
                # Reached the end — stop auto-play and update the label.
                ctrl['playing'] = False
                btn_play.label.set_text('Play')
            yield ctrl['idx']

    def _pause():
        ctrl['playing'] = False
        btn_play.label.set_text('Play')
        try:
            anim.event_source.stop()
        except Exception:
            pass

    def _play():
        # Restart from the beginning if we are sitting on the last frame.
        if ctrl['idx'] >= n_frames - 1:
            ctrl['idx'] = 0
        ctrl['playing'] = True
        btn_play.label.set_text('Pause')
        try:
            anim.event_source.start()
        except Exception:
            pass

    def _on_play(_event):
        if ctrl['playing']:
            _pause()
        else:
            _play()

    def _on_prev(_event):
        _pause()
        render(ctrl['idx'] - 1)

    def _on_next(_event):
        _pause()
        render(ctrl['idx'] + 1)

    def _on_slider(val):
        _pause()
        render(int(val))

    def _on_key(event):
        # Keyboard stepping mirrors the '< Prev' / 'Next >' buttons.
        if event.key in ('left', 'right'):
            _pause()
            render(ctrl['idx'] + (1 if event.key == 'right' else -1))

    btn_play.on_clicked(_on_play)
    btn_prev.on_clicked(_on_prev)
    btn_next.on_clicked(_on_next)
    slider.on_changed(_on_slider)
    fig.canvas.mpl_connect('key_press_event', _on_key)

    anim = FuncAnimation(fig, render, frames=_frame_source,
                         init_func=init, interval=interval_ms,
                         blit=False, repeat=False, save_count=n_frames)

    if save:
        anim.save(save, writer='ffmpeg', fps=max(1, int(1000 / interval_ms)))
        print(f"Saved animation to {save}")

    # NOTE: no ``tight_layout()`` here — this figure mixes a 3-D Axes with
    # the 2-D panels, and mplot3d Axes are not compatible with
    # tight_layout (it emits a UserWarning and can mangle the layout).
    # Stash the animation AND the widgets on the figure so they survive
    # garbage collection when this function returns (FuncAnimation only
    # keeps a weak ref to itself via the event source, and the widgets
    # would otherwise be collected, killing their callbacks — e.g. when
    # invoked from a Qt slot).
    fig._daa_anim = anim                                # noqa: SLF001
    fig._daa_widgets = (slider, btn_prev, btn_play, btn_next)   # noqa: SLF001
    plt.show()
    return anim


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description="Animate the avoidance simulation for a fixed encounter seed.")
    p.add_argument('--seed', type=int, default=100,
                   help='Master seed used to draw the encounter spec (default: 100)')
    p.add_argument('--lookahead', type=float, default=LOOKAHEAD_S)
    p.add_argument('--cyl-h', type=float, default=CYL_HEIGHT_M)
    p.add_argument('--cyl-d', type=float, default=CYL_DIAMETER_M)
    p.add_argument('--lateral-shift', type=float, default=LATERAL_SHIFT_RATIO,
                   help='Lateral escape sizing as a ratio of the '
                        'protection-cylinder radius (plus intruder '
                        'uncertainty) targeted at CPA (1.0 = grazes the '
                        'cylinder ideally; 1.5 keeps a 50%% margin).')
    p.add_argument('--k-xt', type=float, default=DEFAULT_K_XT_PER_M,
                   help='Cross-track line-attraction gain (1/m, = 1/look-ahead) '
                        'of the route guidance law (larger = sharper transition).')
    p.add_argument('--a-max-along',    type=float, default=DEFAULT_A_MAX_ALONG_M_S2,
                   help='Max along-track (speed-module) acceleration (m/s²) of the integrator.')
    p.add_argument('--rate-max-azimuth',   type=float,
                   default=DEFAULT_RATE_MAX_AZIMUTH_RAD_S,
                   help='Max course-angle (azimuth) rate (rad/s) of the integrator.')
    p.add_argument('--rate-max-elevation', type=float,
                   default=DEFAULT_RATE_MAX_ELEVATION_RAD_S,
                   help='Max flight-path-angle (elevation) rate (rad/s) of the integrator.')
    p.add_argument('--alert-threshold', type=float, default=ALERT_THRESHOLD)
    p.add_argument('--engage-hysteresis-s', type=float,
                   default=DEFAULT_HYSTERESIS_S,
                   help='Seconds the collision alert must persist '
                        'continuously before an avoidance maneuver is '
                        'committed (and the encounter is classified). '
                        '0 = act on the first alerting step. Default: 2 s.')
    p.add_argument('--return-hysteresis-s', type=float,
                   default=DEFAULT_RETURN_HYSTERESIS_S,
                   help='Seconds the return path must stay continuously '
                        'clear before the return-to-route maneuver '
                        'starts. 0 = return on the first clear step. '
                        'Default: 10 s.')
    p.add_argument('--closed-loop-mode',
                   choices=[CLOSED_LOOP_OPEN, CLOSED_LOOP_ON_CONFLICT,
                            CLOSED_LOOP_PERIODIC],
                   default=DEFAULT_CLOSED_LOOP_MODE,
                   help='Avoidance re-evaluation policy while flying a '
                        'maneuver. "open" = legacy single '
                        'maneuver. "on_conflict" = re-check and stack a '
                        'fresh escape on top of the active one whenever a '
                        'new conflict is confirmed. "periodic" (default) = '
                        're-rank the escape set every --periodic-interval '
                        'seconds and switch (stack) when the anti-flicker '
                        'margin is met.')
    p.add_argument('--periodic-interval', type=float, default=1.0,
                   help='Closed-loop "periodic" mode: seconds between '
                        'full escape-set re-evaluations (default: 1.0).')
    p.add_argument('--switch-improve-ratio', type=float,
                   default=DEFAULT_SWITCH_IMPROVE_RATIO,
                   help='Closed-loop "periodic" mode: minimum fractional '
                        'CPA-distance improvement a re-ranked escape must '
                        'show before the ownship switches to it '
                        '(default: 0.15).')
    p.add_argument('--stride', type=int, default=10,
                   help='Animation stride (1 = every step, default: 10)')
    p.add_argument('--interval-ms', type=int, default=60,
                   help='Animation frame interval in ms')
    p.add_argument('--save', type=str, default=None,
                   help='Optional path to save the animation as mp4')
    p.add_argument('--n-sigma', type=float, default=2.0,
                   help='Sigma scale for the intruder uncertainty ellipsoid (default: 2.0)')
    p.add_argument('--no-show', action='store_true',
                   help='Run the simulation without launching the GUI')
    args = p.parse_args()

    spec = make_spec_from_seed(args.seed)
    print(f"Running simulation with seed={args.seed}, spec={spec}")

    result = run_simulation_from_spec(
        spec,
        generators=default_generators(
            lateral_shift_ratio=args.lateral_shift,
        ),
        lookahead=args.lookahead,
        cyl_h=args.cyl_h,
        cyl_d=args.cyl_d,
        alert_threshold=args.alert_threshold,
        engage_hysteresis_s=args.engage_hysteresis_s,
        return_hysteresis_s=args.return_hysteresis_s,
        closed_loop_mode=args.closed_loop_mode,
        periodic_interval_s=args.periodic_interval,
        switch_improve_ratio=args.switch_improve_ratio,
        k_xt=args.k_xt,
        a_max_along=args.a_max_along,
        rate_max_azimuth=args.rate_max_azimuth,
        rate_max_elevation=args.rate_max_elevation,
    )

    print(f"  steps recorded: {len(result.times)}")
    if result.maneuver_idx >= 0:
        man_t = result.times[result.maneuver_start] - result.times[0]
        # ``committed_names`` lists every committed escape in order, one
        # entry per commit — so closed-loop re-stacks (which each compose
        # a fresh transform) are all shown, not collapsed.
        seq = result.committed_names
        if result.n_commits > 1:
            # Run-length encode the sequence for a compact label, e.g.
            # ``slow_down -> left_shift -> right_shift x4``.
            parts = []
            prev, run = None, 0
            for nm in seq:
                if nm == prev:
                    run += 1
                else:
                    if prev is not None:
                        parts.append(prev if run == 1 else f'{prev} x{run}')
                    prev, run = nm, 1
            if prev is not None:
                parts.append(prev if run == 1 else f'{prev} x{run}')
            print(f"  avoidance: {result.n_commits} maneuvers committed "
                  f"(first at t = {man_t:.2f} s)")
            print(f"    sequence: {' -> '.join(parts)}")
        else:
            print(f"  avoidance maneuver: {seq[0]} at t = {man_t:.2f} s")
    else:
        print("  no avoidance maneuver triggered")
    for k, name in enumerate(result.candidate_names):
        print(f"  min d_{name:<10s} = {result.d_candidates[:, k].min():.3f}")
    print(f"  classification = {result.classification}  "
          f"(LoWC no-man={result.lowc_no_maneuver}, flown={result.lowc_maneuver})")
    print(f"  min cyldist (no maneuver) = {result.cyldist_min_no_maneuver:.3f}")
    print(f"  min cyldist (flown)       = {result.cyldist_min_maneuver:.3f}")

    # Encounter classifications — one per committed maneuver shift (the
    # core re-classifies on every commit, including each closed-loop
    # re-stack); paired with the committed escape.
    encs = tuple(getattr(result, 'encounters', ()) or ())
    if encs:
        seq = result.committed_names
        print(f"  encounter classifications: {len(encs)}")
        for i, ec in enumerate(encs):
            nm = seq[i] if i < len(seq) else '—'
            verdict = 'gives way' if ec.own_gives_way else 'right-of-way'
            print(f"    [{i + 1}] {nm}: Case {ec.case_id} ({ec.geometry}) "
                  f"-> {ec.maneuver}  (ownship {verdict}; compliant: "
                  f"{','.join(ec.compliant_actions) or '—'})")

    if args.no_show and not args.save:
        return

    if args.no_show:
        matplotlib.use('Agg')
    animate(result,
            interval_ms=args.interval_ms,
            stride=args.stride,
            save=args.save,
            n_sigma=args.n_sigma,
            seed=args.seed)


if __name__ == '__main__':
    main()
