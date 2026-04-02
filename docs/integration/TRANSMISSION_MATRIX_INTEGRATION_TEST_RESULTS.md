# Transmission-Matrix Integration Test Results

Date: 2026-03-24
Scope: Transmission-matrix math, inverse extraction, and GUI integration path

## Scope Clarification

This file covers only transmission-matrix integration.  
Hardware ADC/RF-switch validation is tracked separately in [`INTEGRATION_TEST_RESULTS.md`](INTEGRATION_TEST_RESULTS.md).

## What Was Executed  

### 1) Forward-model and S->T validation (`tests/test_spam_calc.py`)

Executed logic:
- Loads simulated `.mat` datasets from `Simulated Spam Calculations/`
- Converts measured SPAM S-parameters to T-matrices:
  - `spam_s_to_tmatrix(S_SPAM, theta_deg)`
- Builds theoretical T-matrices from material tensors:
  - `material_to_tmatrix(erv, mrv, theta_deg, K0D)`
- Computes error:
  - `tmatrix_error(T_meas, T_theory)`

Evidence in code:
- Dataset loader and case list: `tests/test_spam_calc.py`
- S->T conversion function: `spam_calc.py`
- Forward model function: `spam_calc.py`

Result status: PASS (simulation benchmark validation)

Observed summary:
- Validation case set covers 10 simulated material files (including complex/full-tensor cases).
- Reported benchmark behavior in project notes: approximately <=0.1% relative T-matrix error vs MATLAB reference flow.

### 2) Inverse extraction validation (`tests/test_optimizer.py`)

Executed logic:
- Loads simulated SPAM data from `Simulated Spam Calculations/`
- Runs progressive extraction:
  - `extract_material_progressive(S, th, K0D, target_type=..., max_iter_per_stage=2000, callback=...)`
- Exercises staged solve path (isotropic -> diagonal -> symmetric) depending on target.

Evidence in code:
- Test harness and test cases: `tests/test_optimizer.py`
- Progressive solver implementation: `spam_optimizer.py`

Result status: PASS (representative simulated extraction cases)

Observed summary:
- Cases include isotropic-like, diagonal anisotropic, and symmetric-target extraction.
- Project benchmark notes report low fit error and low single-digit parameter recovery error on representative simulated cases.

### 3) GUI integration path verification (`GUI.py`)

Executed logic path in app:
- Sweep completion triggers extraction:
  - `self.after(100, self._run_extraction)`
- Worker runs optimizer:
  - `extract_material_progressive(...)`
- Status/debug updates and result persistence execute through the extraction worker flow.

Evidence in code:
- Sweep-to-extraction trigger and extraction worker calls: `GUI.py`

Result status: PASS (integration wiring present and exercised in simulation workflow)

## Data and Conditions

- Dataset source: `Simulated Spam Calculations/`
- Reference conditions used by tests:
  - Frequency: 24 GHz
  - Slab thickness: 60 mil

## Pass/Fail Summary

- Forward-model + S->T validation: PASS
- Progressive inverse extraction validation: PASS
- GUI extraction integration path: PASS

## Thickness Parameter Guidance (Manual Session Setting)

- Thickness is a manual extraction-session parameter in GUI Extraction Settings.
- It directly affects extraction physics through \(k_0 d\) (free-space wavenumber times slab thickness).
- The GUI now validates thickness input range (1 to 500 mil) and logs saved extraction settings with:
  - frequency (`f0_ghz`)
  - thickness (`d_mil`)
  - computed `k0d`
  - tensor type
- An advisory resonance warning is shown if the selected thickness is near quarter-wave resonance zones (heuristic check in \(k_0 d\) space). This warning is informational and does not override user input.

### Operator Checklist (Before Running Extraction)

1. Open Extraction Settings and set:
   - frequency (GHz),
   - slab thickness (mil),
   - tensor type.
2. Confirm no validation errors (thickness must be 1 to 500 mil).
3. If a resonance advisory warning appears:
   - consider adjusting thickness away from the warned zone,
   - proceed only if you intentionally want that operating point.
4. Run sweep and verify extraction debug line includes `f0`, `d`, and `k0d`.
5. After extraction, verify saved result metadata includes thickness in config.

## Known Limits

- Current validation is simulation/benchmark centered.
- Final acceptance still requires calibrated real-measurement validation against known reference material values.

## Next Acceptance Step

Run one full end-to-end extraction using calibrated real S-parameter measurements and compare extracted tensor values against a known reference sample.

