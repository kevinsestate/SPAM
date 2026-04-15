#!/usr/bin/env python3
"""Continuous AD7193 read test.

Usage (on the Pi):
    python3 test_adc.py                       # 96 Hz, gain=1
    python3 test_adc.py --rate 470            # faster settling
    python3 test_adc.py --tare                # zero floating-input bias first
    python3 test_adc.py --rate 96 --tare --gain 1

Press Ctrl+C to stop and print statistics.
"""

import sys
import time
import argparse

sys.path.insert(0, '/home/dibr4426/Desktop/SPAM')

from hardware.ad7193 import AD7193

# ── ANSI helpers ──────────────────────────────────────────────────────────────
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_RED    = "\033[91m"
_WHITE  = "\033[97m"
_BLUE   = "\033[94m"

def _c(text, *codes):
    return "".join(codes) + str(text) + _RESET

def _bar(val_mv, full_scale_mv=2500.0, width=20):
    """ASCII voltage bar, centred at 0."""
    frac = max(-1.0, min(1.0, val_mv / full_scale_mv))
    mid  = width // 2
    pos  = int(frac * mid)
    bar  = [" "] * width
    bar[mid] = _c("|", _DIM)
    if pos >= 0:
        for k in range(mid, mid + pos + 1):
            bar[k] = _c("█", _GREEN)
    else:
        for k in range(mid + pos, mid + 1):
            bar[k] = _c("█", _YELLOW)
    return "".join(bar)

SILENT_LEVELS = {"DEBUG"}

def log(msg, level="INFO"):
    if level in SILENT_LEVELS:
        return
    ts    = _c(time.strftime("%H:%M:%S"), _DIM)
    color = {
        "SUCCESS": _GREEN, "ERROR": _RED, "WARNING": _YELLOW,
        "INFO": _CYAN,
    }.get(level, _WHITE)
    print(f"  {ts} {_c(f'[{level}]', color, _BOLD)} {msg}")


def _header():
    w = 72
    print()
    print(_c("─" * w, _DIM))
    print(_c("  AD7193  LIVE VOLTAGE MONITOR", _CYAN, _BOLD))
    print(_c("─" * w, _DIM))


def _print_table_header():
    print()
    print(
        _c(f"  {'#':>5}", _DIM) +
        _c(f"  {'I  (AIN1) mV':>14}", _GREEN, _BOLD) +
        _c(f"   {'bar (±2.5 V)':^22}", _DIM) +
        _c(f"  {'Q  (AIN2) mV':>14}", _YELLOW, _BOLD) +
        _c(f"   {'bar (±2.5 V)':^22}", _DIM)
    )
    print(_c("  " + "─" * 88, _DIM))


def _fmt_mv(val_mv):
    color = _GREEN if val_mv >= 0 else _YELLOW
    return _c(f"{val_mv:>+9.2f} mV", color)


