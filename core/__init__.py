"""
Core scientific computation package for SPAM.

Re-exports the public API from spam_calc and spam_optimizer so callers
can use ``from core import compute_k0d`` etc.
"""

from .spam_calc import (
    solve_dispersion,
    material_to_tmatrix,
    spam_s_to_tmatrix,
    tmatrix_error,
    compute_k0d,
    mil_to_m,
    C0, EP0, MU0, ETA0,
)

from .spam_optimizer import (
    extract_material,
    extract_material_progressive,
)

__all__ = [
    "solve_dispersion",
    "material_to_tmatrix",
    "spam_s_to_tmatrix",
    "tmatrix_error",
    "compute_k0d",
    "mil_to_m",
    "C0", "EP0", "MU0", "ETA0",
    "extract_material",
    "extract_material_progressive",
]
