# REPO_CONTEXT

Last updated: 2026-04-13 (expo polish, servo calibration, GUI fixes)
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
- Documentation: `docs/` (see `docs/README.md` — handoff, benchmarks, integration reports, hardware reference PDFs)

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
- `hardware/ad7193.py`, `hardware/rf_switch.py`, `hardware/servo.py`
  - ADC (SPI), switch control, and HPS-2518MG servo — all with simulation fallback.
- `scripts/pi/`
  - Pi-only ADC/SPI helpers: `check_adc_lowlevel.py`, `live_adc_view.py`, `adc_fast_capture.py`
  - Servo calibration: `servo_test.py` — interactive pulse-width finder (scan/sweep/setmin/setmax)
  - C++ (build on Pi): `spi_ad7193_benchmark.cpp` (raw SPI rate), `ad7193_cpp_benchmark.cpp` (full AD7193 protocol + pair/s benchmark)

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
- `docs/integration/TRANSMISSION_MATRIX_INTEGRATION_TEST_RESULTS.md`
- `docs/benchmarks/benchmark_results.md`
- `docs/benchmarks/benchmark_report.tex` (Overleaf-ready academic report)
- `docs/benchmarks/artifacts/` (raw outputs + environment)

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
- `docs/integration/INTEGRATION_TEST_RESULTS.md` (hardware-only scope)

## Current Truth (As of Latest Run)

- AD7193 SPI communication is validated on Pi with stable ID reads (`0xA2`) and finite I/Q values.
- Required AD7193 driver expectations:
  - ID check should validate low nibble (`0xX2`), not upper nibble.
  - Mode writes must set internal clock bits (`CLK1=1`, `CLK0=0`) so conversions complete.
  - Differential channel select uses CH0/CH1 bit positions in config (`0x0100`, `0x0200`).
  - REFIN1 selection is used for the Pmod AD5 default reference path.
- **Current ADC config**: `adc_data_rate=4800`, `spi_speed=4000000`, `adc_samples_per_point=8`. Achieves ~300+ samp/s in background stream mode; ~8 samples averaged per sweep measurement point.
- **Output data rate knob**: `configure(gain, data_rate)` in `hardware/ad7193.py` maps requested Hz → FS (`MCLK/1024/FS`). GUI: **Connection Setup → Data Rate (Hz)** / `spam_config.json` key `adc_data_rate`. Higher values → faster ODR, more noise / less line-frequency rejection.
- **Background ADC stream**: enabled via View → Toggle ADC Voltage Graph. Runs a daemon thread calling `read_iq_stream()` continuously, protected by `_adc_lock`. Displays live voltage oscilloscope and real samp/s in the graph panel. Stream pauses only when graph is disabled or app closes.
- **Motor control**: GPIO ISR edge detection fails on this Pi kernel (`Failed to add edge detection`). Fallback is two-phase I2C polling of MCU status register 0x00: wait for bit 0x02 to clear (motor started), then wait for it to set (motor arrived). Confirmed against Arduino firmware in `motor_control_status.py`. Collision detection (bit 0x01) disabled in polling path — appears during normal movement.
- **Sweep throughput**: ~0.15-0.25 meas/s, bottlenecked by motor travel time (~2-4s per 5° step), not ADC speed.
- **spidev ioctl**: `SPI_IOC_MESSAGE` success is **non-negative** return; treating `== 0` only as success breaks transfers on some Pi kernels (fixed in `ad7193_cpp_benchmark.cpp`).
- GUI ADC-only measurement path is operational on Pi without motor/RF switch app control.
- Extraction caveat: calibrated voltage→S-param conversion is implemented (`core/calibration.py`). Requires Through+Reflect calibration sweep before material measurements. Geometry constants `cal_d_m` and `cal_d_sheet_m` default to 0 — **must be measured and configured for the hardware rig** (Settings → Connection Setup).

## Who Owns What

- You (integration owner):
  - ADC bring-up and wiring validation
  - AD7193 driver + GUI acquisition path
  - Pi runbook execution and hardware sanity checks
- Teammate (math owner):
  - Calibrated voltage->S-parameter conversion — **merged** (core/calibration.py)
  - Calibration model/fit integration into extraction pipeline — **merged** (gui/callbacks.py, gui/measurement.py)

## Next Chat Bootstrap Checklist

1. Read this file plus `docs/HANDOFF_STATUS.md` and `docs/README.md` (doc index).
2. Confirm `hardware/ad7193.py` includes low-nibble ID check and internal-clock mode writes.
3. Re-run short Pi ADC loop and confirm no channel timeouts + finite I/Q.
4. Treat extraction outputs as provisional until teammate calibration math is merged.
5. Continue from handoff "Immediate Next Steps" in `docs/HANDOFF_STATUS.md`.

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

