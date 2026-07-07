"""
Compute the closest distance between a 3D ellipsoid surface (matrix form)
and a vertical cylinder surface with bases in the XY plane.

Ellipsoid: (x - c)^T A (x - c) = 1
    A : 3x3 symmetric positive-definite matrix
    c : 3D center

Cylinder: vertical axis at (cx, cy), radius r, z in [z_min, z_max].
    Surface includes the lateral wall and both circular caps.

Approach
--------
The ellipsoid is parametrized via spherical angles (theta, phi) mapped
through the inverse Cholesky factor of A.  For each candidate ellipsoid
point the closest point on the cylinder surface is computed analytically.
The 2-parameter objective is minimised with Nelder-Mead over many random
restarts to guard against local minima.
"""

import numpy as np


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def ellipsoid_point(theta, phi, L_inv_T, center):
    """Map spherical angles to a point on the ellipsoid surface.

    Given the Cholesky decomposition A = L L^T, a point on the ellipsoid is
        x = center + L^{-T} u
    where u = (sin(theta)cos(phi), sin(theta)sin(phi), cos(theta)).
    """
    u = np.array([
        np.sin(theta) * np.cos(phi),
        np.sin(theta) * np.sin(phi),
        np.cos(theta),
    ])
    return center + L_inv_T @ u


def closest_point_on_cylinder(point, cyl_center_xy, radius, z_min, z_max):
    """Closest point on a closed vertical cylinder surface to *point*.

    The cylinder surface is the union of:
      - lateral wall  : (x-cx)^2 + (y-cy)^2 = r^2,  z_min <= z <= z_max
      - top cap       : (x-cx)^2 + (y-cy)^2 <= r^2,  z = z_max
      - bottom cap    : (x-cx)^2 + (y-cy)^2 <= r^2,  z = z_min

    Returns
    -------
    closest : ndarray (3,)
    distance : float
    """
    px, py, pz = point
    cx, cy = cyl_center_xy

    dx, dy = px - cx, py - cy
    d_xy = np.hypot(dx, dy)

    # Unit radial direction in the XY plane (arbitrary when on-axis)
    if d_xy > 1e-14:
        ux, uy = dx / d_xy, dy / d_xy
    else:
        ux, uy = 1.0, 0.0

    # Candidate 1 – lateral surface
    z_clamp = np.clip(pz, z_min, z_max)
    lat = np.array([cx + radius * ux, cy + radius * uy, z_clamp])

    # Candidate 2 – top cap (z = z_max)
    rho = min(d_xy, radius)
    top = np.array([cx + rho * ux, cy + rho * uy, z_max])

    # Candidate 3 – bottom cap (z = z_min)
    bot = np.array([cx + rho * ux, cy + rho * uy, z_min])

    best_pt, best_d = lat, np.linalg.norm(point - lat)
    for cand in (top, bot):
        d = np.linalg.norm(point - cand)
        if d < best_d:
            best_pt, best_d = cand, d

    return best_pt, best_d


def ray_cylinder_intersection(origin, target, cyl_center_xy, radius, z_min, z_max):
    """Find where the ray from *origin* toward *target* exits the cylinder surface.

    The ray is  P(t) = origin + t * (target - origin),  t >= 0.
    Returns the first intersection point on the cylinder surface (lateral wall
    or caps) in the direction of *target*.
    """
    d = target - origin
    cx, cy = cyl_center_xy
    candidates = []

    # Lateral wall:  (ox + t*dx - cx)^2 + (oy + t*dy - cy)^2 = r^2
    ox, oy = origin[0] - cx, origin[1] - cy
    a_coef = d[0]**2 + d[1]**2
    b_coef = 2.0 * (ox * d[0] + oy * d[1])
    c_coef = ox**2 + oy**2 - radius**2

    if a_coef > 1e-28:
        disc = b_coef**2 - 4.0 * a_coef * c_coef
        if disc >= 0.0:
            sqrt_disc = np.sqrt(max(disc, 0.0))
            for t_lat in ((-b_coef + sqrt_disc) / (2.0 * a_coef),
                          (-b_coef - sqrt_disc) / (2.0 * a_coef)):
                if t_lat > -1e-12:
                    pt = origin + max(t_lat, 0.0) * d
                    if z_min - 1e-10 <= pt[2] <= z_max + 1e-10:
                        candidates.append((max(t_lat, 0.0), pt))

    # Top cap  z = z_max
    if abs(d[2]) > 1e-14:
        t_top = (z_max - origin[2]) / d[2]
        if t_top > -1e-12:
            pt = origin + max(t_top, 0.0) * d
            rho = np.hypot(pt[0] - cx, pt[1] - cy)
            if rho <= radius + 1e-10:
                candidates.append((max(t_top, 0.0), pt))

        # Bottom cap  z = z_min
        t_bot = (z_min - origin[2]) / d[2]
        if t_bot > -1e-12:
            pt = origin + max(t_bot, 0.0) * d
            rho = np.hypot(pt[0] - cx, pt[1] - cy)
            if rho <= radius + 1e-10:
                candidates.append((max(t_bot, 0.0), pt))

    if not candidates:
        # Fallback – should not happen when origin is inside the cylinder
        return closest_point_on_cylinder(target, cyl_center_xy, radius,
                                         z_min, z_max)[0]

    # Pick the candidate with the smallest positive t (first exit)
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


