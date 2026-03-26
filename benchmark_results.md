# Fresh Benchmark Results (2026-03-26)

This file summarizes fresh benchmark runs executed from the current codebase.

## Reproducibility Artifacts

- Environment: `benchmark_artifacts/environment.txt`
- Forward-path output: `benchmark_artifacts/test_spam_calc_output.txt`
- Optimizer output: `benchmark_artifacts/test_optimizer_output.txt`

## Runtime Environment

- OS: Windows-11-10.0.26200-SP0
- Python: 3.14.2 (MSC v.1944 64-bit)
- CPU: AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD
- Working directory: `C:\Users\Kevin\Downloads\SPAM-main\SPAM`

## Commands Executed

```powershell
python test_spam_calc.py
python test_optimizer.py
```

## A) Forward Path Benchmark (`test_spam_calc.py`)

Configuration used by script:
- Frequency = 24 GHz
- Thickness = 60 mil
- Angle samples = 44 (2 deg to 88 deg)
- Dataset folder = `Simulated Spam Calculations/`

### Per-case T-matrix error summary

| Dataset | Mean relative error | Max relative error |
|---|---:|---:|
| SPAM_Scat_Mat_er2_mur3 | 0.001484 | 0.003479 |
| SPAM_Scat_Mat_er225_mur333 | 0.000689 | 0.002004 |
| SPAM_Scat_Mat_er225_mur343 | 0.000707 | 0.002011 |
| SPAM_Scat_Mat_er201205_mur343 | 0.000684 | 0.001971 |
| SPAM_Scat_Mat_er210205_mur343 | 0.000742 | 0.001926 |
| SPAM_Scat_Mat_er200215_mur343 | 0.000529 | 0.001520 |
| SPAM_Scat_Mat_er201205_allj_mur343_allj | 0.001777 | 0.003064 |
| SPAM_Scat_Mat_erfull_murdiag | 0.000753 | 0.001964 |
| SPAM_Scat_Mat_erfull_murfull | 0.000609 | 0.002027 |
| SPAM_Scat_Mat_erfull_murfull_cutoff | 0.001669 | 0.004535 |

Aggregate:
- Mean of mean errors: **0.0009643**
- Worst-case max error: **0.004535**

## B) Inverse Benchmark (`test_optimizer.py`)

Configuration used by script:
- `K0D = compute_k0d(24e9, mil_to_m(60))`
- `max_iter_per_stage = 2000`
- Cases: isotropic-like, diagonal, symmetric target

### Per-case extraction summary

| Test case | Fit error | Max \|erv error\| | Max \|mrv error\| | Elapsed (s) |
|---|---:|---:|---:|---:|
| Test 1: isotropic (er2_mur3 -> diagonal) | 0.000842 | 0.0031 | 0.0100 | 7.1 |
| Test 2: diagonal (er225_mur343 -> diagonal) | 0.000438 | 0.0331 | 0.0058 | 9.0 |
| Test 3: full symmetric (erfull_murdiag -> symmetric) | 0.000548 | 1.3861 | 0.8351 | 17.7 |

Aggregate:
- Mean fit error across cases: **0.0006093**
- Total elapsed across cases: **33.8 s**

## Notes

- Both benchmark scripts completed successfully with exit code 0.
- Benchmark artifact files were captured by PowerShell redirection and are UTF-16 encoded.
- The symmetric case achieves low fit error but shows larger tensor-parameter deviation than diagonal/isotropic cases, consistent with higher nonconvexity and parameter coupling.
