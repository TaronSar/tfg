"""
Thin ctypes wrapper around the daa_estimators DLL.

Usage:
    from daa_estimators_wrapper import propagate_batch_cv, propagate_batch_ca, propagate_batch_cab

    positions, covariances = propagate_batch_cv(
        n0, e0, d0, vn, ve, vd, P_full, taus
    )
"""

import ctypes
import os
import sys
import numpy as np
from numpy.ctypeslib import ndpointer

# --------------- locate and load the DLL ---------------

_c_double   = ctypes.c_double
_c_int      = ctypes.c_int
_double_ptr = ctypes.POINTER(ctypes.c_double)


def _load_lib():
    """Find daa_estimators DLL next to this file, or on PATH."""
    here = os.path.dirname(os.path.abspath(__file__))
    if sys.platform == "win32":
        names = ["daa_estimators.dll", "DAA_dll__sil.dll"]
    else:
        names = ["libdaa_estimators.so", "libDAA_dll__sil.so"]

    for name in names:
        path = os.path.join(here, name)
        if os.path.isfile(path):
            return ctypes.CDLL(path)
    # Fall back to system search
    return ctypes.CDLL(names[0])


_lib = _load_lib()


# --------------- declare signatures ---------------

_lib.propagate_batch_cv.restype  = _c_int
_lib.propagate_batch_cv.argtypes = [
    _c_double, _c_double, _c_double,          # n0, e0, d0
    _c_double, _c_double, _c_double,          # vn, ve, vd
    _double_ptr,                               # P_full (6×6) or NULL
    _double_ptr, _c_int,                       # taus, N
    _double_ptr,                               # pos_out
    _double_ptr,                               # cov_out or NULL
]

_lib.propagate_batch_ca.restype  = _c_int
_lib.propagate_batch_ca.argtypes = [
    _c_double, _c_double, _c_double,          # n0, e0, d0
    _c_double, _c_double, _c_double,          # vn, ve, vd
    _c_double, _c_double, _c_double,          # an, ae, ad
    _double_ptr,                               # P_full (9×9) or NULL
    _double_ptr, _c_int,                       # taus, N
    _double_ptr,                               # pos_out
    _double_ptr,                               # cov_out or NULL
]

_lib.propagate_batch_cab.restype  = _c_int
_lib.propagate_batch_cab.argtypes = [
    _c_double, _c_double, _c_double,          # n0, e0, d0
    _c_double, _c_double, _c_double,          # vn, ve, vd
    _c_double, _c_double, _c_double,          # a_tan, a_nor, a_ver
    _double_ptr,                               # P_full (9×9) or NULL
    _double_ptr, _c_int,                       # taus, N
    _double_ptr,                               # pos_out
    _double_ptr,                               # cov_out or NULL
]


# --------------- helpers ---------------

def _as_ptr(arr):
    """Convert a contiguous float64 numpy array to a ctypes double pointer."""
    if arr is None:
        return None
    arr = np.ascontiguousarray(arr, dtype=np.float64)
    return arr.ctypes.data_as(_double_ptr)


# --------------- public API ---------------

def propagate_batch_cv(n0, e0, d0, vn, ve, vd, P_full, taus):
    """CV model: p(τ) = p₀ + v·τ.

    Args:
        n0, e0, d0: position [ft]
        vn, ve, vd: velocity [ft/s]
        P_full:     6×6 covariance (ndarray) or None
        taus:       1-D array of lookahead times [s], ascending

    Returns:
        (positions, covariances)
        positions:   (N, 3) ndarray — [north, east, down] per tau
        covariances: (N, 3, 3) ndarray or None
    """
    taus = np.ascontiguousarray(taus, dtype=np.float64)
    N = len(taus)
    pos_out = np.empty((N, 3), dtype=np.float64)
    cov_out = np.empty((N, 3, 3), dtype=np.float64) if P_full is not None else None

    rc = _lib.propagate_batch_cv(
        n0, e0, d0, vn, ve, vd,
        _as_ptr(P_full),
        _as_ptr(taus), N,
        _as_ptr(pos_out),
        _as_ptr(cov_out),
    )
    if rc != 0:
        raise RuntimeError(f"propagate_batch_cv returned {rc}")
    return pos_out, cov_out


def propagate_batch_ca(n0, e0, d0, vn, ve, vd, an, ae, ad, P_full, taus):
    """CA model: p(τ) = p₀ + v·τ + ½a·τ².

    Args:
        n0, e0, d0: position [ft]
        vn, ve, vd: velocity [ft/s]
        an, ae, ad: acceleration [ft/s²]
        P_full:     9×9 covariance (ndarray) or None
        taus:       1-D array of lookahead times [s], ascending

    Returns:
        (positions, covariances)
    """
    taus = np.ascontiguousarray(taus, dtype=np.float64)
    N = len(taus)
    pos_out = np.empty((N, 3), dtype=np.float64)
    cov_out = np.empty((N, 3, 3), dtype=np.float64) if P_full is not None else None

    rc = _lib.propagate_batch_ca(
        n0, e0, d0, vn, ve, vd, an, ae, ad,
        _as_ptr(P_full),
        _as_ptr(taus), N,
        _as_ptr(pos_out),
        _as_ptr(cov_out),
    )
    if rc != 0:
        raise RuntimeError(f"propagate_batch_ca returned {rc}")
    return pos_out, cov_out


def propagate_batch_cab(n0, e0, d0, vn, ve, vd, a_tan, a_nor, a_ver,
                        P_full, taus):
    """CAB model: sub-stepped Euler with body-frame acceleration.

    Note: covariance propagation is not yet implemented in the DLL.
          cov_out will be zeros when P_full is provided.

    Args:
        n0, e0, d0:          position [ft]
        vn, ve, vd:          velocity [ft/s]
        a_tan, a_nor, a_ver: body-frame acceleration [ft/s²]
        P_full:              9×9 covariance (ndarray) or None
        taus:                1-D array of lookahead times [s], ascending

    Returns:
        (positions, covariances)
    """
    taus = np.ascontiguousarray(taus, dtype=np.float64)
    N = len(taus)
    pos_out = np.empty((N, 3), dtype=np.float64)
    cov_out = np.empty((N, 3, 3), dtype=np.float64) if P_full is not None else None

    rc = _lib.propagate_batch_cab(
        n0, e0, d0, vn, ve, vd, a_tan, a_nor, a_ver,
        _as_ptr(P_full),
        _as_ptr(taus), N,
        _as_ptr(pos_out),
        _as_ptr(cov_out),
    )
    if rc != 0:
        raise RuntimeError(f"propagate_batch_cab returned {rc}")
    return pos_out, cov_out