# ---------------------------------------------------------------------------
# Nelder-Mead simplex optimiser (pure numpy)
# ---------------------------------------------------------------------------

def _nelder_mead(func, x0, xtol=1e-4, ftol=1e-12, maxiter=10000):
    """Minimise *func*(x) using the Nelder-Mead simplex method.

    Parameters
    ----------
    func : callable  (ndarray -> float)
    x0 : array_like (n,)
    xtol, ftol : float  –  convergence tolerances
    maxiter : int

    Returns
    -------
    best_x : ndarray (n,)
    best_f : float
    """
    n = len(x0)
    # Build initial simplex
    simplex = np.empty((n + 1, n))
    simplex[0] = x0
    for i in range(n):
        v = np.array(x0, dtype=float)
        v[i] += 0.05 if v[i] == 0.0 else 0.05 * v[i]
        simplex[i + 1] = v

    f_vals = np.array([func(simplex[i]) for i in range(n + 1)])

    alpha, gamma, rho, sigma = 1.0, 2.0, 0.5, 0.5

    for _ in range(maxiter):
        # Sort
        order = np.argsort(f_vals)
        simplex = simplex[order]
        f_vals = f_vals[order]

        # Check convergence
        if (np.max(np.abs(simplex[-1] - simplex[0])) < xtol and
                np.abs(f_vals[-1] - f_vals[0]) < ftol):
            break

        # Centroid of all but worst
        centroid = simplex[:-1].mean(axis=0)

        # Reflection
        xr = centroid + alpha * (centroid - simplex[-1])
        fr = func(xr)
        if f_vals[0] <= fr < f_vals[-2]:
            simplex[-1], f_vals[-1] = xr, fr
            continue

        # Expansion
        if fr < f_vals[0]:
            xe = centroid + gamma * (xr - centroid)
            fe = func(xe)
            if fe < fr:
                simplex[-1], f_vals[-1] = xe, fe
            else:
                simplex[-1], f_vals[-1] = xr, fr
            continue

        # Contraction
        xc = centroid + rho * (simplex[-1] - centroid)
        fc = func(xc)
        if fc < f_vals[-1]:
            simplex[-1], f_vals[-1] = xc, fc
            continue

        # Shrink
        for i in range(1, n + 1):
            simplex[i] = simplex[0] + sigma * (simplex[i] - simplex[0])
            f_vals[i] = func(simplex[i])

    best_idx = np.argmin(f_vals)
    return simplex[best_idx], f_vals[best_idx]


# ---------------------------------------------------------------------------
# Gradient descent optimiser (pure numpy, finite-difference gradients)
# ---------------------------------------------------------------------------

