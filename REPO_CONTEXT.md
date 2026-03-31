# REPO_CONTEXT

Last updated: 2026-03-26 (post-refactor)
Purpose: fast handoff context for new agents and maintainers.

## Agent Update Protocol (Required)

After every substantial task, update this file in one pass:

1. Update `Last updated` date.
2. Add one entry to **Decision Log** (newest first) with:
   - what changed,
   - affected files,
   - verification performed,
   - remaining risks/follow-ups.
3. If architecture, commands, or active-status changed, update those sections too.

Rules:
- Keep facts only (no speculative claims).
- Summarize and link; do not duplicate full documents.
- Keep this readable in under 2 minutes.

---

## Project Snapshot

SPAM is a local desktop app for scanning polarized anisotropic materials and extracting electromagnetic material tensors from SPAM measurements. The current workflow is measurement sweep -> database persistence -> transmission-matrix-based extraction -> GUI display + saved extraction record.

Runtime entrypoints:
- `start_spam.bat` (Windows) -> launches `python GUI.py`
- `start_spam.sh` (Linux/Raspberry Pi) -> launches `python3 GUI.py`

Active runtime path:
- Main app: `GUI.py` -> `app.py` (thin entry point delegates to mixin-assembled `SPAMGui`)
- GUI mixins: `gui/` (widgets, config, hardware, measurement, extraction, graphs, callbacks, panels/, dialogs/)
- Core extraction math: `core/spam_calc.py`, `core/spam_optimizer.py` (root shims for backward compat)
- Persistence: `backend/` (relative imports, re-exports from `__init__.py`)
- Hardware integration: `hardware/`
- Tests: `tests/`

---

## Active Architecture Map

### Core modules

- `GUI.py` -> `app.py`
  - `GUI.py` is now a thin entry point that imports from `app.py`.
  - `app.py` assembles `SPAMGui` from mixin classes in `gui/`.
- `gui/` package (mixin-based architecture):
  - `themes.py` - Theme palettes and font constants
  - `widgets.py` - Styled widget factory (WidgetsMixin)
  - `config.py` - Config persistence (ConfigMixin)
  - `hardware_mixin.py` - Hardware init and motor control (HardwareMixin)
  - `db_helpers.py` - Database CRUD helpers (DBMixin)
  - `measurement.py` - Measurement sweep worker (MeasurementMixin)
  - `extraction.py` - Material extraction worker (ExtractionMixin)
  - `graphs.py` - Center panel graphs (GraphsMixin)
  - `callbacks.py` - Status, calibrate, export, help (CallbacksMixin)
  - `debug_console.py` - Standalone DebugConsole Toplevel
  - `panels/` - menu.py, status_bar.py, sidebar.py, detail_panel.py
  - `dialogs/` - base.py, extraction_dlg.py, parameters_dlg.py, connection_dlg.py
- `core/` package:
  - `spam_calc.py` - Forward model and S->T conversion
  - `spam_optimizer.py` - Progressive inverse extraction
  - Root-level `spam_calc.py` and `spam_optimizer.py` are backward-compat shims.
- `backend/database.py`, `backend/models.py`
  - SQLite models; uses relative imports; `backend/__init__.py` re-exports public API.
- `hardware/ad7193.py`, `hardware/rf_switch.py`
  - ADC and switch control with simulation fallback.

### Data flow

1. GUI collects/creates per-angle measurement data.
2. Measurements are written to SQLite.
3. On sweep completion, extraction is launched in background thread.
4. `k0d` is built from frequency + thickness; optimizer solves tensor parameters.
5. Fit/summary values update in GUI and extraction record is persisted.

---

## Current Feature Status

### Transmission-matrix integration

Status: implemented and benchmarked on simulated datasets.

Key files:
- `TRANSMISSION_MATRIX_INTEGRATION_TEST_RESULTS.md`
- `benchmark_results.md`
- `benchmark_report.tex` (Overleaf-ready academic report)
- `benchmark_artifacts/` (raw outputs + environment)

Latest fresh benchmark snapshot (2026-03-26):
- Forward (10 datasets): mean-of-means error `0.0009643`, worst-case max `0.004535`
- Inverse (3 cases): mean fit error `0.0006093`, total elapsed `33.8 s`

### Thickness parameter (manual mode)

Status: implemented in GUI extraction settings.

Behavior:
- Manual thickness input with validation (`1-500 mil`)
- Resonance-risk advisory warning based on `k0d` proximity to quarter-wave zones
- Settings persisted in config:
  - `extraction_f0_ghz`
  - `extraction_d_mil`
  - `extraction_tensor_type`
- Extraction logs include `f0`, `d_mil`, `k0d`, `tensor_type`
- Extraction DB metadata includes `k0d`

### ADC/switch integration

Status: software + simulation path validated; full hardware-in-loop validation pending.

Reference:
- `INTEGRATION_TEST_RESULTS.md` (hardware-only scope)

### Active vs archived