- Raw outputs: `docs/benchmarks/artifacts/`
- Parsed summary: `docs/benchmarks/benchmark_results.md`
- Academic report: `docs/benchmarks/benchmark_report.tex`

### Pi ADC bring-up helpers

- Runbook: `scripts/pi/PI_ADC_BRINGUP.md`
- Low-level checker: `python scripts/pi/check_adc_lowlevel.py --seconds 15 --rate-hz 10`
- Live viewer / benchmark: `python scripts/pi/live_adc_view.py --help` (use `--data-rate`, `--benchmark-raw`, `--result-json`; no placeholder `...` args)
- C++ (compile on Pi): `scripts/pi/spi_ad7193_benchmark.cpp`, `scripts/pi/ad7193_cpp_benchmark.cpp` — see file headers for `g++ -O3` lines
- First-field log template: `scripts/pi/PI_FIRST_FIELD_TEST_LOG_TEMPLATE.md`

---

## Decision Log (Newest First)

### 2026-04-13 - Expo fixes: export, cal guard, motor reset, servo GPIO UI, cal status, log file
- Changed:
  - `gui/callbacks.py`: export now includes all S-param fields (tx/rx power+phase, polarization) in chronological order; JSON export appends latest extraction result block; help text updated to "Version 2.0 — Expo Build"; `_log_debug` appends to `~/SPAM/spam_run.log` (append mode, survives crashes); `_update_status` tracks `_last_status_type`.
  - `gui/measurement.py`: extraction only auto-fires after sweep if `cal_through` is populated — otherwise logs warning and sets `extraction_status_var = "No Cal Data"`; all exit paths (success, stop, early abort) now reset `motor_position_var` → `0.0°` and `motor_status_var` → `Ready`.
  - `gui/dialogs/connection_dlg.py`: added `Servo GPIO Pin (BCM)` field to Motor Controller section.
  - `gui/config.py`: added `servo_gpio: '18'` default.
  - `gui/panels/detail_panel.py`: added `cal_status_var` StringVar and `Cal Data` row in Measurement section.
  - `gui/graphs.py`: `_update_display` updates `cal_status_var` (✓ HH loaded / ⚠ Through only / ✗ None); resets status dot to green when idle and no recent error/warning.
- Verified:
  - All changes committed and pushed (commit `bd76a72`).
- Risks/follow-up:
  - Cal status only shows HH (pol-0) loaded; dual-pol calibration not yet implemented.
  - Log file grows unboundedly on very long sessions; no rotation implemented yet.

### 2026-04-13 - Servo calibration and jitter fix
- Changed:
  - `hardware/servo.py`: calibrated pulse widths to **850µs = 0° (horizontal)**, **1800µs = 90° (vertical)**; angle math changed from 0–180° to 0–90° range (`angle / 90.0` factor); init no longer sends pulse on startup (sends 0 = PWM disabled); `move_to()` releases PWM signal (sends 0) after settle delay so servo holds mechanically without hunting.
  - `gui/measurement.py`: second sweep command changed from `_send_servo_command(180.0)` to `_send_servo_command(90.0)` (was silently clamped before).
  - `scripts/pi/servo_test.py`: **NEW** interactive calibration tool — `scan`, `sweep`, `min<us>`, `max<us>`, `p<us>`, angle commands, prints final MIN/MAX on quit.
- Verified:
  - Physical calibration: 850µs ≈ horizontal, 1800µs ≈ vertical (confirmed on Pi with pigpio).
  - Jitter eliminated: servo no longer hunts on GUI startup.
- Risks/follow-up:
  - settle_s=2.0s in measurement worker is conservative; tune once mechanical stop time is measured.

### 2026-04-12 - HPS-2518MG servo driver + dual-polarization sweep
- Changed:
  - **NEW** `hardware/servo.py`: `HPS2518Servo` class. GPIO BCM PWM (50 Hz), sim fallback on non-Linux. `move_to(angle, settle_s)`, `close()`, `_angle_to_duty()`.
  - `hardware/__init__.py`: exports `HPS2518Servo`.
  - `spam_config.json`: added `servo_gpio` key (default `"18"`).
  - `app.py`: added `self.servo = None`, `self.servo_angle = 0.0`, `self.current_polarization = 0.0` init.
  - `gui/hardware_mixin.py`: imports `HPS2518Servo`; servo init block in `_initialize_hardware()` reads `servo_gpio` from config; added `_send_servo_command(angle, settle_s)`.
  - `gui/measurement.py`: split sweep into `_run_single_sweep(pol_angle)` helper + refactored `_measurement_worker` for dual-polarization: sweep at 0°, arm+material return home, servo rotates horn to 90° (2s settle), sweep at 90°, horn returns to 0°, extraction fires once.
- Verified:
  - Sim path: on Windows, servo logs `(sim) -> X°` and sweep runs without blocking.
  - Stop during either sweep aborts cleanly; arm not forcibly returned.
