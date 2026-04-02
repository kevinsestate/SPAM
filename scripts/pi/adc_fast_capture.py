"""Optional fast-capture harness for AD7193.

This script attempts to use a compiled helper module first. If unavailable,
it falls back to the optimized Python streaming path and reports throughput.

Usage:
  python scripts/pi/adc_fast_capture.py --duration 10
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AD7193 fast-capture harness")
    p.add_argument("--duration", type=float, default=10.0)
    p.add_argument("--spi-bus", type=int, default=0)
    p.add_argument("--spi-cs", type=int, default=0)
    p.add_argument("--spi-speed", type=int, default=1_000_000)
    p.add_argument("--gain", type=int, default=1, choices=[1, 8, 16, 32, 64, 128])
    p.add_argument("--data-rate", type=int, default=96)
    return p.parse_args()


def _run_python_fallback(args: argparse.Namespace) -> int:
    from hardware import AD7193

    adc = AD7193(args.spi_bus, args.spi_cs, args.spi_speed, log_fn=lambda m, l: None)
    try:
        adc.configure(gain=args.gain, data_rate=args.data_rate)
        adc.start_iq_stream()
        t0 = time.monotonic()
        n = 0
        while (time.monotonic() - t0) < args.duration:
            adc.read_iq_stream(timeout_s=0.5)
            n += 1
        dt = max(1e-9, time.monotonic() - t0)
        pair_hz = n / dt
        print(f"[PY_FALLBACK] pairs={n} elapsed={dt:.3f}s pair_rate={pair_hz:.2f}Hz per_channel={pair_hz:.2f}Hz")
        return 0 if not adc.is_simulated else 4
    finally:
        adc.close()


def main() -> int:
    args = parse_args()

    # Optional compiled helper (future/perf path).
    try:
        from scripts.pi.perf import adc_fast_native  # type: ignore

        rc = adc_fast_native.run(
            duration=float(args.duration),
            spi_bus=int(args.spi_bus),
            spi_cs=int(args.spi_cs),
            spi_speed=int(args.spi_speed),
            gain=int(args.gain),
            data_rate=int(args.data_rate),
        )
        print(f"[NATIVE] completed rc={rc}")
        return int(rc)
    except Exception:
        print("[INFO] Native fast module unavailable; using optimized Python fallback.")
        return _run_python_fallback(args)


if __name__ == "__main__":
    sys.exit(main())

