# Raspberry Pi ADC Bring-Up (Pmod AD5 / AD7193)

This checklist is the practical runbook for first hardware bring-up on Raspberry Pi.
It assumes RF switch control is optional and disabled in software by default.

## 0) What success looks like

- Pi can talk to AD7193 over SPI (no ID/read timeout errors).
- `read_iq()` returns finite values repeatedly.
- GUI debug log shows `ADC ready (SPI)` and runs sweep without ADC errors.
- Extraction starts and reports fit status after sweep.

## 1) Hardware wiring (ADC only first)

Wire Raspberry Pi SPI to Pmod AD5:

- Pi MOSI -> AD7193 DIN
- Pi MISO -> AD7193 DOUT/RDY
- Pi SCLK -> AD7193 SCLK
- Pi CE0 (or CE1) -> AD7193 CS
- Pi 3.3V logic and GND -> board logic rails

Analog differential inputs:

- IF-I differential pair -> AIN1+ / AIN1-
- IF-Q differential pair -> AIN2+ / AIN2-

Notes:

- Keep analog ground/common reference clean and short.
- Verify your exact Pmod AD5 pinout against Digilent docs before power-on.
- If unsure, power with input source disconnected first.

## 2) Pi setup

1. Enable SPI:
   - `sudo raspi-config` -> Interface Options -> SPI -> Enable
2. Reboot.
3. Verify SPI device nodes:
   - `ls /dev/spidev*`
4. In repo venv, install dependencies:
   - `pip install -r requirements.txt`

## 3) Low-level ADC check (before GUI)

Run:

```bash
python scripts/pi/check_adc_lowlevel.py --seconds 15 --rate-hz 10
```

Optional explicit config:

```bash
python scripts/pi/check_adc_lowlevel.py \
  --spi-bus 0 --spi-cs 0 --spi-speed 1000000 \
  --gain 1 --data-rate 96 --seconds 20 --rate-hz 10 \
  --csv benchmark_artifacts/pi_adc_iq.csv
```

Pass criteria:

- No `timeout reading ch...` errors.
- `simulated=False` in script output.
- Finite I/Q values for all samples.
- RMS/std is non-zero when signal changes; stable baseline when static.

## 4) GUI ADC-only validation

1. Launch app.
2. Open Connection Setup and set:
   - SPI Bus / SPI CS / SPI Speed
   - ADC Gain / Data Rate
   - Enable RF Switch Control = `0`
3. Save settings.
4. Open Debug Console and confirm:
   - `ADC ready (SPI)`
   - `RF switch control disabled (ADC-only mode)`
5. Run a short sweep.

Pass criteria:

- Sweep completes without ADC exceptions.
- TX/RX values update over angle.
- Extraction starts and logs fit status.

## 5) Extraction verification on Pi

Start with:

- Tensor type: `diagonal`
- Correct frequency and slab thickness values

Check debug output includes:

- `f0`, `d`, `k0d`, tensor type

If unstable fit:

- Lower ADC data rate (more averaging).
- Re-check differential polarity and shielding/grounding.
- Re-check thickness/frequency settings.

## 6) Optional RF switch integration later

Only if needed by your team:

- Set `Enable RF Switch Control = 1`
- Wire switch GPIO control pin
- Verify path toggle logs before using S21/S11 sequencing

## 7) First field-test evidence to save

Keep one short log bundle:

- Connection settings used
- 10-20 second low-level I/Q capture
- GUI sweep excerpt
- Extraction output (fit error + runtime)

Use `scripts/pi/PI_FIRST_FIELD_TEST_LOG_TEMPLATE.md` as the template.