def _gradient_descent(func, x0, lr=0.05, ftol=1e-10, maxiter=10000, h=1e-7):
    """Minimise *func*(x) using the Adam optimiser with finite-difference gradients.

    Parameters
    ----------
    func : callable  (ndarray -> float)
    x0 : array_like (n,)
    lr : float  –  learning rate
    ftol : float  –  convergence tolerance on function value change
    maxiter : int
    h : float  –  finite-difference step size

    Returns
    -------
    best_x : ndarray (n,)
    best_f : float
    """
    x = np.array(x0, dtype=float)
    n = len(x)
    f_val = func(x)
    best_x, best_f = x.copy(), f_val

    # Adam parameters
    beta1, beta2, eps = 0.9, 0.999, 1e-8
    m = np.zeros(n)
    v = np.zeros(n)

    for t in range(1, maxiter + 1):
        # Forward finite differences (n+1 evals total including cached f_val)
        grad = np.empty(n)
        for i in range(n):
            x_fwd = x.copy(); x_fwd[i] += h
            grad[i] = (func(x_fwd) - f_val) / h

        # Adam update
        m = beta1 * m + (1.0 - beta1) * grad
        v = beta2 * v + (1.0 - beta2) * grad * grad
        m_hat = m / (1.0 - beta1**t)
        v_hat = v / (1.0 - beta2**t)
        x_new = x - lr * m_hat / (np.sqrt(v_hat) + eps)
        f_new = func(x_new)

        if f_new < best_f:
            best_x, best_f = x_new.copy(), f_new

        # Convergence check
        if abs(f_val - f_new) < ftol:
            break

        x = x_new
        f_val = f_new

    return best_x, best_f


# ---------------------------------------------------------------------------
# Main solver
# ---------------------------------------------------------------------------

