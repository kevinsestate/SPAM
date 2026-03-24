# SPAM -- Material Extraction Implementation Update

**Date:** March 2026

---

## What Was Implemented

We implemented the material property extraction system based on the "Transmission Matrix Formulation for Anisotropic Slabs" paper. This is the part that takes the raw SPAM scattering measurements and works backward to determine the permittivity and permeability tensors of the sample.

### How It Works (High Level)

The extraction has two main pieces:

**1. Forward Model** -- Given a guess at what the material properties are, predict what the SPAM measurements *should* look like. Internally this means:
- Building the 3x3 permittivity and permeability tensors from the guessed values
- Solving a quartic (4th-degree) polynomial at each incidence angle to find how waves propagate inside the slab
- Computing a 4x4 transmission matrix (the ABCD matrix) at each angle from the wave solutions

**2. Inverse Solver** -- Run the forward model thousands of times with different guesses, comparing each prediction to the actual measured data, until the best-fit material parameters are found. A numerical optimizer (Powell's method from SciPy) handles the searching.

To make the inverse problem tractable, it runs in progressive stages. Each stage uses the previous result as its starting point:

| Stage | Unknowns | What it assumes |
|-------|----------|-----------------|
| Isotropic | 2 | Material is the same in all directions |
| Diagonal | 6 | Different along x, y, z but no coupling |
| Symmetric | 12 | Full anisotropic coupling between axes |

This staged approach is critical -- jumping straight to 12 unknowns from a random guess almost never converges. Starting simple and refining works reliably.

### Validation Results

The forward model has been tested against all 10 simulated HFSS cases from the "Simulated Spam Calculations" folder. It matches the MATLAB reference code to within 0.1% relative T-matrix error across every case, including the complex-valued and full-tensor cases.

The inverse solver was tested on 3 representative cases:

| Test Case | True Material | Fit Error | Time (desktop) |
|-----------|--------------|-----------|----------------|
| Isotropic (er=2, mur=3) | Recovered within 1% | 0.08% | ~8 sec |
| Diagonal anisotropic | Recovered within 3% | 0.04% | ~10 sec |
| Full symmetric tensor | Recovered within 1.5% | 0.05% | ~20 sec |

---

## Optimization for Raspberry Pi 4B

The Pi has a 1.5 GHz ARM processor with 4 cores -- roughly 3-5x slower than a typical laptop for this kind of math. Three main optimizations were done:

**Batch linear algebra (biggest win):** The original code solved the quartic polynomial and built the transmission matrix one angle at a time in a Python loop. This has been rewritten so all 44 angles are processed in a single batch operation. Instead of 44 separate matrix inversions, there is one call that inverts all 44 matrices at once. The underlying BLAS library (the low-level math engine) is heavily optimized for exactly this kind of batch operation.

**Parallel optimizer restarts:** The solver runs multiple optimization attempts from different starting points (to avoid getting stuck in a bad local minimum). These now run across all 4 Pi cores simultaneously using Python's multiprocessing, instead of one after another.

**Tightened search space:** When moving from the isotropic stage to diagonal, the bounds for the optimizer are narrowed to +/- 50% around the isotropic solution instead of searching the entire default range. This means later stages converge faster with less wasted work.

### Expected Pi 4B Timing

Based on the desktop benchmarks and the typical 3-5x ARM slowdown:

| Extraction Target | Desktop | Estimated Pi 4B |
|-------------------|---------|-----------------|
| Diagonal (2 stages) | ~10 sec | ~30-50 sec |
| Full symmetric (3 stages) | ~20 sec | ~1-2 min |

This runs automatically after each measurement sweep completes, so the user just waits for it to finish. The GUI stays responsive during extraction.

---

## How It Connects to the Rest of the System

The extraction pipeline is fully wired into the GUI:

1. User runs a measurement sweep (0-90 degrees)
2. At each angle, the S-parameters are measured and stored in the database
3. When the sweep finishes, extraction runs automatically in the background
4. Results (permittivity/permeability tensor components and fit quality) display in the GUI info panel
5. Results are saved to the database for later review/export

The user can configure the operating frequency (default 24 GHz), slab thickness (default 60 mil), and tensor type (isotropic/diagonal/symmetric) via a settings dialog.

---

## Questions / Items for Discussion

1. **Frequency and thickness defaults** -- Currently hardcoded to 24 GHz and 60 mil. Should these be adjustable per measurement session, or are they fixed for the SPAM hardware?

2. **Which tensor type to target by default?** -- Diagonal (6 unknowns) is fast and usually sufficient. Symmetric (12 unknowns) gives more detail but takes longer and needs good measurement SNR. What do we expect for the samples being tested?

3. **Validation with real data** -- All testing so far uses HFSS simulations. Once real measurements are available, we should run the extraction on a known reference material to verify end-to-end accuracy. Do we have a reference sample with published permittivity/permeability values?

4. **Convergence monitoring** -- The fit error tells us how well the model matches the data, but a low fit error doesn't guarantee the extracted parameters are physically correct (the optimizer could find a non-physical solution that happens to fit). Should we add bounds checking or physical constraints (e.g., real parts must be positive, imaginary parts must be negative for lossy materials)?