def _stats_box(label, vals):
    if not vals:
        return
    lo, hi, mean = min(vals), max(vals), sum(vals) / len(vals)
    span = hi - lo
    print(
        f"  {_c(label, _BOLD, _WHITE)}  "
        f"mean {_c(f'{mean:>+8.2f}', _CYAN)} mV   "
        f"min {_c(f'{lo:>+8.2f}', _YELLOW)} mV   "
        f"max {_c(f'{hi:>+8.2f}', _GREEN)} mV   "
        f"span {_c(f'{span:>7.2f}', _DIM)} mV"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Continuous AD7193 voltage monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--rate",      type=int, default=96,
                        help="Output data rate Hz (default 96)")
    parser.add_argument("--gain",      type=int, default=1,
                        help="PGA gain 1/8/16/32/64/128 (default 1)")
    parser.add_argument("--tare",      action="store_true",
                        help="Sample and subtract floating-input DC bias")
    parser.add_argument("--spi-speed", type=int, default=4_000_000,
                        help="SPI clock Hz (default 4 MHz)")
    args = parser.parse_args()

    _header()
    print(f"  rate={_c(args.rate, _CYAN)} Hz   "
          f"gain={_c(args.gain, _CYAN)}   "
          f"tare={_c(args.tare, _CYAN)}   "
          f"spi={_c(args.spi_speed//1_000_000, _CYAN)} MHz")

    try:
        adc = AD7193(spi_bus=0, spi_cs=0, speed_hz=args.spi_speed, log_fn=log)
    except Exception as e:
        print(_c(f"\n  ERROR: {e}", _RED, _BOLD))
        sys.exit(1)

    mode = _c("simulated", _YELLOW) if adc.is_simulated else _c("hardware", _GREEN)
    print(f"  ADC mode : {mode}")
    adc.configure(gain=args.gain, data_rate=args.rate)
    print(f"  FS={_c(adc._fs_val, _CYAN)}  realized ~{_c(adc._data_rate, _CYAN)} Hz")

    # ── Warmup with live counter ──────────────────────────────────────────────
    total_warm = adc._fs_val * 2
    print(f"\n  {_c('Warming up…', _DIM)} ", end="", flush=True)
    _orig_warmup = adc.warmup

    done_warm = [0]

    def _patched_read_channel(ch, _orig=adc.read_channel):
        v = _orig(ch)
        done_warm[0] += 1
        pct = int(done_warm[0] / total_warm * 20)
        bar = _c("█" * pct, _CYAN) + _c("░" * (20 - pct), _DIM)
        print(f"\r  {_c('Warming up…', _DIM)} [{bar}] "
              f"{_c(done_warm[0], _CYAN)}/{total_warm} ", end="", flush=True)
        return v

    adc.read_channel = _patched_read_channel
    adc.warmup()
    adc.read_channel = lambda ch, _orig=adc.__class__.read_channel: _orig(adc, ch)
    print(_c("  done", _GREEN, _BOLD))

    if args.tare:
        print(f"  {_c('Taring…', _DIM)} ", end="", flush=True)
        dc_i, dc_q = adc.tare()
        print(f"{_c('done', _GREEN, _BOLD)}  "
              f"dc_I={_c(f'{dc_i*1000:+.2f}', _CYAN)} mV  "
              f"dc_Q={_c(f'{dc_q*1000:+.2f}', _CYAN)} mV")

    print(f"\n  {_c('Ctrl+C', _BOLD)} to stop\n")
    _print_table_header()

    i_vals, q_vals = [], []
    n = 0
    t0 = time.monotonic()

    try:
        while True:
            i_v = adc.read_channel(0)
            q_v = adc.read_channel(1)
            n += 1
            i_mv, q_mv = i_v * 1000, q_v * 1000
            i_vals.append(i_mv)
            q_vals.append(q_mv)
            ts = _c(time.strftime("%H:%M:%S"), _DIM)
            print(
                f"  {_c(f'{n:>5}', _DIM)}"
                f"  {ts}"
                f"  {_fmt_mv(i_mv)}"
                f"  [{_bar(i_mv)}]"
                f"  {_fmt_mv(q_mv)}"
                f"  [{_bar(q_mv)}]"
            )
    except KeyboardInterrupt:
        elapsed = time.monotonic() - t0
        rate    = n / elapsed if elapsed > 0 else 0
        print()
        print(_c("  " + "─" * 72, _DIM))
        print(_c("  SUMMARY", _BOLD, _WHITE))
        print(_c("  " + "─" * 72, _DIM))
        print(f"  {_c(n, _CYAN)} reads  "
              f"{_c(f'{elapsed:.1f}', _CYAN)} s  "
              f"{_c(f'{rate:.1f}', _CYAN)} reads/s")
        print()
        _stats_box("I (AIN1)", i_vals)
        _stats_box("Q (AIN2)", q_vals)
        print(_c("  " + "─" * 72, _DIM))
        print()
        adc.close()


if __name__ == "__main__":
    main()