- Risks/follow-up:
  - PWM on GPIO 18 via pigpio (hardware PWM) preferred over RPi.GPIO software PWM for accuracy.

### 2026-04-07 - Voltage→S-parameter calibration (Through/Reflect)
- Changed:
  - **NEW** `core/calibration.py`: `compute_tau_m()`, `compute_gamma_m()`, `compute_k0()`, `lookup_cal_voltage()` — implements PDF inversion formulas from `26_03_31_Cal_Approx_SPAM.pdf`.
  - **NEW** `backend/models.py`: `CalibrationSweep` model (angles_json, voltages_json, geometry_json, f0_ghz, sweep_type).
  - `backend/database.py`: migration creates `calibration_sweeps` table on old DBs.
  - `gui/callbacks.py`: `_on_calibrate()` replaced placeholder with real two-step Through+Reflect motor sweep. Each step runs in background thread, stores per-angle complex voltage in DB. `_load_latest_calibration()` restores cal from DB on startup.
  - `gui/measurement.py`: added `_take_raw_voltage()` for cal sweeps; `_take_adc_reading()` now applies `compute_tau_m`/`compute_gamma_m` when calibration data exists, falls back to raw-proxy with warning when not.
  - `app.py`: init `cal_through`, `cal_reflect`, `cal_d`, `cal_d_sheet` from config.
  - `gui/config.py`: added `cal_d_m`, `cal_d_sheet_m` defaults.
  - `gui/dialogs/connection_dlg.py`: added "Calibration Geometry" section with `d (m)` and `d_sheet (m)` fields.
  - `spam_config.json`: added `cal_d_m`, `cal_d_sheet_m` keys (default 0.0).
  - **NEW** `tests/test_calibration.py`: unit tests for calibration math.
- Verified:
  - Calibration math matches PDF boxed formulas (C3).
  - Extraction pipeline unchanged — already consumes complex S₂₁/S₁₁ from stored power+phase.
- Risks/follow-up:
  - `cal_d_m` and `cal_d_sheet_m` default to 0 → phase correction is identity until real geometry is measured.
  - Cal sweep only moves arm motor (motor 1); material motor not moved during cal — may need adjustment if fixture geometry requires it.

### 2026-04-07 - Background ADC stream thread + SPI lock
- Changed:
  - `gui/measurement.py`: added `_adc_stream_worker()`, `_start_adc_stream_thread()`, `_stop_adc_stream_thread()`. Background thread reads ADC continuously at ~100-600 samp/s, feeding the live oscilloscope graph independently of the sweep.
  - `gui/measurement.py`: `_avg_stream_reads()` now acquires `_adc_lock` per read so sweep and stream thread share SPI safely.
  - `gui/graphs.py`: `_toggle_adc_demo_graph()` starts/stops stream thread; `_update_graphs()` bypasses measurement-count early-return when stream is active.
  - `app.py`: added `_adc_lock = threading.Lock()`, `_adc_stream_running`, `_adc_stream_thread` init; added `import threading`; `_on_close()` stops stream thread before ADC shutdown.
- Verified:
  - Background stream shows ~300+ samp/s in graph when sweep is idle.
  - Sweep continues to take per-angle averaged measurements correctly via lock.
- Risks/follow-up:
  - Lock contention could slightly reduce background stream rate during sweep's 8-sample averaged reads — acceptable tradeoff.

### 2026-04-07 - Motor control: I2C bit 0x02 polling (replaces broken GPIO ISR)
- Changed:
  - `gui/hardware_mixin.py`: `_wait_for_motor_position()` replaced GPIO ISR path (broken on this Pi kernel) with two-phase I2C polling: phase 1 waits for MCU status bit 0x02 to clear (motor started), phase 2 waits for it to set (motor arrived). Timeout 10s as safety fallback. No collision detection in polling path (bit 0x01 appears during normal movement).
  - `gui/hardware_mixin.py`: added `motor_isr_available` flag set during GPIO init to select poll vs ISR path.
- Verified:
  - Motors stop correctly at each 5° position during sweep.
  - Sweep throughput ~0.15-0.25 meas/s (limited by motor travel ~2-4s per step).
  - Poll trace during diagnostic phase: `['0x00', '0x02', '0x06', '0xDD']` — bit 0x02 confirms position reached per Arduino firmware (`motor_control_status.py`).
- Risks/follow-up:
  - Collision detection disabled in polling path; physical collision would cause 10s timeout then continue.
  - GPIO ISR would restore collision detection if kernel support is added.

