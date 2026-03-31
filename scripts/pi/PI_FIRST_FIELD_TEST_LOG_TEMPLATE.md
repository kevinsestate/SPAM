# PI First Field-Test Log Template

Date:
Operator:
Pi hostname:
Code commit:

## 1) Hardware Setup

- ADC board: Pmod AD5 / AD7193
- SPI wiring confirmed: yes/no
- Differential wiring:
  - AIN1+/AIN1- source:
  - AIN2+/AIN2- source:
- Grounding/shielding notes:

## 2) Software Setup

- SPI enabled in raspi-config: yes/no
- `/dev/spidev*` present:
- Python/venv:
- Installed requirements date:

## 3) Connection Settings Used (GUI)

- SPI Bus:
- SPI CS:
- SPI Speed (Hz):
- ADC Gain:
- ADC Data Rate:
- Enable RF Switch Control (0/1):
- Switch GPIO Pin (if enabled):
- Frequency (GHz):
- Thickness (mil):
- Tensor type:

## 4) Low-Level ADC Check

Command run:

```bash
python scripts/pi/check_adc_lowlevel.py --seconds 15 --rate-hz 10
```

Result summary:
- Exit code:
- simulated=True/False:
- sample count:
- finite samples:
- I mean/std:
- Q mean/std:
- |IQ| mean/std:
- Any timeout/errors:

## 5) GUI Sweep Test

- Debug log contains `ADC ready (SPI)`: yes/no
- Debug log contains `RF switch control disabled (ADC-only mode)` (if expected): yes/no
- Sweep completed: yes/no
- TX/RX updated over angle: yes/no
- Errors observed:

## 6) Extraction Test

- Extraction started automatically after sweep: yes/no
- Fit error:
- Runtime:
- Status (Done/No Converge/Error):
- Notes:

## 7) Outcome

- Pass / Fail:
- Blocking issues:
- Next action:
