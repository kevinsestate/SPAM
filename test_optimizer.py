"""
Validate the inverse solver against simulated HFSS data.

Usage:
    python test_optimizer.py
"""

import os
import time
import numpy as np
import scipy.io as sio

from spam_optimizer import extract_material_progressive
from spam_calc import compute_k0d, mil_to_m

K0D = compute_k0d(24e9, mil_to_m(60))
DATA_DIR = os.path.join(os.path.dirname(__file__), "Simulated Spam Calculations")


def load_mat(fname):
    path = os.path.join(DATA_DIR, fname)
    d = sio.loadmat(path)
    S = np.transpose(d["S_SPAM"], (2, 0, 1))
    th = d["theta_deg"].ravel()
    return S, th


def stage_cb(stage, res):
    print(f"    [{stage:20s}]  error={res['fit_error']:.6f}  nfev={res['nfev']}")


def run_case(label, fname, true_erv, true_mrv, target):
    print("=" * 60)
    print(f"  {label}")
    print("=" * 60)
    S, th = load_mat(fname)
    t0 = time.time()
    r = extract_material_progressive(
        S, th, K0D,
        target_type=target,
        max_iter_per_stage=2000,
        callback=stage_cb,
    )
    dt = time.time() - t0
    true_e = np.asarray(true_erv, dtype=complex)
    true_m = np.asarray(true_mrv, dtype=complex)
    print(f"  Extracted erv = {np.round(r['erv'].real, 4)}")
    print(f"  True      erv = {np.round(true_e.real, 4)}")
    print(f"  Extracted mrv = {np.round(r['mrv'].real, 4)}")
    print(f"  True      mrv = {np.round(true_m.real, 4)}")
    print(f"  max |erv err| = {np.max(np.abs(true_e - r['erv'])):.4f}")
    print(f"  max |mrv err| = {np.max(np.abs(true_m - r['mrv'])):.4f}")
    print(f"  fit error     = {r['fit_error']:.6f}")
    print(f"  elapsed       = {dt:.1f}s")
    print()
    return r


if __name__ == "__main__":
    run_case("Test 1: isotropic (er2_mur3 -> diagonal)",
             "SPAM_Scat_Mat_er2_mur3.mat",
             [2, 0, 0, 2, 1e-6, 2], [3, 0, 0, 3, 0, 3],
             "diagonal")

    run_case("Test 2: diagonal (er225_mur343 -> diagonal)",
             "SPAM_Scat_Mat_er225_mur343.mat",
             [2, 0, 0, 2, 0, 5], [3, 0, 0, 4, 0, 3],
             "diagonal")

    run_case("Test 3: full symmetric (erfull_murdiag -> symmetric)",
             "SPAM_Scat_Mat_erfull_murdiag.mat",
             [2, 1.5, 1, 2, 0.5, 5], [3, 0, 0, 4, 0, 3],
             "symmetric")

    print("Done.")
