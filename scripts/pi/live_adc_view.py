"""Live AD7193 ADC viewer (terminal + optional chart).

Usage examples:
  python scripts/pi/live_adc_view.py
  python scripts/pi/live_adc_view.py --spi-speed 100000 --target-hz 12
  python scripts/pi/live_adc_view.py --duration 0 --window-sec 30
  python scripts/pi/live_adc_view.py --no-plot
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
import time
from collections import deque
from pathlib import Path

# Ensure repo root is importable when running from scripts/pi.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live AD7193 ADC read viewer")
    p.add_argument("--spi-bus", type=int, default=0, help="SPI bus index (default: 0)")
    p.add_argument("--spi-cs", type=int, default=0, help="SPI chip-select index (default: 0)")
    p.add_argument("--spi-speed", type=int, default=100_000, help="SPI speed Hz (default: 100000)")
    p.add_argument("--gain", type=int, default=1, choices=[1, 8, 16, 32, 64, 128], help="ADC gain")
    p.add_argument("--data-rate", type=int, default=96, help="ADC data rate in Hz")
    p.add_argument("--target-hz", type=float, default=12.0, help="Target UI sample rate in Hz")
    p.add_argument("--duration", type=float, default=0.0, help="Seconds to run (0 = run until Ctrl+C)")
    p.add_argument("--window-sec", type=float, default=20.0, help="Plot window in seconds")
    p.add_argument("--no-plot", action="store_true", help="Disable matplotlib chart")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    try:
        from hardware import AD7193
    except Exception as exc:
        print(f"[ERROR] Failed to import AD7193: {exc}")
        return 2

    show_plot = not args.no_plot
    plt = None
    fig = ax = ln_i = ln_q = None

    if show_plot:
        try:
            import matplotlib.pyplot as plt  # type: ignore
        except Exception as exc:
            print(f"[WARN] Matplotlib unavailable ({exc}); continuing in terminal mode.")
            show_plot = False

    t_buf: deque[float] = deque()
    i_buf_mv: deque[float] = deque()
    q_buf_mv: deque[float] = deque()

    all_i_mv: list[float] = []
    all_q_mv: list[float] = []
    all_mag_mv: list[float] = []

    def log_fn(msg: str, lvl: str) -> None:
        print(f"[{lvl}] {msg}")

    adc = None
    try:
        adc = AD7193(args.spi_bus, args.spi_cs, args.spi_speed, log_fn=log_fn)
        adc.configure(gain=args.gain, data_rate=args.data_rate)
        print(
            f"[INFO] configured spi={args.spi_bus}.{args.spi_cs} speed={args.spi_speed} "
            f"gain={args.gain} rate={args.data_rate}Hz simulated={adc.is_simulated}"
        )
        print("[INFO] Channels: CH0=I (AIN1+/AIN1-), CH1=Q (AIN2+/AIN2-)")
        print("[INFO] Press Ctrl+C to stop.\n")

        if show_plot and plt is not None:
            plt.ion()
            fig, ax = plt.subplots(figsize=(9, 4))
            ln_i, = ax.plot([], [], label="I (mV)", linewidth=1.8)
            ln_q, = ax.plot([], [], label="Q (mV)", linewidth=1.8)
            ax.set_title("Live ADC Voltage")
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Voltage (mV)")
            ax.set_ylim(0, 1000)
            ax.grid(True, alpha=0.3)
            ax.legend(loc="upper right")
            fig.tight_layout()

        dt = 1.0 / max(args.target_hz, 0.5)
        t0 = time.monotonic()
        last_print = 0.0

        while True:
            now = time.monotonic()
            t = now - t0
            if args.duration > 0 and t >= args.duration:
                break

            i_v, q_v = adc.read_iq()
            i_mv = i_v * 1000.0
            q_mv = q_v * 1000.0
            mag_mv = math.sqrt(i_mv * i_mv + q_mv * q_mv)
            d_mv = i_mv - q_mv

            t_buf.append(t)
            i_buf_mv.append(i_mv)
            q_buf_mv.append(q_mv)
            all_i_mv.append(i_mv)
            all_q_mv.append(q_mv)
            all_mag_mv.append(mag_mv)

            while t_buf and (t - t_buf[0]) > args.window_sec:
                t_buf.popleft()
                i_buf_mv.popleft()
                q_buf_mv.popleft()

            n_win = len(t_buf)
            if n_win >= 2:
                rate = (n_win - 1) / max(1e-9, (t_buf[-1] - t_buf[0]))
            else:
                rate = 0.0

            # Print at ~4 Hz so terminal stays readable.
            if (now - last_print) >= 0.25:
                print(
                    f"\rt={t:7.2f}s  I={i_mv:7.1f} mV  Q={q_mv:7.1f} mV  "
                    f"Δ={d_mv:+7.1f} mV  |IQ|={mag_mv:7.1f} mV  "
                    f"N={len(all_i_mv):5d}  ~{rate:5.2f} samp/s",
                    end="",
                    flush=True,
                )
                last_print = now

            if show_plot and plt is not None and ax is not None and ln_i is not None and ln_q is not None:
                tx = list(t_buf)
                iy = list(i_buf_mv)
                qy = list(q_buf_mv)
                ln_i.set_data(tx, iy)
                ln_q.set_data(tx, qy)
                if tx:
                    x0 = max(0.0, tx[-1] - args.window_sec)
                    ax.set_xlim(x0, max(x0 + 1.0, tx[-1] + 0.2))
                    ymax = max(max(iy), max(qy))
                    ax.set_ylim(0.0, max(1000.0, ymax + 80.0))
                plt.pause(0.001)

            time.sleep(dt)

        print()  # newline after carriage-return loop

        if not all_i_mv:
            print("[ERROR] No samples captured.")
            return 3

        print("\n=== Summary ===")
        print(f"samples={len(all_i_mv)}")
        print(
            "I(mV): mean={:.2f} std={:.2f} min={:.2f} max={:.2f}".format(
                statistics.mean(all_i_mv), statistics.pstdev(all_i_mv), min(all_i_mv), max(all_i_mv)
            )
        )
        print(
            "Q(mV): mean={:.2f} std={:.2f} min={:.2f} max={:.2f}".format(
                statistics.mean(all_q_mv), statistics.pstdev(all_q_mv), min(all_q_mv), max(all_q_mv)
            )
        )
        print(
            "|IQ|(mV): mean={:.2f} std={:.2f} min={:.2f} max={:.2f}".format(
                statistics.mean(all_mag_mv), statistics.pstdev(all_mag_mv), min(all_mag_mv), max(all_mag_mv)
            )
        )

        if adc.is_simulated:
            print("[WARN] ADC is in simulation mode. On Pi, verify spidev and wiring.")
            return 4
        return 0

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")
        return 0
    except Exception as exc:
        print(f"\n[ERROR] Live ADC view failed: {exc}")
        return 1
    finally:
        if adc is not None:
            try:
                adc.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())

