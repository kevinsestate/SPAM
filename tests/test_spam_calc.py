"""
Validation of spam_calc.py against MATLAB reference data.

Loads the simulated HFSS .mat files, computes T-matrices via both paths
(forward model and S-parameter conversion), and reports the error profile
that should reproduce MATLAB's Compare_Tmat.m output.

Usage:
    python tests/test_spam_calc.py
"""

import os
import numpy as np
import scipy.io as sio

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.spam_calc import (
    material_to_tmatrix,
    spam_s_to_tmatrix,
    tmatrix_error,
    compute_k0d,
    mil_to_m,
)

# ---------------------------------------------------------------------------
# Physical / experiment parameters  (must match Compare_Tmat.m)
# ---------------------------------------------------------------------------
F0 = 24e9          # 24 GHz
D_MIL = 60         # slab thickness in mils
D_M = mil_to_m(D_MIL)
K0D = compute_k0d(F0, D_M)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..",
                        "Simulated Spam Calculations")

# ---------------------------------------------------------------------------
# Test cases – (filename, erv, mrv) tuples from Compare_Tmat.m
# ---------------------------------------------------------------------------
TEST_CASES = [
    ("SPAM_Scat_Mat_er2_mur3.mat",
     [2, 0, 0, 2, 1e-6, 2],
     [3, 0, 0, 3, 0, 3]),

    ("SPAM_Scat_Mat_er225_mur333.mat",
     [2, 0, 0, 2, 0, 5],
     [3, 0, 0, 3, 0, 3]),

    ("SPAM_Scat_Mat_er225_mur343.mat",
     [2, 0, 0, 2, 0, 5],
     [3, 0, 0, 4, 0, 3]),

    ("SPAM_Scat_Mat_er201205_mur343.mat",
     [2, 0, 1, 2, 0, 5],
     [3, 0, 0, 4, 0, 3]),

    ("SPAM_Scat_Mat_er210205_mur343.mat",
     [2, 1, 0, 2, 0, 5],
     [3, 0, 0, 4, 0, 3]),

    ("SPAM_Scat_Mat_er200215_mur343.mat",
     [2, 0, 0, 2, 1, 5],
     [3, 0, 0, 4, 0, 3]),

    ("SPAM_Scat_Mat_er201205_allj_mur343_allj.mat",
     np.array([2, 0, 1, 2, 0, 5]) * (1 - 1j),
     np.array([3, 0, 0, 4, 0, 3]) * (1 - 1j)),

    ("SPAM_Scat_Mat_erfull_murdiag.mat",
     [2, 1.5, 1, 2, 0.5, 5],
     [3, 0, 0, 4, 0, 3]),

    ("SPAM_Scat_Mat_erfull_murfull.mat",
     [2, 1.5, 1, 2, 0.5, 5],
     [1.25, 1, 0.5, 4, 0.75, 3]),

    ("SPAM_Scat_Mat_erfull_murfull_cutoff.mat",
     [2, 1.5, 1, 2, 0.5, 5],
     [3, 1, 0, 4, 2, 1]),
]


def load_mat(fname):
    """Load S_SPAM and theta_deg from a MATLAB .mat file.

    Returns S_SPAM with shape (Ntheta, 4, 4) and theta_deg as 1-D array.
    """
    path = os.path.join(DATA_DIR, fname)
    data = sio.loadmat(path)
    S_SPAM_matlab = data["S_SPAM"]           # (4, 4, Ntheta) from MATLAB
    theta_deg = data["theta_deg"].ravel()    # (Ntheta,)
    S_SPAM = np.transpose(S_SPAM_matlab, (2, 0, 1))   # → (Ntheta, 4, 4)
    return S_SPAM, theta_deg


def run_test(fname, erv, mrv, verbose=True):
    """Run a single forward-model vs measurement comparison.

    Returns per-angle error array and mean error.
    """
    S_SPAM, theta_deg = load_mat(fname)

    T_meas = spam_s_to_tmatrix(S_SPAM, theta_deg)
    T_theory = material_to_tmatrix(erv, mrv, theta_deg, K0D)
    err, mean_err = tmatrix_error(T_meas, T_theory)

    if verbose:
        short = os.path.splitext(fname)[0]
        print(f"\n{'=' * 60}")
        print(f"  {short}")
        print(f"  erv = {np.array(erv)}")
        print(f"  mrv = {np.array(mrv)}")
        print(f"{'=' * 60}")
        print(f"  Angles : {theta_deg[0]:.0f}° – {theta_deg[-1]:.0f}°  "
              f"({len(theta_deg)} points)")
        print(f"  Mean relative T-matrix error : {mean_err:.6f}")
        print(f"  Max  relative T-matrix error : {np.max(err):.6f}")
        print(f"  Min  relative T-matrix error : {np.min(err):.6f}")

    return err, mean_err


def main():
    print("=" * 60)
    print("  SPAM T-Matrix Validation")
    print(f"  f0 = {F0/1e9:.1f} GHz,  d = {D_MIL} mil,  k0d = {K0D:.6f}")
    print("=" * 60)

    results = []
    skipped = []

    for fname, erv, mrv in TEST_CASES:
        path = os.path.join(DATA_DIR, fname)
        if not os.path.isfile(path):
            skipped.append(fname)
            continue
        err, mean_err = run_test(fname, erv, mrv)
        results.append((fname, mean_err, np.max(err)))

    if skipped:
        print(f"\nSkipped (file not found): {skipped}")

    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    for fname, mean_e, max_e in results:
        tag = os.path.splitext(fname)[0]
        print(f"  {tag:50s}  mean={mean_e:.6f}  max={max_e:.6f}")


if __name__ == "__main__":
    main()
