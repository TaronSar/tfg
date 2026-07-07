#!/usr/bin/env python3
"""
Shared ctypes loader for ``libDAA_dll__sil``.

The DAA SIL DLL is consumed by Python code in several sibling packages
(at least ``sw_conflict_resolution/scripts/candidate_trajectories`` and
``sw_conflict_resolution/scripts/avoidance_core``).  This module
centralises:

  * the platform-specific DLL filename,
  * the search-path policy (source tree, then frozen-bundle fallbacks),
  * a process-wide ``ctypes.CDLL`` singleton.

Each consumer is still responsible for declaring its own
``argtypes``/``restype`` on the returned handle; the ``Simulator``
class below binds the ``daa_sim_*`` slice of the C API.

Typical use::

    from daa_dll import Simulator
    sim = Simulator(dt=0.1, sim_dt_max=0.05, k_xt=0.001,
                    p0=p0, v0=v0, route_capacity=64,
                    a_max_along=..., rate_max_azimuth=...,
                    rate_max_elevation=...)
    sim.push_route(route_pdt)            # (N, 4) [N, E, D, speed]
    baseline = sim.simulate(n_out=600)   # never-maneuvered look-ahead
    sim.step()                           # advance the real flight by dt
"""

from __future__ import annotations

import ctypes
import os
import sys
from typing import Iterable, List, Optional


if sys.platform == "win32":
    DLL_NAME = "libDAA_dll__sil.dll"
    _BUILD_SUBDIR = os.path.join("build", "bin")
else:
    DLL_NAME = "libDAA_so__sil.so"
    _BUILD_SUBDIR = os.path.join("build", "DAA_so")


_LIB: Optional[ctypes.CDLL] = None


