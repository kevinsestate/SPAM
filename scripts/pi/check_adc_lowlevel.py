"""Low-level AD7193 bring-up check for Raspberry Pi.

Usage examples:
  python scripts/pi/check_adc_lowlevel.py --seconds 15 --rate-hz 10
  python scripts/pi/check_adc_lowlevel.py --spi-bus 0 --spi-cs 0 --gain 1 --data-rate 96
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
import time
from pathlib import Path

# Ensure repo root is importable when running from scripts/pi.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AD7193 low-level I/Q read check")
    p.add_argument("--spi-bus", type=int, default=0, help="SPI bus index (default: 0)")
    p.add_argument("--spi-cs", type=int, default=0, help="SPI chip-select index (default: 0)")
    p.add_argument("--spi-speed", type=int, default=1_000_000, help="SPI speed Hz (default: 1000000)")
    p.add_argument("--gain", type=int, default=1, choices=[1, 8, 16, 32, 64, 128], help="ADC gain")
    p.add_argument("--data-rate", type=int, default=96, help="ADC data rate in Hz")
    p.add_argument("--seconds", type=float, default=15.0, help="Capture duration in seconds")
    p.add_argument("--rate-hz", type=float, default=10.0, help="Sampling print rate in Hz")
    p.add_argument("--acq-mode", choices=["single", "stream"], default="single",
                   help="ADC acquisition backend to test")
    p.add_argument("--csv", type=str, default="", help="Optional CSV output path")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    try:
        from hardware import AD7193
    except Exception as exc:
        print(f"[ERROR] Failed to import AD7193: {exc}")
        return 2

    log_records: list[tuple[float, float, float, float]] = []

    def log_fn(msg: str, lvl: str) -> None:
        print(f"[{lvl}] {msg}")

    adc = None
    try:
        adc = AD7193(args.spi_bus, args.spi_cs, args.spi_speed, log_fn=log_fn)
        adc.configure(gain=args.gain, data_rate=args.data_rate)
        if args.acq_mode == "stream" and not adc.is_simulated:
            adc.start_iq_stream()
        print(
            f"[INFO] configured spi={args.spi_bus}.{args.spi_cs} speed={args.spi_speed} "
            f"gain={args.gain} rate={args.data_rate}Hz acq_mode={args.acq_mode} simulated={adc.is_simulated}"
        )

        dt = 1.0 / max(args.rate_hz, 0.1)
        start = time.time()
        while time.time() - start < args.seconds:
            t = time.time() - start
            if args.acq_mode == "stream":
                i_v, q_v = adc.read_iq_stream(timeout_s=0.5)
            else:
                i_v, q_v = adc.read_iq()
            mag = math.sqrt(i_v * i_v + q_v * q_v)
            log_records.append((t, i_v, q_v, mag))
            finite = math.isfinite(i_v) and math.isfinite(q_v) and math.isfinite(mag)
            print(
                f"t={t:7.3f}s  I={i_v: .6f} V  Q={q_v: .6f} V  |IQ|={mag: .6f}  finite={finite}"
            )
            time.sleep(dt)

        if not log_records:
            print("[ERROR] No samples captured.")
            return 3

        i_vals = [r[1] for r in log_records if math.isfinite(r[1])]
        q_vals = [r[2] for r in log_records if math.isfinite(r[2])]
        m_vals = [r[3] for r in log_records if math.isfinite(r[3])]
        finite_count = len(m_vals)
        total_count = len(log_records)

        print("\n=== Summary ===")
        print(f"samples={total_count} finite={finite_count}")
        if finite_count != total_count:
            print("[WARN] Non-finite samples detected.")
        if i_vals:
            print(
                "I: mean={:.6f} std={:.6f} min={:.6f} max={:.6f}".format(
                    statistics.mean(i_vals),
                    statistics.pstdev(i_vals),
                    min(i_vals),
                    max(i_vals),
                )
            )
        if q_vals:
            print(
                "Q: mean={:.6f} std={:.6f} min={:.6f} max={:.6f}".format(
                    statistics.mean(q_vals),
                    statistics.pstdev(q_vals),
                    min(q_vals),
                    max(q_vals),
                )
            )
        if m_vals:
            print(
                "|IQ|: mean={:.6f} std={:.6f} min={:.6f} max={:.6f}".format(
                    statistics.mean(m_vals),
                    statistics.pstdev(m_vals),
                    min(m_vals),
                    max(m_vals),
                )
            )

        if args.csv:
            out_path = Path(args.csv)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["t_s", "i_v", "q_v", "mag_v"])
                w.writerows(log_records)
            print(f"[INFO] wrote CSV -> {out_path}")

        if adc.is_simulated:
            print("[WARN] ADC is in simulation mode. On Pi, verify spidev and wiring.")
            return 4
        if finite_count != total_count:
            return 5
        print("[OK] ADC low-level check passed.")
        return 0

    except Exception as exc:
        print(f"[ERROR] ADC check failed: {exc}")
        return 1
    finally:
        if adc is not None:
            try:
                adc.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
