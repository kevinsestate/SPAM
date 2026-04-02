"""Live AD7193 ADC viewer (low-noise + max-rate modes).

Usage examples:
  python scripts/pi/live_adc_view.py
  python scripts/pi/live_adc_view.py --mode low-noise
  python scripts/pi/live_adc_view.py --mode max-rate --no-plot --duration 10
  python scripts/pi/live_adc_view.py --spi-speed 100000 --data-rate 96 --target-hz 20
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
    p.add_argument("--target-hz", type=float, default=20.0, help="Target acquisition rate in Hz (ignored in max-rate mode)")
    p.add_argument("--duration", type=float, default=0.0, help="Seconds to run (0 = run until Ctrl+C)")
    p.add_argument("--window-sec", type=float, default=20.0, help="Plot window in seconds")
    p.add_argument("--no-plot", action="store_true", help="Disable matplotlib chart")
    p.add_argument("--mode", choices=["low-noise", "max-rate"], default="low-noise", help="Operating mode")
    p.add_argument("--print-hz", type=float, default=4.0, help="Terminal refresh rate")
    p.add_argument("--plot-hz", type=float, default=8.0, help="Plot refresh rate")
    p.add_argument("--median-window", type=int, default=5, help="Low-noise median window size (odd number preferred)")
    p.add_argument("--ema-alpha", type=float, default=0.25, help="Low-noise EMA alpha (0..1)")
    p.add_argument("--spike-threshold-mv", type=float, default=250.0, help="Spike reject threshold in mV (<=0 disables)")
    return p.parse_args()


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _safe_stats(values: list[float]) -> tuple[float, float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0, 0.0
    return statistics.mean(values), statistics.pstdev(values), min(values), max(values)


def main() -> int:
    args = parse_args()

    try:
        from hardware import AD7193
    except Exception as exc:
        print(f"[ERROR] Failed to import AD7193: {exc}")
        return 2

    show_plot = not args.no_plot
    plt = None
    fig = ax_top = ax_bot = ln_i = ln_q = ln_mag = txt_live = None

    if show_plot:
        try:
            import matplotlib.pyplot as plt  # type: ignore
        except Exception as exc:
            print(f"[WARN] Matplotlib unavailable ({exc}); continuing in terminal mode.")
            show_plot = False

    # Rolling display buffers (filtered values for cleaner demo).
    t_buf: deque[float] = deque()
    i_buf_mv: deque[float] = deque()
    q_buf_mv: deque[float] = deque()

    # Raw capture for diagnostics.
    raw_i_mv: list[float] = []
    raw_q_mv: list[float] = []
    raw_mag_mv: list[float] = []

    # Display (post-filter) capture.
    disp_i_mv: list[float] = []
    disp_q_mv: list[float] = []
    disp_mag_mv: list[float] = []

    # Low-noise filter state.
    med_n = max(1, int(args.median_window))
    med_i: deque[float] = deque(maxlen=med_n)
    med_q: deque[float] = deque(maxlen=med_n)
    ema_i: float | None = None
    ema_q: float | None = None
    alpha = _clamp(float(args.ema_alpha), 0.01, 1.0)
    spike_thr = float(args.spike_threshold_mv)
    spike_rejects = 0

    # Rate tracking.
    t_acq: deque[float] = deque(maxlen=2048)
    render_count = 0
    plot_count = 0

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
        print(f"[INFO] mode={args.mode}  print_hz={args.print_hz}  plot_hz={args.plot_hz}")
        print("[INFO] Channels: CH0=I (AIN1+/AIN1-), CH1=Q (AIN2+/AIN2-)")
        print("[INFO] Press Ctrl+C to stop.\n")

        if show_plot and plt is not None:
            plt.ion()
            fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(11, 5.2), sharex=True)
            ln_i, = ax_top.plot([], [], label="I (mV)", linewidth=1.8)
            ln_q, = ax_top.plot([], [], label="Q (mV)", linewidth=1.8)
            ln_mag, = ax_bot.plot([], [], label="|IQ| (mV)", linewidth=1.8, color="tab:green")
            ax_top.set_title("Live ADC Voltage")
            ax_top.set_ylabel("I / Q (mV)")
            ax_top.set_ylim(0, 1000)
            ax_top.grid(True, alpha=0.3)
            ax_top.legend(loc="upper right")
            txt_live = ax_top.text(
                0.02, 0.03, "",
                transform=ax_top.transAxes,
                ha="left", va="bottom",
                fontsize=8, family="monospace",
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white", alpha=0.85),
            )
            ax_bot.set_xlabel("Time (s)")
            ax_bot.set_ylabel("|IQ| (mV)")
            ax_bot.set_ylim(0, 1000)
            ax_bot.grid(True, alpha=0.3)
            ax_bot.legend(loc="upper right")
            fig.tight_layout()

        acq_dt = 0.0 if args.mode == "max-rate" else (1.0 / max(args.target_hz, 0.5))
        print_dt = 1.0 / max(args.print_hz, 0.2)
        plot_dt = 1.0 / max(args.plot_hz, 0.2)

        t0 = time.monotonic()
        last_print = 0.0
        last_plot = 0.0

        while True:
            now = time.monotonic()
            t = now - t0
            if args.duration > 0 and t >= args.duration:
                break

            i_v, q_v = adc.read_iq()
            i_mv_raw = i_v * 1000.0
            q_mv_raw = q_v * 1000.0
            mag_mv_raw = math.sqrt(i_mv_raw * i_mv_raw + q_mv_raw * q_mv_raw)
            raw_i_mv.append(i_mv_raw)
            raw_q_mv.append(q_mv_raw)
            raw_mag_mv.append(mag_mv_raw)

            if args.mode == "low-noise":
                med_i.append(i_mv_raw)
                med_q.append(q_mv_raw)
                i_med = statistics.median(med_i)
                q_med = statistics.median(med_q)

                if ema_i is None:
                    ema_i = i_med
                    ema_q = q_med
                else:
                    cand_i = ema_i + alpha * (i_med - ema_i)
                    cand_q = ema_q + alpha * (q_med - ema_q)
                    if spike_thr > 0 and abs(cand_i - ema_i) > spike_thr:
                        spike_rejects += 1
                        cand_i = ema_i
                    if spike_thr > 0 and abs(cand_q - ema_q) > spike_thr:
                        spike_rejects += 1
                        cand_q = ema_q
                    ema_i, ema_q = cand_i, cand_q

                i_mv = float(ema_i)
                q_mv = float(ema_q)
            else:
                i_mv = i_mv_raw
                q_mv = q_mv_raw

            mag_mv = math.sqrt(i_mv * i_mv + q_mv * q_mv)
            d_mv = i_mv - q_mv

            disp_i_mv.append(i_mv)
            disp_q_mv.append(q_mv)
            disp_mag_mv.append(mag_mv)

            t_buf.append(t)
            i_buf_mv.append(i_mv)
            q_buf_mv.append(q_mv)
            while t_buf and (t - t_buf[0]) > args.window_sec:
                t_buf.popleft()
                i_buf_mv.popleft()
                q_buf_mv.popleft()

            t_acq.append(now)
            if len(t_acq) >= 2:
                acq_rate = (len(t_acq) - 1) / max(1e-9, (t_acq[-1] - t_acq[0]))
            else:
                acq_rate = 0.0

            if (now - last_print) >= print_dt:
                render_count += 1
                print_rate = render_count / max(1e-9, t)
                print(
                    f"\rt={t:7.2f}s  I={i_mv:7.1f} mV  Q={q_mv:7.1f} mV  "
                    f"Δ={d_mv:+7.1f} mV  |IQ|={mag_mv:7.1f} mV  "
                    f"N={len(raw_i_mv):5d}  acq~{acq_rate:6.2f}Hz  disp~{print_rate:5.2f}Hz",
                    end="",
                    flush=True,
                )
                last_print = now

            if (
                show_plot
                and plt is not None
                and ax_top is not None
                and ax_bot is not None
                and ln_i is not None
                and ln_q is not None
                and ln_mag is not None
                and txt_live is not None
                and (now - last_plot) >= plot_dt
            ):
                plot_count += 1
                tx = list(t_buf)
                iy = list(i_buf_mv)
                qy = list(q_buf_mv)
                my = [math.sqrt(i * i + q * q) for i, q in zip(iy, qy)]
                ln_i.set_data(tx, iy)
                ln_q.set_data(tx, qy)
                ln_mag.set_data(tx, my)
                if tx:
                    x0 = max(0.0, tx[-1] - args.window_sec)
                    x1 = max(x0 + 1.0, tx[-1] + 0.2)
                    ax_top.set_xlim(x0, x1)
                    ax_bot.set_xlim(x0, x1)
                    ymax_iq = max(max(iy), max(qy))
                    ymax_mag = max(my) if my else 0.0
                    ax_top.set_ylim(0.0, max(1000.0, ymax_iq + 80.0))
                    ax_bot.set_ylim(0.0, max(1000.0, ymax_mag + 80.0))
                    txt_live.set_text(
                        f"I={i_mv:7.1f} mV  Q={q_mv:7.1f} mV  Δ={d_mv:+7.1f} mV  |IQ|={mag_mv:7.1f} mV\n"
                        f"N={len(raw_i_mv):5d}  acq~{acq_rate:6.2f} Hz  mode={args.mode}"
                    )
                plt.pause(0.001)
                last_plot = now

            if acq_dt > 0:
                time.sleep(acq_dt)

        print()  # newline after carriage-return loop

        if not raw_i_mv:
            print("[ERROR] No samples captured.")
            return 3

        t_elapsed = max(1e-9, time.monotonic() - t0)
        acq_eff = len(raw_i_mv) / t_elapsed
        disp_eff = render_count / t_elapsed
        plot_eff = (plot_count / t_elapsed) if show_plot else 0.0

        i_mu, i_sd, i_min, i_max = _safe_stats(raw_i_mv)
        q_mu, q_sd, q_min, q_max = _safe_stats(raw_q_mv)
        m_mu, m_sd, m_min, m_max = _safe_stats(raw_mag_mv)
        fi_mu, fi_sd, fi_min, fi_max = _safe_stats(disp_i_mv)
        fq_mu, fq_sd, fq_min, fq_max = _safe_stats(disp_q_mv)
        fm_mu, fm_sd, fm_min, fm_max = _safe_stats(disp_mag_mv)

        print("\n=== Summary ===")
        print(f"mode={args.mode}")
        print(f"samples={len(raw_i_mv)} elapsed={t_elapsed:.2f}s")
        print(f"rates: acquisition={acq_eff:.2f} Hz  terminal={disp_eff:.2f} Hz  plot={plot_eff:.2f} Hz")
        if args.mode == "low-noise":
            print(
                f"filters: median_window={med_n} ema_alpha={alpha:.3f} "
                f"spike_threshold_mV={spike_thr:.1f} spike_rejects={spike_rejects}"
            )
        print(
            "RAW I(mV): mean={:.2f} std={:.2f} min={:.2f} max={:.2f}".format(i_mu, i_sd, i_min, i_max)
        )
        print(
            "RAW Q(mV): mean={:.2f} std={:.2f} min={:.2f} max={:.2f}".format(q_mu, q_sd, q_min, q_max)
        )
        print(
            "RAW |IQ|(mV): mean={:.2f} std={:.2f} min={:.2f} max={:.2f}".format(m_mu, m_sd, m_min, m_max)
        )
        print(
            "DSP I(mV): mean={:.2f} std={:.2f} min={:.2f} max={:.2f}".format(fi_mu, fi_sd, fi_min, fi_max)
        )
        print(
            "DSP Q(mV): mean={:.2f} std={:.2f} min={:.2f} max={:.2f}".format(fq_mu, fq_sd, fq_min, fq_max)
        )
        print(
            "DSP |IQ|(mV): mean={:.2f} std={:.2f} min={:.2f} max={:.2f}".format(fm_mu, fm_sd, fm_min, fm_max)
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

