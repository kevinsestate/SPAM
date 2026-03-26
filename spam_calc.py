"""Backward-compatibility shim — real code lives in core.spam_calc."""
from core.spam_calc import *  # noqa: F401,F403
from core.spam_calc import (
    solve_dispersion,
    material_to_tmatrix,
    spam_s_to_tmatrix,
    tmatrix_error,
    compute_k0d,
    mil_to_m,
    C0, EP0, MU0, ETA0,
    _dispersion_internals,
)