def _default_search_dirs() -> List[str]:
    """Default DLL search dirs.

    Order:
      1. ``sw_daa_SIL/code/project/build/bin`` (developer source tree),
      2. directory of *this* file (handy when somebody drops the DLL
         next to ``daa_dll.py``),
      3. PyInstaller ``_MEIPASS`` extraction root (frozen folder mode),
      4. directory of the executable (frozen one-file mode).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    # This file lives at ``sw_daa_SIL/scripts/daa_dll.py``;
    # the build output is at ``sw_daa_SIL/code/project/build/bin``.
    build_bin = os.path.normpath(os.path.join(
        here, "..", "code", "project", _BUILD_SUBDIR,
    ))
    dirs: List[str] = [build_bin, here]
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            dirs.append(meipass)
        dirs.append(os.path.dirname(sys.executable))
    return dirs


def load(extra_search_dirs: Iterable[str] = ()) -> ctypes.CDLL:
    """Locate and load the DAA DLL.

    ``extra_search_dirs`` are prepended (highest priority) to the
    default search list — useful for callers that know a custom
    location.  Raises ``FileNotFoundError`` with the full list of
    attempted paths when the DLL cannot be found.
    """
    dirs = list(extra_search_dirs) + _default_search_dirs()
    tried: List[str] = []
    for d in dirs:
        path = os.path.join(d, DLL_NAME)
        tried.append(path)
        if os.path.isfile(path):
            return ctypes.CDLL(path)
    raise FileNotFoundError(
        f"DAA DLL '{DLL_NAME}' not found. Tried:\n  - "
        + "\n  - ".join(tried)
        + "\nBuild it first with: ninja DAA_so__sil  (Linux)  or  ninja DAA_dll__sil  (Windows)"
    )


def get_lib() -> ctypes.CDLL:
    """Return a process-wide singleton ``CDLL`` handle (lazy)."""
    global _LIB
    if _LIB is None:
        _LIB = load()
    return _LIB


# ---------------------------------------------------------------------------
# Per-API signature binders (idempotent)
# ---------------------------------------------------------------------------
#
# Each ``bind_*`` declares ``restype``/``argtypes`` for one slice of the
# C API on the singleton ``CDLL`` handle and returns it.  Calls are
# idempotent thanks to the ``_BOUND`` set, so consumers can call them
# from a hot path without worrying about reassignment cost.

_BOUND: set = set()

# Common ctypes shortcuts.
_c_double   = ctypes.c_double
_c_int      = ctypes.c_int
_void_ptr   = ctypes.c_void_p
_double_ptr = ctypes.POINTER(ctypes.c_double)
_int_ptr    = ctypes.POINTER(ctypes.c_int)


def bind_simulator(lib: Optional[ctypes.CDLL] = None) -> ctypes.CDLL:
    """Declare argtypes for the ``daa_sim_*`` opaque-handle API."""
    lib = lib or get_lib()
    if 'simulator' in _BOUND:
        return lib
    # daa_sim_create(dt, sim_dt_max, k_xt, p0_ned, v0_ned, route_capacity,
    #     a_max_along, rate_max_azimuth, rate_max_elevation,
    #     v_max, v_min,
    #     el_min, el_max,
    #     lookahead, ukf_alpha, ukf_beta, ukf_kappa, cyl_h, cyl_d,
    #     ukf_model) -> handle
    lib.daa_sim_create.restype  = _void_ptr
    lib.daa_sim_create.argtypes = [
        _c_double, _c_double, _c_double,     # dt, sim_dt_max, k_xt
        _double_ptr, _double_ptr,            # p0_ned, v0_ned
        _c_int,                              # route_capacity
        _c_double, _c_double, _c_double,     # a_max along/lat/vert
        _c_double, _c_double,                # v_max, v_min
        _c_double, _c_double,                # el_min, el_max
        _c_double,                           # lookahead
        _c_double, _c_double, _c_double,     # ukf_alpha, ukf_beta, ukf_kappa
        _c_double, _c_double,                # cyl_h, cyl_d
        _c_int,                              # ukf_model
    ]
    # daa_sim_destroy(handle)
    lib.daa_sim_destroy.restype  = None
    lib.daa_sim_destroy.argtypes = [_void_ptr]
    # daa_sim_push_route(handle, pdt_n4, n) -> int (pushed count)
    lib.daa_sim_push_route.restype  = _c_int
    lib.daa_sim_push_route.argtypes = [_void_ptr, _double_ptr, _c_int]
    # daa_sim_set_route_xf(handle, mode, shift3, speed_scale, vel3,
    #                      track_p0, track_p1, track_speed) -> int
    lib.daa_sim_set_route_xf.restype  = _c_int
    lib.daa_sim_set_route_xf.argtypes = [
        _void_ptr, _c_int, _double_ptr, _c_double, _double_ptr,
        _double_ptr, _double_ptr, _c_double,
    ]
    # daa_sim_get_route_xf(handle, mode_out, shift3_out, speed_scale_out,
    #                      vel3_out, track_p0_out, track_p1_out,
    #                      track_speed_out) -> int
    #                      (any out pointer may be NULL)
    lib.daa_sim_get_route_xf.restype  = _c_int
    lib.daa_sim_get_route_xf.argtypes = [
        _void_ptr, _int_ptr, _double_ptr, _double_ptr, _double_ptr,
        _double_ptr, _double_ptr, _double_ptr,
    ]
    # daa_sim_get_position / get_velocity(handle, out3) -> int
    lib.daa_sim_get_position.restype  = _c_int
    lib.daa_sim_get_position.argtypes = [_void_ptr, _double_ptr]
    lib.daa_sim_get_velocity.restype  = _c_int
    lib.daa_sim_get_velocity.argtypes = [_void_ptr, _double_ptr]
    # daa_sim_step(handle, p_out_or_null, v_out_or_null,
    #              track_pt_out_or_null) -> int
    lib.daa_sim_step.restype  = _c_int
    lib.daa_sim_step.argtypes = [
        _void_ptr, _double_ptr, _double_ptr, _double_ptr,
    ]
    # daa_sim_simulate(handle, mode, shift3, speed_scale, vel3, track_p0,
    #                  track_p1, track_speed, traj_out, n_out) -> int
    lib.daa_sim_simulate.restype  = _c_int
    lib.daa_sim_simulate.argtypes = [
        _void_ptr, _c_int, _double_ptr, _c_double, _double_ptr,
        _double_ptr, _double_ptr, _c_double, _double_ptr, _c_int,
    ]
    # ---- embedded estimator UKF ----------------------------------
    # daa_sim_est_init_from_measurement(handle, z3, pos3, att3, cov36, dt, q,
    #                                   meas3, vvar, avar, vvar_vert, avar_vert,
    #                                   q_var_diag, q_n)
    lib.daa_sim_est_init_from_measurement.restype  = _c_int
    lib.daa_sim_est_init_from_measurement.argtypes = [
        _void_ptr, _double_ptr, _double_ptr, _double_ptr, _double_ptr,
        _c_double, _c_double, _double_ptr, _c_double, _c_double,
        _c_double, _c_double, _double_ptr, _c_int,
    ]
    # daa_sim_est_predict(handle)
    lib.daa_sim_est_predict.restype  = _c_int
    lib.daa_sim_est_predict.argtypes = [_void_ptr]
    # daa_sim_est_update(handle, z3, meas3, pos3, att3, cov36)
    lib.daa_sim_est_update.restype  = _c_int
    lib.daa_sim_est_update.argtypes = [
        _void_ptr, _double_ptr, _double_ptr, _double_ptr, _double_ptr,
        _double_ptr,
    ]
    # daa_sim_est_get_state(handle, state6_out, P36_out, accel_var3_out)
    lib.daa_sim_est_get_state.restype  = _c_int
    lib.daa_sim_est_get_state.argtypes = [
        _void_ptr, _double_ptr, _double_ptr, _double_ptr]
    # daa_sim_propagate_batch(handle, n)
    lib.daa_sim_propagate_batch.restype  = _c_int
    lib.daa_sim_propagate_batch.argtypes = [_void_ptr, _c_int]
    # daa_sim_capacity(handle) -> int
    lib.daa_sim_capacity.restype  = _c_int
    lib.daa_sim_capacity.argtypes = [_void_ptr]
    # daa_sim_propagation_pos / cov(handle) -> double*
    lib.daa_sim_propagation_pos.restype  = _double_ptr
    lib.daa_sim_propagation_pos.argtypes = [_void_ptr]
    lib.daa_sim_propagation_cov.restype  = _double_ptr
    lib.daa_sim_propagation_cov.argtypes = [_void_ptr]
    # daa_sim_simulate_and_score(handle, mode, shift3, speed_scale, vel3,
    #     track_p0, track_p1, track_speed, traj_out_or_null, n_out,
    #     idx_cpa_out) -> double.  Protection cylinder dims come from the
    #     simulator config (daa_sim_create).
    lib.daa_sim_simulate_and_score.restype  = _c_double
    lib.daa_sim_simulate_and_score.argtypes = [
        _void_ptr, _c_int, _double_ptr, _c_double, _double_ptr,
        _double_ptr, _double_ptr, _c_double, _double_ptr, _c_int,
        _int_ptr,
    ]
    _BOUND.add('simulator')
    return lib


# Sentinel "effectively unlimited" used as the default for the
# always-on velocity caps.  A large finite value (rather than +inf
# or 0) keeps the C side branch-free.
_V_UNLIMITED = 1.0E12

# Flight-path-angle bound for "effectively no limit": the elevation is
# physically confined to +/- pi/2, so +/- pi/2 is an unreachable bound.
_EL_UNLIMITED = 1.5707963267948966

# Embedded intruder estimator motion models (mirror DAA::Ukf_model in
# the C++ header).  Passed as the ``ukf_model`` argument to
# :meth:`Simulator.__init__`.
UKF_MODEL_CV  = 0   # Constant-velocity (6-state).
UKF_MODEL_CA  = 1   # Constant-acceleration, NED frame (9-state).
UKF_MODEL_CAB = 2   # Constant-acceleration, body frame (9-state).
UKF_MODEL_CTRA = 3  # Constant turn-rate + tangential accel, constant
                    # vertical speed (8-state).


class Simulator:
    """Pythonic wrapper around the ``daa_sim_*`` C API.

    Owns one ``Daa_simulator`` opaque handle which bundles:

    * a **route tracker** (the polyline waypoints still to be flown,
      uploaded once via :meth:`push_route`),
    * a **Virtual_ownship** (the current kinematic flight state),
    * the **active route transform** (an affine shift + dt-scale
      applied to the route on the fly, the identity until
      :meth:`set_route_xf`).

    Intended flow for a maneuvered encounter:

    1. :meth:`push_route` the full route once.
    2. :meth:`simulate` with the whole encounter length to obtain the
       never-maneuvered baseline trajectory.
    3. Per step, :meth:`step` advances the real flight by ``dt`` (and
       pops surpassed waypoints).  Evaluate candidate maneuvers with
       :meth:`simulate` passing a hypothetical ``shift`` / ``speed_scale``
       (these never mutate the tracker).
    4. **Commit** a maneuver by calling :meth:`set_route_xf`; keep
       stepping.  The return-to-route maneuver is just
       :meth:`simulate` with the inverse of the active transform.

    The handle is freed in :meth:`close` / ``__del__`` / context-manager
    exit.  Velocity-envelope semantics use the positive-down NED
    convention (see the C header).
    """

    __slots__ = ('_lib', '_h', '_dt', '_cap', '_pos_view', '_cov_view')

    def __init__(self,
                 dt: float,
                 sim_dt_max: float,
                 k_xt: float,
                 p0,
                 v0,
                 route_capacity: int,
                 a_max_along: float,
                 rate_max_azimuth: float,
                 rate_max_elevation: float,
                 v_max: float = _V_UNLIMITED,
                 v_min: float = 0.0,
                 el_min: float = -_EL_UNLIMITED,
                 el_max: float = _EL_UNLIMITED,
                 lookahead: float = 0.0,
                 ukf_alpha: float = 1.0E-3,
                 ukf_beta: float = 2.0,
                 ukf_kappa: Optional[float] = None,
                 cyl_h: float = 0.0,
                 cyl_d: float = 0.0,
                 ukf_model: int = UKF_MODEL_CV):
        import numpy as _np
        if ukf_kappa is None:
            ukf_kappa = 3.0 - 6.0
        self._lib = bind_simulator()
        self._h = None
        self._dt = float(dt)
        p0 = _np.ascontiguousarray(p0, dtype=_np.float64).reshape(3)
        v0 = _np.ascontiguousarray(v0, dtype=_np.float64).reshape(3)
        h = self._lib.daa_sim_create(
            _c_double(dt),
            _c_double(sim_dt_max),
            _c_double(k_xt),
            p0.ctypes.data_as(_double_ptr),
            v0.ctypes.data_as(_double_ptr),
            _c_int(int(route_capacity)),
            _c_double(a_max_along),
            _c_double(rate_max_azimuth),
            _c_double(rate_max_elevation),
            _c_double(v_max),
            _c_double(v_min),
            _c_double(el_min),
            _c_double(el_max),
            _c_double(lookahead),
            _c_double(ukf_alpha),
            _c_double(ukf_beta),
            _c_double(ukf_kappa),
            _c_double(cyl_h),
            _c_double(cyl_d),
            _c_int(int(ukf_model)),
        )
        if not h:
            raise RuntimeError("daa_sim_create failed")
        self._h = h
        # Capacity and zero-copy views over the simulator-owned
        # propagation buffers, built once.  They alias C++ memory and
        # stay valid until the handle is destroyed; every
        # :meth:`propagate` call overwrites them in place.
        self._cap = int(self._lib.daa_sim_capacity(h))
        pos_ptr = self._lib.daa_sim_propagation_pos(h)
        cov_ptr = self._lib.daa_sim_propagation_cov(h)
        self._pos_view = _np.ctypeslib.as_array(pos_ptr,
                                                shape=(self._cap, 3))
        self._cov_view = _np.ctypeslib.as_array(cov_ptr,
                                                shape=(self._cap, 4))

    @property
    def dt(self) -> float:
        """Real-flight step duration (s) configured at construction."""
        return self._dt

    # -- lifetime ------------------------------------------------------

    def close(self) -> None:
        """Destroy the underlying handle (idempotent)."""
        if getattr(self, '_h', None):
            self._lib.daa_sim_destroy(self._h)
            self._h = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self) -> "Simulator":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # -- route ---------------------------------------------------------

    def push_route(self, route_pdt) -> int:
        """Append waypoints to the route.

        ``route_pdt`` is an ``(N, 4)`` array of ``[N, E, D, speed]`` rows
        (NED m + per-segment target speed m/s).  The speed in row i is
        the speed the ownship shall have when flying *towards* waypoint
        i, so the first row's speed is unused.  Returns the number of
        waypoints actually pushed (< N if capacity is reached).
        """
        import numpy as _np
        arr = _np.ascontiguousarray(route_pdt, dtype=_np.float64).reshape(-1, 4)
        pushed = self._lib.daa_sim_push_route(
            self._h, arr.ctypes.data_as(_double_ptr), _c_int(int(arr.shape[0])))
        if pushed < 0:
            raise RuntimeError(f"daa_sim_push_route failed (rc={pushed})")
        return int(pushed)

    # -- active route transform ---------------------------------------

    def set_route_xf(self, shift, speed_scale: float = 1.0,
                     mode: int = 0, velocity=None,
                     track_p0=None, track_p1=None,
                     track_speed: float = 0.0) -> None:
        """Replace the active route transform.

        * ``mode`` 0 (track route) applies ``shift`` + ``speed_scale`` to
          the route; ``mode`` 1 (hold velocity) ignores the route and
          flies the constant NED ``velocity``; ``mode`` 2 (external
          track) ignores the route and flies the straight segment
          ``track_p0`` -> ``track_p1`` at the constant ``track_speed``
          (m/s).
        """
        import numpy as _np
        s = _np.ascontiguousarray(shift, dtype=_np.float64).reshape(3)
        if velocity is None:
            v = _np.zeros(3, dtype=_np.float64)
        else:
            v = _np.ascontiguousarray(velocity, dtype=_np.float64).reshape(3)
        p0 = (_np.zeros(3, dtype=_np.float64) if track_p0 is None
              else _np.ascontiguousarray(track_p0, dtype=_np.float64).reshape(3))
        p1 = (_np.zeros(3, dtype=_np.float64) if track_p1 is None
              else _np.ascontiguousarray(track_p1, dtype=_np.float64).reshape(3))
        rc = self._lib.daa_sim_set_route_xf(
            self._h, _c_int(int(mode)),
            s.ctypes.data_as(_double_ptr), _c_double(speed_scale),
            v.ctypes.data_as(_double_ptr),
            p0.ctypes.data_as(_double_ptr),
            p1.ctypes.data_as(_double_ptr),
            _c_double(track_speed))
        if rc != 0:
            raise RuntimeError(f"daa_sim_set_route_xf failed (rc={rc})")

    def get_route_xf(self):
        """Return the active route transform.

        Returns ``(shift(3,), speed_scale, mode, velocity(3,),
        track_p0(3,), track_p1(3,), track_speed)``.
        """
        import numpy as _np
        shift = _np.empty(3, dtype=_np.float64)
        velocity = _np.empty(3, dtype=_np.float64)
        track_p0 = _np.empty(3, dtype=_np.float64)
        track_p1 = _np.empty(3, dtype=_np.float64)
        speed_scale = _c_double(0.0)
        mode = _c_int(0)
        track_speed = _c_double(0.0)
        rc = self._lib.daa_sim_get_route_xf(
            self._h, ctypes.byref(mode),
            shift.ctypes.data_as(_double_ptr), ctypes.byref(speed_scale),
            velocity.ctypes.data_as(_double_ptr),
            track_p0.ctypes.data_as(_double_ptr),
            track_p1.ctypes.data_as(_double_ptr),
            ctypes.byref(track_speed))
        if rc != 0:
            raise RuntimeError(f"daa_sim_get_route_xf failed (rc={rc})")
        return (shift, float(speed_scale.value), int(mode.value), velocity,
                track_p0, track_p1, float(track_speed.value))

    # -- ownship state -------------------------------------------------

    def get_position(self, out=None):
        """Return the current ownship NED position ``(3,)``."""
        import numpy as _np
        if out is None:
            out = _np.empty(3, dtype=_np.float64)
        rc = self._lib.daa_sim_get_position(
            self._h, out.ctypes.data_as(_double_ptr))
        if rc != 0:
            raise RuntimeError(f"daa_sim_get_position failed (rc={rc})")
        return out

    def get_velocity(self, out=None):
        """Return the current ownship NED velocity ``(3,)``."""
        import numpy as _np
        if out is None:
            out = _np.empty(3, dtype=_np.float64)
        rc = self._lib.daa_sim_get_velocity(
            self._h, out.ctypes.data_as(_double_ptr))
        if rc != 0:
            raise RuntimeError(f"daa_sim_get_velocity failed (rc={rc})")
        return out

    # -- stepping ------------------------------------------------------

    def step(self, p_out=None, v_out=None, track_pt_out=None):
        """Advance the real flight by ``dt`` and pop surpassed waypoints.

        Returns the per-step quantities as a tuple
        ``(position(3,), velocity(3,), track_point(3,))`` where the
        track point is the foot of perpendicular of the new ownship
        position onto the active route segment.  Optional
        ``p_out`` / ``v_out`` / ``track_pt_out`` are pre-allocated
        ``(3,)`` C-contiguous float64 buffers written in place
        (zero-copy); when ``None`` fresh arrays are allocated.
        """
        import numpy as _np
        if p_out is None:
            p_out = _np.empty(3, dtype=_np.float64)
        if v_out is None:
            v_out = _np.empty(3, dtype=_np.float64)
        if track_pt_out is None:
            track_pt_out = _np.empty(3, dtype=_np.float64)
        rc = self._lib.daa_sim_step(
            self._h,
            p_out.ctypes.data_as(_double_ptr),
            v_out.ctypes.data_as(_double_ptr),
            track_pt_out.ctypes.data_as(_double_ptr),
        )
        if rc != 0:
            raise RuntimeError(f"daa_sim_step failed (rc={rc})")
        return p_out, v_out, track_pt_out

    # -- look-ahead projection ----------------------------------------

    def simulate(self,
                 n_out: int,
                 shift=None,
                 speed_scale: float = 1.0,
                 out=None,
                 mode: int = 0,
                 velocity=None,
                 track_p0=None,
                 track_p1=None,
                 track_speed: float = 0.0):
        """Project the look-ahead trajectory from the current state.

        Samples are spaced ``dt`` apart in time; ``traj[0]`` is the
        current ownship position.  The projection runs on a private
        copy of the ownship and **never** mutates the simulator or its
        tracker.

        * ``mode`` 0 (track route) uses ``shift`` / ``speed_scale`` to
          describe a *hypothetical* route transform (defaults to the
          identity).  Pass a maneuver's shift to preview it, or the
          inverse of the active transform to preview a return-to-route.
        * ``mode`` 1 (hold velocity) ignores the route and previews
          flying the constant NED ``velocity``.
        * ``mode`` 2 (external track) ignores the route and previews
          flying the straight ``track_p0`` -> ``track_p1`` segment at
          the constant ``track_speed`` (m/s).
        * ``out`` optional pre-allocated ``(n_out, 3)`` C-contiguous
          float64 buffer (zero-copy); when ``None`` a fresh array is
          allocated and returned.

        Returns the ``(n_out, 3)`` NED trajectory.
        """
        import numpy as _np
        if shift is None:
            s = _np.zeros(3, dtype=_np.float64)
        else:
            s = _np.ascontiguousarray(shift, dtype=_np.float64).reshape(3)
        if velocity is None:
            v = _np.zeros(3, dtype=_np.float64)
        else:
            v = _np.ascontiguousarray(velocity, dtype=_np.float64).reshape(3)
        p0 = (_np.zeros(3, dtype=_np.float64) if track_p0 is None
              else _np.ascontiguousarray(track_p0, dtype=_np.float64).reshape(3))
        p1 = (_np.zeros(3, dtype=_np.float64) if track_p1 is None
              else _np.ascontiguousarray(track_p1, dtype=_np.float64).reshape(3))
        if out is None:
            out = _np.empty((int(n_out), 3), dtype=_np.float64)
        rc = self._lib.daa_sim_simulate(
            self._h,
            _c_int(int(mode)),
            s.ctypes.data_as(_double_ptr),
            _c_double(speed_scale),
            v.ctypes.data_as(_double_ptr),
            p0.ctypes.data_as(_double_ptr),
            p1.ctypes.data_as(_double_ptr),
            _c_double(track_speed),
            out.ctypes.data_as(_double_ptr),
            _c_int(int(n_out)),
        )
        if rc != 0:
            raise RuntimeError(f"daa_sim_simulate failed (rc={rc})")
        return out

    # -- embedded intruder estimator (CV UKF) -------------------------

    @property
    def capacity(self) -> int:
        """Number of propagation samples the owned buffers can hold."""
        return self._cap

    def est_init_from_measurement(self, z, ownship_pos, ownship_attitude,
                                  ownship_cov, dt, process_noise_std,
                                  measurement_noise_std, velocity_variance,
                                  acceleration_variance,
                                  velocity_variance_vertical=None,
                                  acceleration_variance_vertical=None,
                                  q_var_diag=None):
        """Bootstrap the embedded UKF from a single first measurement.

        The intruder NED position and an anisotropic initial position
        covariance are derived from the measurement geometry inside the
        C++ estimator; velocity and acceleration are seeded to zero with
        the supplied variances and refined by the subsequent
        ``est_predict`` / ``est_update`` stream.  ``measurement_noise_std``
        is a dict with keys ``azimuth_rad``, ``elevation_rad`` and
        ``range_m``.  ``acceleration_variance`` is ignored by models
        without an acceleration state (e.g. CV).

        ``velocity_variance`` / ``acceleration_variance`` seed the
        horizontal (north / east) states.  ``velocity_variance_vertical``
        / ``acceleration_variance_vertical`` seed the vertical (down)
        states; because aircraft fly largely level they are normally
        tighter than the horizontal seeds, which keeps the predicted
        altitude envelope from fanning out over the lookahead horizon.
        Both default to their horizontal counterparts when omitted.

        ``q_var_diag`` optionally overrides the process-noise covariance
        Q with a per-state diagonal (state order; length must equal the
        active model's state dimension — 6 CV, 9 CA / CAB, 8 CTRA),
        replacing the single lumped ``process_noise_std`` so each
        manoeuvre channel is tuned independently.  This is essential for
        CTRA, whose tangential-acceleration ((m/s²)²) and turn-rate
        ((rad/s)²) channels need very different magnitudes.  ``None``
        keeps the model's own (possibly structured) Q.
        """
        import numpy as _np
        if velocity_variance_vertical is None:
            velocity_variance_vertical = velocity_variance
        if acceleration_variance_vertical is None:
            acceleration_variance_vertical = acceleration_variance
        z_arr = _np.ascontiguousarray(z, dtype=_np.float64)
        pos_arr = _np.ascontiguousarray(ownship_pos, dtype=_np.float64)
        att_arr = _np.ascontiguousarray(ownship_attitude, dtype=_np.float64)
        cov_arr = _np.ascontiguousarray(ownship_cov, dtype=_np.float64)
        meas = _np.array([
            measurement_noise_std['azimuth_rad'],
            measurement_noise_std['elevation_rad'],
            measurement_noise_std['range_m'],
        ], dtype=_np.float64)
        if q_var_diag is None:
            q_ptr = None
            q_n = 0
        else:
            q_arr = _np.ascontiguousarray(
                q_var_diag, dtype=_np.float64).reshape(-1)
            q_ptr = q_arr.ctypes.data_as(_double_ptr)
            q_n = int(q_arr.size)
        rc = self._lib.daa_sim_est_init_from_measurement(
            self._h,
            z_arr.ctypes.data_as(_double_ptr),
            pos_arr.ctypes.data_as(_double_ptr),
            att_arr.ctypes.data_as(_double_ptr),
            cov_arr.ctypes.data_as(_double_ptr),
            _c_double(dt), _c_double(process_noise_std),
            meas.ctypes.data_as(_double_ptr),
            _c_double(velocity_variance),
            _c_double(acceleration_variance),
            _c_double(velocity_variance_vertical),
            _c_double(acceleration_variance_vertical),
            q_ptr, _c_int(q_n),
        )
        if rc != 0:
            raise RuntimeError(
                f"daa_sim_est_init_from_measurement failed (rc={rc})")

    def est_predict(self):
        """Time-update the embedded estimator by one ``dt``."""
        rc = self._lib.daa_sim_est_predict(self._h)
        if rc != 0:
            raise RuntimeError(f"daa_sim_est_predict failed (rc={rc})")

    def est_update(self, z, measurement_noise_std, ownship_pos,
                   ownship_attitude, ownship_cov):
        """Measurement-update the embedded estimator.

        ``measurement_noise_std`` is the ``[az_std, el_std, range_std]``
        triple for *this* measurement (radians, radians, feet).  It is
        supplied per call rather than fixed at init so the range variance
        can track the measured distance (e.g. a fraction of range) and so
        a sensor can inject per-frame uncertainty bounds.
        """
        import numpy as _np
        z_arr = _np.ascontiguousarray(z, dtype=_np.float64)
        meas_arr = _np.ascontiguousarray(measurement_noise_std, dtype=_np.float64)
        pos_arr = _np.ascontiguousarray(ownship_pos, dtype=_np.float64)
        att_arr = _np.ascontiguousarray(ownship_attitude, dtype=_np.float64)
        cov_arr = _np.ascontiguousarray(ownship_cov, dtype=_np.float64)
        rc = self._lib.daa_sim_est_update(
            self._h,
            z_arr.ctypes.data_as(_double_ptr),
            meas_arr.ctypes.data_as(_double_ptr),
            pos_arr.ctypes.data_as(_double_ptr),
            att_arr.ctypes.data_as(_double_ptr),
            cov_arr.ctypes.data_as(_double_ptr),
        )
        if rc != 0:
            raise RuntimeError(f"daa_sim_est_update failed (rc={rc})")

    def est_get_state(self, state_out=None, P_out=None, accel_var_out=None):
        """Return the embedded estimator ``(state(6,), P(6,6), accel_var(3,))``.

        ``accel_var`` holds the diagonal variances of the acceleration
        states ``{var_an, var_ae, var_ad}`` (CA / CAB models); it is zero
        for models without an acceleration state (e.g. CV).

        Optional ``state_out`` (a ``(6,)`` buffer), ``P_out`` (a
        ``(6, 6)`` buffer) and ``accel_var_out`` (a ``(3,)`` buffer) are
        pre-allocated C-contiguous float64 arrays written in place
        (zero-copy); when ``None`` fresh arrays are allocated.  Re-using
        caller-owned buffers avoids a per-call allocation in hot per-step
        capture loops.
        """
        import numpy as _np
        if state_out is None:
            state_out = _np.empty(6, dtype=_np.float64)
        if P_out is None:
            P_out = _np.empty((6, 6), dtype=_np.float64)
        if accel_var_out is None:
            accel_var_out = _np.empty(3, dtype=_np.float64)
        rc = self._lib.daa_sim_est_get_state(
            self._h,
            state_out.ctypes.data_as(_double_ptr),
            P_out.ctypes.data_as(_double_ptr),
            accel_var_out.ctypes.data_as(_double_ptr))
        if rc != 0:
            raise RuntimeError(f"daa_sim_est_get_state failed (rc={rc})")
        return state_out, P_out, accel_var_out

    def propagate(self, n):
        """Propagate the intruder for ``n`` samples into the owned buffers.

        Samples are taken on the uniform look-ahead grid ``i*dt``
        (``i`` in ``[0, n)``) using the configured step.  Returns
        zero-copy views ``(pos, cov)`` of shapes ``(n, 3)`` and
        ``(n, 4)`` aliasing the simulator-owned memory.  Each ``cov``
        row is the packed position covariance ``[Pnn, Pne, Pee, Pdd]``
        (the horizontal 2x2 covariance plus the vertical variance) — the
        only terms the protection-cylinder test consumes.  The views
        are overwritten by the next call — copy them to retain the
        result.
        """
        if n < 0 or n > self._cap:
            raise ValueError(f"n={n} out of range [0, {self._cap}]")
        rc = self._lib.daa_sim_propagate_batch(self._h, _c_int(int(n)))
        if rc != 0:
            raise RuntimeError(f"daa_sim_propagate_batch failed (rc={rc})")
        return self._pos_view[:n], self._cov_view[:n]

    def simulate_and_score(self,
                           n_out: int,
                           shift=None,
                           speed_scale: float = 1.0,
                           out=None,
                           mode: int = 0,
                           velocity=None,
                           track_p0=None,
                           track_p1=None,
                           track_speed: float = 0.0):
        """Fused look-ahead projection + cylinder-distance scoring.

        Projects the look-ahead trajectory under the hypothetical route
        transform (as :meth:`simulate`) and scores it against the
        intruder propagation currently held in the owned buffers (fill
        them first with :meth:`propagate`), in a single boundary
        crossing.  The protection cylinder dimensions are taken from the
        simulator configuration (``cyl_h`` / ``cyl_d`` passed at
        construction).

        ``out`` is an optional pre-allocated ``(n_out, 3)`` C-contiguous
        float64 buffer receiving the projected trajectory; pass ``None``
        to skip writing it back (only the score is wanted).

        Returns ``(trajectory_or_None, min_cyldist, idx_cpa)``.
        """
        import numpy as _np
        if shift is None:
            s = _np.zeros(3, dtype=_np.float64)
        else:
            s = _np.ascontiguousarray(shift, dtype=_np.float64).reshape(3)
        if velocity is None:
            v = _np.zeros(3, dtype=_np.float64)
        else:
            v = _np.ascontiguousarray(velocity, dtype=_np.float64).reshape(3)
        p0 = (_np.zeros(3, dtype=_np.float64) if track_p0 is None
              else _np.ascontiguousarray(track_p0, dtype=_np.float64).reshape(3))
        p1 = (_np.zeros(3, dtype=_np.float64) if track_p1 is None
              else _np.ascontiguousarray(track_p1, dtype=_np.float64).reshape(3))
        traj_ptr = (out.ctypes.data_as(_double_ptr)
                    if out is not None else None)
        idx_cpa = _c_int(-1)
        d = self._lib.daa_sim_simulate_and_score(
            self._h,
            _c_int(int(mode)),
            s.ctypes.data_as(_double_ptr),
            _c_double(speed_scale),
            v.ctypes.data_as(_double_ptr),
            p0.ctypes.data_as(_double_ptr),
            p1.ctypes.data_as(_double_ptr),
            _c_double(track_speed),
            traj_ptr,
            _c_int(int(n_out)),
            ctypes.byref(idx_cpa),
        )
        return out, float(d), int(idx_cpa.value)