def ellipsoid_cylinder_distance(A, center, cyl_center_xy, cyl_radius,
                                z_min, z_max, n_restarts=0,
                                maxiter=500, ftol=1e-12,
                                optimizer='nelder-mead'):
    """Minimum distance between an ellipsoid surface and a cylinder surface.

    An analytical seed (ellipsoid point facing the cylinder) is always
    computed and used as the primary optimiser starting point.  Additional
    random restarts can be requested for extra robustness.

    Parameters
    ----------
    A : array_like (3, 3)
        Symmetric positive-definite matrix defining the ellipsoid
        (x - center)^T A (x - center) = 1.
    center : array_like (3,)
        Ellipsoid centre.
    cyl_center_xy : array_like (2,)
        (x, y) position of the cylinder axis.
    cyl_radius : float
        Cylinder radius (> 0).
    z_min, z_max : float
        Vertical extent of the cylinder (z_min < z_max).
    n_restarts : int
        Extra random restarts for the optimiser (0 = analytical seed only).
    maxiter : int
        Maximum iterations per optimiser run.
    ftol : float
        Function-value convergence tolerance (in the same units as the
        distance, e.g. metres).
    optimizer : str
        Optimisation method: 'nelder-mead' (default) or 'gradient-descent'.

    Returns
    -------
    distance : float
        Minimum Euclidean distance (0 when the surfaces intersect).
    p_ellipsoid : ndarray (3,)
        Closest point on the ellipsoid.
    p_cylinder : ndarray (3,)
        Closest point on the cylinder.
    """
    A = np.asarray(A, dtype=float)
    center = np.asarray(center, dtype=float)
    cyl_center_xy = np.asarray(cyl_center_xy, dtype=float)

    # Select optimiser
    opt_name = optimizer.lower().replace('_', '-')
    if opt_name == 'gradient-descent':
        _optimize = _gradient_descent
    elif opt_name == 'nelder-mead':
        _optimize = _nelder_mead
    else:
        raise ValueError(f"Unknown optimizer '{optimizer}'. "
                         f"Use 'nelder-mead' or 'gradient-descent'.")

    # Cholesky: A = L L^T  =>  ellipsoid point x = center + L^{-T} u
    L = np.linalg.cholesky(A)
    L_inv_T = np.linalg.inv(L.T)

    # Analytical seed: ellipsoid surface point in the direction of the
    # cylinder center.  This seed is cheap (no optimisation) and ensures
    # the solver always explores the side of the ellipsoid that faces the
    # cylinder, which is critical for reliable inside-cylinder detection.
    cyl_center_3d = np.array([cyl_center_xy[0], cyl_center_xy[1],
                              0.5 * (z_min + z_max)])
    dir_to_cyl = cyl_center_3d - center
    w = L.T @ dir_to_cyl
    w_norm = np.linalg.norm(w)
    if w_norm > 1e-14:
        u_dir = w / w_norm
    else:
        u_dir = np.array([1.0, 0.0, 0.0])
    analytical_seed = np.array([
        np.arccos(np.clip(u_dir[2], -1.0, 1.0)),
        np.arctan2(u_dir[1], u_dir[0]),
    ])
    pe_analytical = ellipsoid_point(analytical_seed[0], analytical_seed[1],
                                    L_inv_T, center)

    def objective(params):
        theta, phi = params
        pe = ellipsoid_point(theta, phi, L_inv_T, center)
        _, d = closest_point_on_cylinder(pe, cyl_center_xy, cyl_radius,
                                         z_min, z_max)
        return d

    # --- Analytical seed (always tried) --------------------------------------
    best_params, best_val = _optimize(objective, analytical_seed.copy(),
                                      maxiter=maxiter, ftol=ftol)

    # --- Optional random restarts --------------------------------------------
    if n_restarts > 0:
        rng = np.random.default_rng(42)
        thetas = np.arccos(1.0 - 2.0 * rng.uniform(size=n_restarts))
        phis = rng.uniform(0.0, 2.0 * np.pi, n_restarts)

        for t0, p0 in zip(thetas, phis):
            x_opt, f_opt = _optimize(objective, np.array([t0, p0]),
                                        maxiter=maxiter, ftol=ftol)
            if f_opt < best_val:
                best_val = f_opt
                best_params = x_opt

    # --- Extract solution ----------------------------------------------------
    pe_opt = ellipsoid_point(best_params[0], best_params[1], L_inv_T, center)
    pc_opt, dist_opt = closest_point_on_cylinder(
        pe_opt, cyl_center_xy, cyl_radius, z_min, z_max)

    # --- Check if the ellipsoid penetrates the cylinder ----------------------
    # Use BOTH the optimiser result and the analytical point (which faces the
    # cylinder) so that detection does not depend on the optimiser finding the
    # exact global minimum.
    def _is_inside_cylinder(pt):
        d_xy = np.hypot(pt[0] - cyl_center_xy[0], pt[1] - cyl_center_xy[1])
        return d_xy <= cyl_radius and z_min <= pt[2] <= z_max

    if _is_inside_cylinder(pe_opt) or _is_inside_cylinder(pe_analytical) or dist_opt < 1e-6:

        def objective_center(params):
            theta, phi = params
            pe = ellipsoid_point(theta, phi, L_inv_T, center)
            return np.linalg.norm(pe - cyl_center_3d)

        # Start from the analytical seed (points toward cylinder center)
        x_opt, _ = _optimize(objective_center,
                                analytical_seed.copy(), maxiter=maxiter, ftol=ftol)

        if n_restarts > 0:
            rng2 = np.random.default_rng(123)
            thetas2 = np.arccos(1.0 - 2.0 * rng2.uniform(size=n_restarts))
            phis2 = rng2.uniform(0.0, 2.0 * np.pi, n_restarts)
            best_center_val = objective_center(x_opt)
            best_center_params = x_opt
            for t0, p0 in zip(thetas2, phis2):
                xc, fc = _optimize(objective_center,
                                      np.array([t0, p0]), maxiter=maxiter, ftol=ftol)
                if fc < best_center_val:
                    best_center_val = fc
                    best_center_params = xc
            x_opt = best_center_params

        best_params = x_opt
        pe_opt = ellipsoid_point(best_params[0], best_params[1], L_inv_T, center)
        # Cylinder point = where the ray from cylinder center through the
        # ellipsoid point intersects the cylinder surface.
        pc_opt = ray_cylinder_intersection(
            cyl_center_3d, pe_opt, cyl_center_xy, cyl_radius, z_min, z_max)
        dist_opt = np.linalg.norm(pe_opt - pc_opt)

    return dist_opt, pe_opt, pc_opt


# ---------------------------------------------------------------------------
# Demo / self-test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    # Axis-aligned ellipsoid with semi-axes a=3, b=2, c=1 at the origin
    #   A = diag(1/a², 1/b², 1/c²)
    A = np.diag([1.0 / 9.0, 1.0 / 4.0, 1.0])
    center = np.array([0.0, 0.0, 0.0])

    # Vertical cylinder at (6, 0), radius 1, z ∈ [-2, 2]
    cyl_xy = np.array([6.0, 0.0])
    cyl_r = 1.0
    z_lo, z_hi = -2.0, 2.0

    dist, pe, pc = ellipsoid_cylinder_distance(
        A, center, cyl_xy, cyl_r, z_lo, z_hi)

    print(f"Minimum distance : {dist:.6f}")
    print(f"Ellipsoid point  : ({pe[0]:.6f}, {pe[1]:.6f}, {pe[2]:.6f})")
    print(f"Cylinder point   : ({pc[0]:.6f}, {pc[1]:.6f}, {pc[2]:.6f})")
    print(f"\nSanity check: ellipsoid reaches x=3, cylinder wall at x=5  "
          f"=> expected distance ≈ 2.0")