- Active code/data paths are in root + `core/` + `gui/` + `backend/` + `hardware/` + `tests/` + `Simulated Spam Calculations/`.
- Archived non-active artifacts are under `archive/legacy/` (includes `motor_control_status.py`) and are not launch targets.

---

## Operations and Testing Quickstart

### Run app

Windows:
```powershell
.\start_spam.bat
```

Linux/RPi:
```bash
./start_spam.sh
```

### Run extraction benchmarks

```powershell
python tests/test_spam_calc.py
python tests/test_optimizer.py
```

### Benchmark/report artifacts

- Raw outputs: `benchmark_artifacts/`
- Parsed summary: `benchmark_results.md`
- Academic report: `benchmark_report.tex`

### Pi ADC bring-up helpers

- Runbook: `scripts/pi/PI_ADC_BRINGUP.md`
- Low-level checker: `python scripts/pi/check_adc_lowlevel.py --seconds 15 --rate-hz 10`
- First-field log template: `scripts/pi/PI_FIRST_FIELD_TEST_LOG_TEMPLATE.md`

---

## Decision Log (Newest First)

### 2026-03-26 - Added Pi ADC bring-up runbook and low-level checker
- Changed:
  - Added `scripts/pi/PI_ADC_BRINGUP.md` (step-by-step wiring, Pi prep, GUI/extraction verification)
  - Added `scripts/pi/check_adc_lowlevel.py` (AD7193 low-level finite/timeout/statistics checker)
  - Added `scripts/pi/PI_FIRST_FIELD_TEST_LOG_TEMPLATE.md` (baseline field-test capture template)
- Verified:
  - Script executes in simulation mode and reports expected warning when not on Pi
  - No linter diagnostics for new files
- Risks/follow-up:
  - Physical wiring and SPI validation must be executed on actual Pi hardware.

### 2026-03-26 - GUI split refactor + modular architecture
- Changed:
  - Split monolithic `GUI.py` (1751 lines) into mixin classes under `gui/` package
  - Moved `spam_calc.py` and `spam_optimizer.py` into `core/` package with root shims
  - Fixed `backend/models.py` to use relative imports; added re-exports in `backend/__init__.py`
  - Created `app.py` to assemble `SPAMGui` from mixins; `GUI.py` is now thin entry point
  - Moved tests to `tests/` directory with updated imports
  - Moved `motor_control_status.py` to `archive/legacy/`
- Verified:
  - All files created with correct imports and structure
  - Launch scripts unchanged (`start_spam.bat`/`.sh` still target `GUI.py`)
- Risks/follow-up:
  - Smoke test all imports and run test suite to confirm no regressions
  - Theme hot-reload still requires restart (unchanged behavior)

### 2026-03-26 - Added benchmark report package and fresh reruns
- Changed:
  - Added `benchmark_results.md`
  - Added `benchmark_report.tex`
  - Captured fresh outputs in `benchmark_artifacts/`
- Verified:
  - Fresh benchmark scripts reran successfully and metrics extracted.
- Risks/follow-up:
  - Local `pdflatex` not installed; compile check should be done in Overleaf.

### 2026-03-26 - Decoupled RF switch from critical measurement path
- Changed:
  - `GUI.py`: RF switch control is now optional and disabled by default (`enable_rf_switch=0`)
  - `GUI.py`: ADC-only real-read mode now works without requiring app-controlled SP2T
  - `GUI.py`: connection setup includes `Enable RF Switch Control (0/1)`
- Verified:
  - preserves optional RF switch path while allowing ADC + extraction flow without switch dependency
- Risks/follow-up:
  - In ADC-only mode, external RF path state must be coordinated outside the app for correct S11/S21 interpretation.

### 2026-03-26 - Implemented manual thickness parameter upgrade
- Changed:
  - `GUI.py`: thickness visibility in info panel, robust validation, resonance advisory, settings persistence, extraction trace logging with `k0d`
  - `TRANSMISSION_MATRIX_INTEGRATION_TEST_RESULTS.md`: operator guidance/checklist
- Verified:
  - `GUI.py` import smoke test passed
  - no linter diagnostics on changed files
- Risks/follow-up:
  - Resonance advisory is heuristic; tune thresholds with real measurement campaigns.

### 2026-03-26 - Repository cleanup and archive structure
- Changed:
  - Moved non-active artifacts to `archive/legacy/`
  - Updated `README.md` active-vs-archive guidance
- Verified:
  - launch scripts still target `GUI.py`
  - test imports and GUI import pass
- Risks/follow-up:
  - Keep `Simulated Spam Calculations/` present for benchmark scripts.

---

## Open Issues / Next Priorities

1. Run smoke test on all imports and test suite to verify refactor integrity.
2. Perform full Raspberry Pi hardware-in-loop validation for AD7193 + RF switch.
3. Validate extraction against calibrated real material reference sample(s).
4. Decide whether to keep/add physical constraints in symmetric extraction to reduce parameter ambiguity.
5. Keep this file updated after each substantial task.
