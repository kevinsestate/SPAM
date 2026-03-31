# HANDOFF_STATUS

Last updated: 2026-03-31
Scope: quick operator + new-agent handoff for current Pi/ADC state.

## Snapshot

### Done
- AD7193 SPI bring-up on Raspberry Pi is working.
- Driver-level conversion timeout issue resolved (ID check, mode clock bits, config alignment).
- GUI runs ADC-only measurement flow and logs live TX/RX updates.

### In Progress
- Team integration of calibrated voltage->S-parameter conversion for extraction accuracy.

### Blocked / Not Final Yet
- Final extraction fidelity on real hardware is blocked on teammate math merge.
- Motor/switch full-rig validation is pending when hardware is fully connected.

## Extraction Caveat (Current)

Current extraction path is operational but provisional: it can consume proxy S-parameters derived from ADC I/Q. Final-calibrated voltage->S conversion is pending teammate implementation.

## Verified Commands and Expected Signals

## 1) Low-level ADC check (Pi)

```bash
python - <<'PY'
from hardware import AD7193
adc = AD7193(spi_bus=0, spi_cs=0, speed_hz=100000, log_fn=lambda m,l: print(f"[{l}] {m}"))
adc.configure(gain=1, data_rate=96)
print("simulated =", adc.is_simulated)
for i in range(20):
    iv, qv = adc.read_iq()
    print(i, "I=", iv, "Q=", qv)
adc.close()
PY
```

Healthy behavior:
- `ID=0xA2 verified` (or any `0xX2` ID low nibble)
- no repeating `timeout reading ch0/ch1`
- finite, varying I/Q values

## 2) GUI run (Pi)

```bash
source venv/bin/activate
python app.py
```

Connection settings baseline:
- SPI bus `0`
- SPI CS `0`
- SPI speed `100000`
- ADC gain `1`
- ADC data rate `96`
- RF switch disabled (ADC-only)

Expected GUI log pattern:
- ADC initialized successfully
- no repeated ADC timeouts
- live measurement updates during run

## Immediate Next Steps (After Teammate Math Lands)

1. Add calibrated voltage->S conversion module at measurement/extraction boundary.
2. Replace proxy S reconstruction path with calibrated complex S11/S21 generation.
3. Re-run extraction against known reference sample and compare fit stability.
4. Lock default Pi settings (gain/rate/speed) based on measured SNR and runtime.
5. Update `README.md` and `REPO_CONTEXT.md` to remove provisional wording.

## Watchlist / Risks

- Calibration quality directly controls extraction trustworthiness.
- ADC-only tests (no motor) validate acquisition path, not full sweep mechanics.
- Wiring/contact quality can still cause intermittent field issues; keep a known-good wiring photo and settings baseline.
