"""
Unit tests for core.calibration — voltage → S-parameter conversion.

Tests verify the inversion formulas from 26_03_31_Cal_Approx_SPAM.pdf (page C3):
  τ_m  = (V₂⁻ / T) · exp(−j k₀ d / cos θ)
  Γ_m  = (−V₃⁻ / G) · exp(−j k₀ (d − d_sheet) / cos θ)
"""

import sys
import os
import math
import unittest

import numpy as np

# Ensure repo root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.calibration import compute_k0, compute_tau_m, compute_gamma_m, lookup_cal_voltage
from core.spam_calc import C0


class TestComputeK0(unittest.TestCase):
    def test_known_frequency(self):
        f_hz = 24e9
        k0 = compute_k0(f_hz)
        expected = 2.0 * np.pi * f_hz / C0
        self.assertAlmostEqual(k0, expected, places=6)

    def test_zero_frequency(self):
        self.assertEqual(compute_k0(0.0), 0.0)


class TestComputeTauM(unittest.TestCase):
    """Test calibrated S₂₁ (transmission)."""

    def test_identity_when_no_material(self):
        """Through measurement with no material should give τ_m ≈ 1."""
        # V₂⁻ = T (no material → τ=1), d=0 → phase correction = 1
        T = complex(0.5, 0.3)
        V2 = T  # same as through reference
        tau = compute_tau_m(V2, T, k0=0.0, d=0.0, theta_deg=0.0)
        self.assertAlmostEqual(abs(tau), 1.0, places=10)

    def test_half_transmission(self):
        """If V₂⁻ = T/2, τ_m should be 0.5 (d=0)."""
        T = complex(1.0, 0.0)
        V2 = complex(0.5, 0.0)
        tau = compute_tau_m(V2, T, k0=0.0, d=0.0, theta_deg=0.0)
        self.assertAlmostEqual(abs(tau), 0.5, places=10)

    def test_phase_correction(self):
        """Phase correction exp(-j k0 d / cos θ) should rotate the result."""
        T = complex(1.0, 0.0)
        V2 = complex(1.0, 0.0)
        k0 = compute_k0(24e9)
        d = 0.01  # 1 cm
        theta = 0.0
        tau = compute_tau_m(V2, T, k0, d, theta)
        # |τ| should still be 1, but phase should be -k0*d
        self.assertAlmostEqual(abs(tau), 1.0, places=10)
        expected_phase = -k0 * d
        actual_phase = np.angle(tau)
        # Wrap to [-π, π]
        diff = (expected_phase - actual_phase + np.pi) % (2 * np.pi) - np.pi
        self.assertAlmostEqual(diff, 0.0, places=6)

    def test_oblique_angle(self):
        """At oblique angle, path length increases by 1/cos(θ)."""
        T = complex(1.0, 0.0)
        V2 = complex(1.0, 0.0)
        k0 = compute_k0(24e9)
        d = 0.005
        theta = 30.0
        tau = compute_tau_m(V2, T, k0, d, theta)
        expected_phase = -k0 * d / np.cos(np.deg2rad(theta))
        actual_phase = np.angle(tau)
        diff = (expected_phase - actual_phase + np.pi) % (2 * np.pi) - np.pi
        self.assertAlmostEqual(diff, 0.0, places=6)

    def test_array_input(self):
        """Should work with numpy arrays."""
        T = np.array([1.0 + 0j, 1.0 + 0j])
        V2 = np.array([0.5 + 0j, 0.8 + 0.1j])
        tau = compute_tau_m(V2, T, k0=0.0, d=0.0, theta_deg=np.array([0.0, 10.0]))
        self.assertEqual(tau.shape, (2,))
        self.assertAlmostEqual(abs(tau[0]), 0.5, places=10)


