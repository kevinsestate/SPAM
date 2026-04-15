#!/usr/bin/env python3
"""Continuous ADC read test — plug in a known voltage and watch it live.

Usage (on the Pi):
    python3 test_adc.py              # 96 Hz, gain=1, no tare
    python3 test_adc.py --rate 470   # faster (FS=10)
    python3 test_adc.py --tare       # zero out floating-input bias first
    python3 test_adc.py --rate 96 --tare --gain 1

Press Ctrl+C to stop.  Running min/max/mean stats are printed on exit.
"""

import sys
import time
import argparse

sys.path.insert(0, '/home/dibr4426/Desktop/SPAM')

from hardware.ad7193 import AD7193


def log(msg, level="INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def main():
    parser = argparse.ArgumentParser(description="Continuous AD7193 read test")
    parser.add_argument("--rate", type=int, default=96,
                        help="Output data rate in Hz (default 96)")
    parser.add_argument("--gain", type=int, default=1,
                        help="PGA gain: 1,8,16,32,64,128 (default 1)")
    parser.add_argument("--tare", action="store_true",
                        help="Sample DC offset first and subtract it")
    parser.add_argument("--spi-speed", type=int, default=4_000_000,
                        help="SPI clock Hz (default 4000000)")
    args = parser.parse_args()

    print("=" * 60)
    print("AD7193 Continuous Read Test")
    print(f"  rate={args.rate} Hz  gain={args.gain}  tare={args.tare}")
    print("  Ctrl+C to stop")
    print("=" * 60)

    try:
        adc = AD7193(spi_bus=0, spi_cs=0, speed_hz=args.spi_speed, log_fn=log)
    except Exception as e:
        print(f"ERROR: Failed to init ADC: {e}")
        sys.exit(1)

    print(f"Simulated: {adc.is_simulated}")
    adc.configure(gain=args.gain, data_rate=args.rate)
    print(f"FS={adc._fs_val}, realized ~{adc._data_rate} Hz")

    print(f"\nRunning warmup ({adc._fs_val * 2} reads)...")
    adc.warmup()
    print("Warmup done.\n")

    if args.tare:
        print("Taring (64 reads)...")
        dc_i, dc_q = adc.tare()
        print(f"Tare: dc_I={dc_i*1000:+.2f} mV  dc_Q={dc_q*1000:+.2f} mV\n")

    print(f"{'#':>6}  {'I (mV)':>10}  {'Q (mV)':>10}  {'raw_I':>10}  {'raw_Q':>10}")
    print("-" * 56)

    i_vals, q_vals = [], []
    n = 0
    t0 = time.monotonic()

    try:
        while True:
            raw_i = adc.read_channel(0)
            raw_q = adc.read_channel(1)
            n += 1
            i_mv = raw_i * 1000
            q_mv = raw_q * 1000
            i_vals.append(i_mv)
            q_vals.append(q_mv)
            print(f"{n:>6}  {i_mv:>+10.2f}  {q_mv:>+10.2f}")
    except KeyboardInterrupt:
        elapsed = time.monotonic() - t0
        print("\n" + "=" * 60)
        print(f"Stopped after {n} reads in {elapsed:.1f}s  "
              f"({n/elapsed:.1f} reads/s effective)")
        if i_vals:
            print(f"  I: min={min(i_vals):+.2f}  max={max(i_vals):+.2f}  "
                  f"mean={sum(i_vals)/len(i_vals):+.2f} mV")
            print(f"  Q: min={min(q_vals):+.2f}  max={max(q_vals):+.2f}  "
                  f"mean={sum(q_vals)/len(q_vals):+.2f} mV")
        print("=" * 60)
        adc.close()


if __name__ == "__main__":
    main()
