"""
Calibration math for SPAM voltage → S-parameter conversion.

Reference: 26_03_31_Cal_Approx_SPAM.pdf (Pages C1–C3).

Two calibration sweeps provide per-angle reference voltages:
  T(θ) — through (no material, TX detector)
  G(θ) — reflect (metal sheet, RX detector)

Inversion formulas (boxed on PDF page C3):
  τ_m  = (V₂⁻ / T) · exp(−j k₀ d / cos θ)          → S₂₁
  Γ_m  = (−V₃⁻ / G) · exp(−j k₀ (d − d_sheet) / cos θ)  → S₁₁

Where:
  V₂⁻  = measured TX-detector complex voltage (material in place)
  V₃⁻  = measured RX-detector complex voltage (material in place)
  d     = coupler separation distance  [m]
  d_sheet = distance from reference plane to sheet  [m]
  k₀    = free-space wavenumber  [rad/m]
  θ     = incidence angle  [degrees, converted internally]
"""

import numpy as np

from core.spam_calc import C0


def compute_k0(f_hz):
    """Return free-space wavenumber k₀ = 2π f / c₀  [rad/m]."""
    return 2.0 * np.pi * f_hz / C0


def compute_tau_m(V2, T, k0, d, theta_deg):
    """Calibrated transmission coefficient S₂₁ (τ_m).

    Parameters
    ----------
    V2 : complex or ndarray
        Measured TX-detector voltage(s) with material in place.
    T : complex or ndarray
        Through reference voltage(s) — same shape as *V2* or scalar.
    k0 : float
        Free-space wavenumber [rad/m].
    d : float
        Coupler separation distance [m].
    theta_deg : float or ndarray
        Incidence angle(s) in degrees.

    Returns
    -------
    complex or ndarray
        Calibrated S₂₁.
    """
    theta_rad = np.deg2rad(np.asarray(theta_deg, dtype=float))
    cos_th = np.cos(theta_rad)
    phase_corr = np.exp(-1j * k0 * d / cos_th)
    return (np.asarray(V2, dtype=complex) / np.asarray(T, dtype=complex)) * phase_corr


def compute_gamma_m(V3, G, k0, d, d_sheet, theta_deg):
    """Calibrated reflection coefficient S₁₁ (Γ_m).

    Parameters
    ----------
    V3 : complex or ndarray
        Measured RX-detector voltage(s) with material in place.
    G : complex or ndarray
        Reflect reference voltage(s) — same shape as *V3* or scalar.
    k0 : float
        Free-space wavenumber [rad/m].
    d : float
        Coupler separation distance [m].
    d_sheet : float
        Distance from reference plane to sheet [m].
    theta_deg : float or ndarray
        Incidence angle(s) in degrees.

    Returns
    -------
    complex or ndarray
        Calibrated S₁₁.
    """
    theta_rad = np.deg2rad(np.asarray(theta_deg, dtype=float))
    cos_th = np.cos(theta_rad)
    phase_corr = np.exp(-1j * k0 * (d - d_sheet) / cos_th)
    return (-np.asarray(V3, dtype=complex) / np.asarray(G, dtype=complex)) * phase_corr


def lookup_cal_voltage(cal_dict, angle):
    """Look up calibration voltage for the nearest stored angle.

    Parameters
    ----------
    cal_dict : dict
        Mapping {angle_float: complex_voltage}.
    angle : float
        Target angle in degrees.

    Returns
    -------
    complex
        Voltage for the nearest calibration angle.
    """
    if not cal_dict:
        return None
    nearest = min(cal_dict.keys(), key=lambda a: abs(a - angle))
    return cal_dict[nearest]