### 2026-04-07 - ADC speed boost: 4800 Hz data rate, 4 MHz SPI, per-point averaging
- Changed:
  - `spam_config.json`: `spi_speed` 1000000 → 4000000; `adc_data_rate` 96 → 4800; added `adc_samples_per_point: 8`.
  - `gui/config.py`: added `adc_samples_per_point: '8'` default.
  - `app.py`: reads `adc_samples_per_point` from config.
  - `gui/dialogs/connection_dlg.py`: added "Samples/Point" UI field.
  - `gui/measurement.py`: `_take_adc_reading()` calls `_avg_stream_reads(n)` for real hardware (averages n I/Q reads per point); removed `time.sleep(measurement_interval)` calls from sweep loop.
- Verified:
  - ADC initializes at 4800 Hz, SPI 4 MHz on Pi (`AD7193 config: gain=1, FS=1, req_rate=4800Hz realized~4800.0Hz`).
  - Background stream achieves ~300+ samp/s.
- Risks/follow-up:
  - Higher data rate = more noise / less line-frequency rejection. Validate SNR for real material campaigns.

### 2026-04-02 - Repository layout cleanup (docs consolidation)
- Changed:
  - Moved hardware reference PDFs and Pi pinout image to `docs/reference/hardware/`.
  - Moved benchmarks to `docs/benchmarks/` (`benchmark_results.md`, `benchmark_report.tex`, `artifacts/`).
  - Moved integration write-ups to `docs/integration/`.
  - Added `docs/README.md` as documentation index.
  - Removed duplicate root `test_spam_calc.py` and `test_optimizer.py` (use `tests/` only).
  - Renamed `archive/legacy/New folder` → `archive/legacy/matlab_snippets_archived`.
  - Updated cross-links in `README.md`, `REPO_CONTEXT.md`, `scripts/pi/PI_ADC_BRINGUP.md`, moved docs, tests, and `benchmark_report.tex`.
- Verified:
  - `backend/database.py` still uses repo-root `spam.db` (unchanged).
- Risks/follow-up:
  - External bookmarks to old root paths for PDFs/reports need updating.

### 2026-04-02 - Pi ADC throughput documentation + C++ AD7193 benchmark
- Changed:
  - `scripts/pi/ad7193_cpp_benchmark.cpp`: AD7193 protocol mirror + pair/s benchmark; `SPI_IOC_MESSAGE` success as **return >= 0** (not `== 0` only); chrono deadlines use `duration_cast` for Pi `steady_clock`.
  - `README.md`: `scripts/pi/` table, data-rate / pair-rate notes, SPI vs stale I2C wording, example `live_adc_view` command.
  - `REPO_CONTEXT.md`: current truth for data_rate, ~12 Hz pair parity (Py vs C++), spidev ioctl note, expanded Pi commands.
- Verified:
  - Logic reviewed against `hardware/ad7193.py`; user Pi run showed ID OK and ~12 pair/s at `data_rate=96` matching Python.
- Risks/follow-up:
  - High `data_rate` needs analog/SNR validation per campaign.
  - Optional: wire max-rate capture into GUI or sidecar binary for logging.

### 2026-03-31 - AD7193 Pi bring-up stabilized; handoff clarified
- Changed:
  - `hardware/ad7193.py`: corrected AD7193 ID check semantics (`0xX2`), ensured internal clock bits are set in mode writes, and aligned config behavior for active Pi bring-up.
  - `README.md`: added current implementation status and explicit extraction-math boundary language.
  - `REPO_CONTEXT.md`: added current-truth section, ownership split, and next-chat bootstrap checklist.
- Verified:
  - Pi low-level loop now returns finite I/Q values without repeated channel timeouts.
  - GUI logs show ADC initialized and operational in ADC-only mode.
- Risks/follow-up:
  - Voltage->calibrated S-parameter math remains pending teammate implementation.
  - Extraction quality on real hardware remains provisional until calibration module lands.

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

1. **Measure and configure `cal_d_m` and `cal_d_sheet_m`** for the hardware rig — currently 0.0 (phase correction disabled). Set in Settings → Connection Setup.
2. Run Through+Reflect calibration on the actual rig and validate S-param output against a known reference sample.
3. **Dual-pol calibration**: cal sweep currently only captures pol-0 (horn at 0°). For full accuracy, a second through+reflect pass at 90° is needed and `_take_adc_reading` should use the matching reference. Deferred — not blocking expo.
4. Connect RF switch hardware and enable `enable_rf_switch=1` to get independent TX (S21) and RX (S11) measurements — currently both channels read identical ADC input in ADC-only mode.
5. Validate ADC SNR at `data_rate=4800` against real material reference sample (higher rate = more noise).
6. Restore collision detection: currently disabled in I2C polling path. Options: fix GPIO ISR on kernel, or identify a reliable collision-only MCU status value.
7. Validate extraction against calibrated real material reference sample(s).
8. Tune servo `settle_s` (currently 2.0s) once actual travel time from 0°→90° is timed.
9. Add log rotation to `spam_run.log` (currently unbounded append).
