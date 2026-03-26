"""
SPAM Material Parameter Extraction (Inverse Solver)

Given measured SPAM S-parameters, find the permittivity and permeability
tensors (eps_r, mu_r) that best reproduce the measured transmission matrix.

Public API
----------
extract_material             -- Single-stage extraction for a given tensor type
extract_material_progressive -- Multi-stage: isotropic -> diagonal -> symmetric
"""

import os
import warnings
import numpy as np
from scipy.optimize import minimize

from .spam_calc import (
    material_to_tmatrix,
    spam_s_to_tmatrix,
    tmatrix_error,
)

_N_WORKERS = min(os.cpu_count() or 1, 4)

# ---------------------------------------------------------------------------
# Parameter vector packing / unpacking
# ---------------------------------------------------------------------------

def _pack_params(erv, mrv, tensor_type):
    """Flatten erv/mrv into an optimizer parameter vector."""
    erv = np.asarray(erv, dtype=complex)
    mrv = np.asarray(mrv, dtype=complex)

    if tensor_type == "isotropic":
        return np.array([erv[0].real, mrv[0].real])
    elif tensor_type == "diagonal":
        return np.array([erv[0].real, erv[3].real, erv[5].real,
                         mrv[0].real, mrv[3].real, mrv[5].real])
    elif tensor_type == "symmetric":
        return np.concatenate([erv.real, mrv.real])
    elif tensor_type == "complex_symmetric":
        return np.concatenate([erv.real, erv.imag, mrv.real, mrv.imag])
    else:
        raise ValueError(f"Unknown tensor_type: {tensor_type}")


def _unpack_params(x, tensor_type):
    """Reconstruct erv/mrv from an optimizer parameter vector."""
    if tensor_type == "isotropic":
        eps, mu = x[0], x[1]
        erv = np.array([eps, 0, 0, eps, 0, eps], dtype=complex)
        mrv = np.array([mu, 0, 0, mu, 0, mu], dtype=complex)
    elif tensor_type == "diagonal":
        exx, eyy, ezz = x[0], x[1], x[2]
        mxx, myy, mzz = x[3], x[4], x[5]
        erv = np.array([exx, 0, 0, eyy, 0, ezz], dtype=complex)
        mrv = np.array([mxx, 0, 0, myy, 0, mzz], dtype=complex)
    elif tensor_type == "symmetric":
        erv = np.array(x[:6], dtype=complex)
        mrv = np.array(x[6:12], dtype=complex)
    elif tensor_type == "complex_symmetric":
        erv = np.array(x[:6]) + 1j * np.array(x[6:12])
        mrv = np.array(x[12:18]) + 1j * np.array(x[18:24])
    else:
        raise ValueError(f"Unknown tensor_type: {tensor_type}")
    return erv, mrv