class TestComputeGammaM(unittest.TestCase):
    """Test calibrated S₁₁ (reflection)."""

    def test_perfect_reflector(self):
        """Metal sheet: V₃⁻ = G (reflect reference), Γ should be -(-G/G) = 1 magnitude."""
        # G is the reflect reference (already has the -1 baked in from metal sheet).
        # If material reflects same as metal → Γ_m = -V3/G * phase = -G/G = -1 (for d=d_sheet=0)
        # But for a perfect metal (Γ = -1), V₃⁻ = G, so Γ_m = -G/G = -1+0j
        # which has |Γ| = 1.
        G = complex(0.7, -0.2)
        V3 = G
        gamma = compute_gamma_m(V3, G, k0=0.0, d=0.0, d_sheet=0.0, theta_deg=0.0)
        self.assertAlmostEqual(abs(gamma), 1.0, places=10)

    def test_no_reflection(self):
        """If V₃⁻ = 0 (no reflection), Γ_m = 0."""
        G = complex(1.0, 0.0)
        V3 = complex(0.0, 0.0)
        gamma = compute_gamma_m(V3, G, k0=0.0, d=0.0, d_sheet=0.0, theta_deg=0.0)
        self.assertAlmostEqual(abs(gamma), 0.0, places=10)

    def test_phase_correction_with_geometry(self):
        """Phase correction uses (d - d_sheet) / cos θ."""
        G = complex(1.0, 0.0)
        V3 = complex(1.0, 0.0)
        k0 = compute_k0(24e9)
        d = 0.02
        d_sheet = 0.01
        theta = 0.0
        gamma = compute_gamma_m(V3, G, k0, d, d_sheet, theta)
        self.assertAlmostEqual(abs(gamma), 1.0, places=10)
        expected_phase = -k0 * (d - d_sheet) + np.pi  # -V3/G adds π
        actual_phase = np.angle(gamma)
        diff = (expected_phase - actual_phase + np.pi) % (2 * np.pi) - np.pi
        self.assertAlmostEqual(diff, 0.0, places=6)


class TestLookupCalVoltage(unittest.TestCase):
    def test_exact_match(self):
        cal = {0.0: 1 + 0j, 5.0: 0.9 + 0.1j, 10.0: 0.8 + 0.2j}
        self.assertEqual(lookup_cal_voltage(cal, 5.0), 0.9 + 0.1j)

    def test_nearest_angle(self):
        cal = {0.0: 1 + 0j, 10.0: 0.5 + 0j}
        result = lookup_cal_voltage(cal, 7.0)
        self.assertEqual(result, 0.5 + 0j)  # 7 is closer to 10 than 0

    def test_empty_dict(self):
        self.assertIsNone(lookup_cal_voltage({}, 5.0))


class TestRoundTrip(unittest.TestCase):
    """Round-trip: synthesize voltages from known S-params, then recover them."""

    def test_dielectric_slab_round_trip(self):
        """For a known dielectric slab, compute expected S₂₁ and S₁₁,
        synthesize what the ADC would measure, then recover via inversion."""
        eps_r = 4.0
        f_hz = 24e9
        k0 = compute_k0(f_hz)
        d_slab = 60.0 / 39.37 * 1e-3  # 60 mil in metres
        theta_deg = 0.0

        # Expected S-params for dielectric slab at normal incidence (TE)
        beta = k0 * np.sqrt(eps_r)  # in-medium propagation constant
        Zd_over_Z0 = 1.0 / np.sqrt(eps_r)  # ratio of TE impedances
        r = Zd_over_Z0
        denom = 2 * np.cos(beta * d_slab) + 1j * (r + 1.0 / r) * np.sin(beta * d_slab)
        S21_expected = 2.0 / denom
        S11_expected = 1j * (r - 1.0 / r) * np.sin(beta * d_slab) / denom

        # Synthesize measured voltages (assuming d=d_sheet=0 for simplicity,
        # so phase correction is identity)
        T_ref = complex(1.0, 0.0)   # through reference
        G_ref = complex(-1.0, 0.0)  # reflect reference (metal, Γ=-1)

        # V₂⁻ = τ_m · T · exp(j 2k₀ℓ)  with ℓ→0: V₂⁻ = S₂₁ · T
        V2 = S21_expected * T_ref
        # V₃⁻ = -Γ_m · G · exp(...)  with d=d_sheet=0: V₃⁻ = -Γ_m · G → Γ_m = -V₃⁻/G
        # So V₃⁻ = -S₁₁ · G
        V3 = -S11_expected * G_ref

        # Recover via calibration functions
        tau_recovered = compute_tau_m(V2, T_ref, k0=0.0, d=0.0, theta_deg=theta_deg)
        gamma_recovered = compute_gamma_m(V3, G_ref, k0=0.0, d=0.0, d_sheet=0.0, theta_deg=theta_deg)

        self.assertAlmostEqual(abs(tau_recovered - S21_expected), 0.0, places=10)
        self.assertAlmostEqual(abs(gamma_recovered - S11_expected), 0.0, places=10)


if __name__ == '__main__':
    unittest.main()
