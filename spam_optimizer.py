"""Backward-compatibility shim — real code lives in core.spam_optimizer."""
from core.spam_optimizer import *  # noqa: F401,F403
from core.spam_optimizer import (
    extract_material,
    extract_material_progressive,
    _pack_params,
    _unpack_params,
    _default_guess,
    _default_bounds,
    _cost,
    _run_powell,
    _powell_worker,
    _tighten_bounds,
    _GOOD_FIT,
    _N_WORKERS,
)