def _default_guess(tensor_type):
    """Reasonable starting point for the optimizer."""
    if tensor_type == "isotropic":
        return np.array([2.0, 2.0])
    elif tensor_type == "diagonal":
        return np.array([2.0, 2.0, 3.0, 2.0, 2.0, 3.0])
    elif tensor_type == "symmetric":
        return np.array([2.0, 0.0, 0.0, 2.0, 0.0, 3.0,
                         2.0, 0.0, 0.0, 2.0, 0.0, 3.0])
    elif tensor_type == "complex_symmetric":
        return np.array([2.0, 0.0, 0.0, 2.0, 0.0, 3.0,
                         0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                         2.0, 0.0, 0.0, 2.0, 0.0, 3.0,
                         0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    else:
        raise ValueError(f"Unknown tensor_type: {tensor_type}")


def _default_bounds(tensor_type):
    """Parameter bounds."""
    if tensor_type == "isotropic":
        return [(0.5, 20.0), (0.5, 20.0)]
    elif tensor_type == "diagonal":
        return [(0.5, 20.0)] * 6
    elif tensor_type == "symmetric":
        d = (0.5, 20.0)
        o = (-10.0, 10.0)
        return [d, o, o, d, o, d, d, o, o, d, o, d]
    elif tensor_type == "complex_symmetric":
        d = (0.5, 20.0)
        o = (-10.0, 10.0)
        im_d = (-10.0, 0.0)
        im_o = (-10.0, 10.0)
        return ([d, o, o, d, o, d]
                + [im_d, im_o, im_o, im_d, im_o, im_d]
                + [d, o, o, d, o, d]
                + [im_d, im_o, im_o, im_d, im_o, im_d])
    else:
        raise ValueError(f"Unknown tensor_type: {tensor_type}")


# ---------------------------------------------------------------------------
# Cost function
# ---------------------------------------------------------------------------

def _cost(x, tensor_type, T_measured, theta_deg, k0d):
    """Scalar cost: mean relative T-matrix error for parameter vector *x*."""
    erv, mrv = _unpack_params(x, tensor_type)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            T_theory = material_to_tmatrix(erv, mrv, theta_deg, k0d)
            _, mean_err = tmatrix_error(T_measured, T_theory)
        except Exception:
            return 1e6
    if not np.isfinite(mean_err):
        return 1e6
    return mean_err


def _run_powell(x0, cost_args, bounds, max_iter):
    """Run a single bounded-Powell minimisation."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return minimize(
            _cost, x0, args=cost_args,
            method="Powell", bounds=bounds,
            options={"maxiter": max_iter, "maxfev": max_iter * 5},
        )


def _powell_worker(args):
    """Top-level function for multiprocessing (must be picklable)."""
    x0, cost_args, bounds, max_iter = args
    return _run_powell(x0, cost_args, bounds, max_iter)


def _tighten_bounds(default_bounds, x0, margin=0.5):
    """Narrow bounds around *x0* by +/- margin fraction of the default range."""
    tight = []
    for val, (lo, hi) in zip(x0, default_bounds):
        span = (hi - lo) * margin
        tight.append((max(lo, val - span), min(hi, val + span)))
    return tight


# ---------------------------------------------------------------------------
# Public: single-stage extraction
# ---------------------------------------------------------------------------

_GOOD_FIT = 1e-4

def extract_material(S_SPAM, theta_deg, k0d,
                     tensor_type="symmetric",
                     initial_guess=None,
                     max_iter=5000,
                     n_restarts=1,
                     bounds_override=None,
                     callback=None):
    """Extract material parameters from SPAM S-parameter measurements.

    Parameters
    ----------
    S_SPAM : ndarray, shape (Ntheta, 4, 4)
        Measured SPAM scattering matrix in h-v coordinates.
    theta_deg : array-like
        Incidence angles in degrees.
    k0d : float
        Free-space wavenumber x slab thickness.
    tensor_type : str
        One of 'isotropic', 'diagonal', 'symmetric', 'complex_symmetric'.
    initial_guess : ndarray or None
        Starting point (packed parameter vector). Uses default if None.
    max_iter : int
        Maximum optimiser iterations.
    n_restarts : int
        Number of random restarts (best result kept). 1 = single run.
    bounds_override : list or None
        Custom parameter bounds; uses defaults if None.
    callback : callable or None
        Called as callback(xk) after each iteration.

    Returns
    -------
    dict  with keys: erv, mrv, eps_r, mu_r, fit_error,
          err_per_angle, success, nfev, message
    """
    theta_deg = np.asarray(theta_deg, dtype=float).ravel()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        T_measured = spam_s_to_tmatrix(S_SPAM, theta_deg)

    if initial_guess is None:
        x0 = _default_guess(tensor_type)
    else:
        x0 = np.asarray(initial_guess, dtype=float)

    cost_args = (tensor_type, T_measured, theta_deg, k0d)
    bounds = bounds_override if bounds_override is not None else _default_bounds(tensor_type)

    if n_restarts <= 1:
        best_opt = _run_powell(x0, cost_args, bounds, max_iter)
    else:
        rng = np.random.default_rng(42)
        all_x0 = [x0] + [
            np.array([rng.uniform(lo, hi) for lo, hi in bounds])
            for _ in range(n_restarts - 1)
        ]

        try:
            from multiprocessing import Pool
            with Pool(min(n_restarts, _N_WORKERS)) as pool:
                all_opts = pool.map(
                    _powell_worker,
                    [(xi, cost_args, bounds, max_iter) for xi in all_x0],
                )
            best_opt = min(all_opts, key=lambda r: r.fun)
        except (OSError, RuntimeError, ImportError):
            best_opt = _run_powell(x0, cost_args, bounds, max_iter)
            for x_rand in all_x0[1:]:
                if best_opt.fun < _GOOD_FIT:
                    break
                opt_i = _run_powell(x_rand, cost_args, bounds, max_iter)
                if opt_i.fun < best_opt.fun:
                    best_opt = opt_i

    opt = best_opt
    erv, mrv = _unpack_params(opt.x, tensor_type)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            T_theory = material_to_tmatrix(erv, mrv, theta_deg, k0d)
            err_per_angle, fit_error = tmatrix_error(T_measured, T_theory)
        except Exception:
            err_per_angle = np.full(len(theta_deg), np.nan)
            fit_error = float("inf")

    erv_c = np.asarray(erv, dtype=complex)
    mrv_c = np.asarray(mrv, dtype=complex)
    eps_r = np.array([[erv_c[0], erv_c[1], erv_c[2]],
                      [erv_c[1], erv_c[3], erv_c[4]],
                      [erv_c[2], erv_c[4], erv_c[5]]])
    mu_r = np.array([[mrv_c[0], mrv_c[1], mrv_c[2]],
                     [mrv_c[1], mrv_c[3], mrv_c[4]],
                     [mrv_c[2], mrv_c[4], mrv_c[5]]])

    return {
        "erv": erv_c,
        "mrv": mrv_c,
        "eps_r": eps_r,
        "mu_r": mu_r,
        "fit_error": fit_error,
        "err_per_angle": err_per_angle,
        "success": opt.success,
        "nfev": opt.nfev,
        "message": str(opt.message),
    }


# ---------------------------------------------------------------------------
# Public: progressive (staged) extraction
# ---------------------------------------------------------------------------

def extract_material_progressive(S_SPAM, theta_deg, k0d,
                                 target_type="symmetric",
                                 max_iter_per_stage=3000,
                                 callback=None):
    """Multi-stage extraction that progressively refines the solution.

    Stages: isotropic -> diagonal -> symmetric (-> complex_symmetric).
    Each stage uses the previous result as its initial guess, with bounds
    tightened around the prior solution to reduce search space.

    Parameters
    ----------
    S_SPAM : ndarray, shape (Ntheta, 4, 4)
    theta_deg : array-like
    k0d : float
    target_type : str
        Final tensor type to extract.
    max_iter_per_stage : int
    callback : callable or None
        Called as callback(stage_name, result_dict) after each stage.

    Returns
    -------
    result : dict  (same format as extract_material)
    """
    stages = ["isotropic", "diagonal", "symmetric", "complex_symmetric"]
    target_idx = stages.index(target_type)
    stages = stages[: target_idx + 1]

    theta_deg = np.asarray(theta_deg, dtype=float).ravel()
    result = None

    for stage in stages:
        if result is not None:
            prev_erv, prev_mrv = result["erv"], result["mrv"]
            x0 = _pack_params(prev_erv, prev_mrv, stage)
            bounds = _tighten_bounds(_default_bounds(stage), x0, margin=0.5)
        else:
            x0 = None
            bounds = None

        n_params = len(_default_guess(stage))
        restarts = max(1, 8 // max(n_params, 1)) + 1

        result = extract_material(
            S_SPAM, theta_deg, k0d,
            tensor_type=stage,
            initial_guess=x0,
            max_iter=max_iter_per_stage,
            n_restarts=restarts,
            bounds_override=bounds,
        )

        if callback is not None:
            callback(stage, result)

    return result
