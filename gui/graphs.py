"""GraphsMixin: center panel, graph updates, _update_display."""

import tkinter as tk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .themes import _FONT, _MONO


class GraphsMixin:
    """Provides center panel creation, graph styling, graph updates, and periodic display refresh."""

    def _toggle_adc_demo_graph(self):
        self.adc_demo_graph_enabled = not self.adc_demo_graph_enabled
        state = "enabled" if self.adc_demo_graph_enabled else "disabled"
        self._log_debug(f"ADC voltage graph {state}", "INFO")
        if self.adc_demo_graph_enabled:
            self._reset_adc_demo_series()
            if not self.is_measuring:
                self._start_adc_stream_thread()
        else:
            self._stop_adc_stream_thread()
        self._update_graphs()

    def _adc_demo_volts_to_mv(self, v_list):
        return [x * 1000.0 for x in v_list] if v_list else []

    def _adc_demo_ylim_mv(self, tx_mv, rx_mv):
        """Baseline 0..1000 mV; expand upper bound when signal exceeds with padding."""
        all_mv = list(tx_mv) + list(rx_mv)
        if not all_mv:
            return 0.0, 1000.0
        vmax = max(all_mv)
        pad = max(30.0, (vmax - min(all_mv)) * 0.12) if len(all_mv) > 1 else 40.0
        y_high = max(1000.0, vmax + pad)
        return 0.0, y_high

    def _render_adc_live_readout(self):
        """Bottom-left numeric readout (axes coordinates)."""
        txv = self.adc_demo_tx_v if self.adc_demo_tx_v else []
        rxv = self.adc_demo_rx_v if self.adc_demo_rx_v else []
        tx_mv = txv[-1] * 1000.0 if txv else 0.0
        rx_mv = rxv[-1] * 1000.0 if rxv else 0.0
        d_mv = tx_mv - rx_mv
        n = self.adc_demo_sample_count
        rate = self.adc_demo_sample_rate_hz
        body = (
            f"TX  {tx_mv:7.1f} mV\n"
            f"RX  {rx_mv:7.1f} mV\n"
            f"\u0394   {d_mv:+7.1f} mV\n"
            f"N={n}   {rate:.2f} samp/s"
        )
        t = self.theme
        self.ax4.text(
            0.02, 0.02, body,
            transform=self.ax4.transAxes,
            ha="left", va="bottom",
            fontsize=8, family=_MONO,
            color=t['text'],
            bbox=dict(
                boxstyle="round,pad=0.35",
                facecolor=t['bg_elevated'],
                edgecolor=t['border'],
                alpha=0.92,
            ),
        )

    def _render_adc_placeholder(self):
        self.ax4.clear()
        self.ax4.set_xlim(0, 1)
        self.ax4.set_ylim(0, 1)
        self.ax4.grid(False)
        self.ax4.set_xticks([])
        self.ax4.set_yticks([])
        self.ax4.text(
            0.5, 0.58, "ADC demo disabled",
            ha="center", va="center",
            fontsize=12, fontweight="bold",
            color=self._t('text'),
            transform=self.ax4.transAxes
        )
        self.ax4.text(
            0.5, 0.42, "Enable via View -> Toggle ADC Voltage Graph",
            ha="center", va="center",
            fontsize=9,
            color=self._t('text_sec'),
            transform=self.ax4.transAxes
        )

    def _create_center_panel(self) -> None:
        center = tk.Frame(self, bg=self._t('bg'))
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1, pady=1)

        center.rowconfigure(0, weight=1)
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)
        center.columnconfigure(1, weight=1)

        t = self.theme
        fc = t['bg_panel']
        tc = t['text']
        sc = t['text_sec']
        gc = t['grid']
        dpi = 72

        def make_graph(parent, row, col, title_text, ylabel_text, xlabel_text="Angle (\u00b0)"):
            frame = tk.Frame(parent, bg=fc, highlightbackground=t['border'],
                             highlightthickness=1)
            frame.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
            fig = Figure(figsize=(5, 3), dpi=dpi, facecolor=fc)
            ax = fig.add_subplot(111, facecolor=fc)
            ax.set_xlim(0, 90)
            ax.set_title(title_text, color=tc, fontsize=10, fontweight='bold', pad=8)
            ax.set_xlabel(xlabel_text, color=sc, fontsize=9)
            ax.set_ylabel(ylabel_text, color=sc, fontsize=9)
            ax.grid(True, alpha=0.4, color=gc, linestyle='--', linewidth=0.5)
            ax.tick_params(colors=sc, labelsize=8)
            for sp in ['top', 'right']:
                ax.spines[sp].set_visible(False)
            for sp in ['left', 'bottom']:
                ax.spines[sp].set_color(t['border'])
            fig.tight_layout(pad=1.5)
            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            canvas.draw_idle()
            return fig, ax, canvas

        self.fig1, self.ax1, self.canvas1 = make_graph(center, 0, 0,
            "S21 Magnitude vs Angle", "|S21| (dB)")
        self.ax1.set_ylim(-40, 5)

        self.fig2, self.ax2, self.canvas2 = make_graph(center, 0, 1,
            "S11 Magnitude vs Angle", "|S11| (dB)")
        self.ax2.set_ylim(-40, 5)

        self.fig3, self.ax3, self.canvas3 = make_graph(center, 1, 0,
            "TX / RX Power vs Angle", "Power (dBm)")
        self.ax3.set_ylim(-30, 10)

        self.fig4, self.ax4, self.canvas4 = make_graph(center, 1, 1,
            "ADC Voltage vs Time", "Voltage (mV)", xlabel_text="Time (s)")
        self.ax4.set_xlim(0, max(10.0, self.adc_demo_window_sec))
        self.ax4.set_ylim(0, 1000)

        self.center_frame = center
        self.measurement_angles = []
        self.measurement_permittivity = []
        self.measurement_permeability = []
        self.measurement_transmitted_power = []
        self.measurement_reflected_power = []
        self.measurement_transmitted_phase = []
        self.measurement_reflected_phase = []

        def on_resize(event):
            if self.resize_timer:
                self.after_cancel(self.resize_timer)
            def do_resize():
                try:
                    for c in [self.canvas1, self.canvas2, self.canvas3, self.canvas4]:
                        c.draw_idle()
                except:
                    pass
                self.resize_timer = None
            self.resize_timer = self.after(self.resize_delay, do_resize)
        self.bind('<Configure>', on_resize)

    def _style_ax(self, ax, title, ylabel, xlabel="Angle (\u00b0)"):
        t = self.theme
        ax.set_title(title, color=t['text'], fontsize=10, fontweight='bold', pad=8)
        ax.set_xlabel(xlabel, color=t['text_sec'], fontsize=9)
        ax.set_ylabel(ylabel, color=t['text_sec'], fontsize=9)
        ax.grid(True, alpha=0.4, color=t['grid'], linestyle='--', linewidth=0.5)
        ax.tick_params(colors=t['text_sec'], labelsize=8)
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)
        for sp in ['left', 'bottom']:
            ax.spines[sp].set_color(t['border'])

    def _update_graphs(self):
        measurements = self._get_measurements_for_graph()
        n = len(measurements) if measurements else 0
        toggle_changed = getattr(self, '_last_adc_graph_enabled_state', None) != self.adc_demo_graph_enabled
        self._last_adc_graph_enabled_state = self.adc_demo_graph_enabled
        adc_sample_changed = self.adc_demo_sample_count != getattr(self, '_last_adc_sample_count', -1)
        self._last_adc_sample_count = self.adc_demo_sample_count
        data_changed = n != self._last_graph_count
        if not data_changed and not toggle_changed and not adc_sample_changed:
            return
        self._last_graph_count = n
        t = self.theme
        p1, p2 = t['plot1'], t['plot2']

        # --- Separate measurements by polarization ---
        pol0_m  = [m for m in measurements if (getattr(m, 'polarization', 0.0) or 0.0) < 45.0]
        pol90_m = [m for m in measurements if (getattr(m, 'polarization', 0.0) or 0.0) >= 45.0]

        # Sweep progress label
        sweep_prog = ""
        if self.is_measuring:
            pol = getattr(self, 'current_polarization', 0.0)
            pts = len(pol0_m) if pol < 45.0 else len(pol90_m)
            sweep_num = 1 if pol < 45.0 else 2
            sweep_prog = f"  — Sweep {sweep_num}/2 · {pts} pts"

        if not measurements:
            for ax, title, yl, ylim in [
                (self.ax1, "S21 Magnitude vs Angle", "|S21| (dB)", (-40, 5)),
                (self.ax2, "S11 Magnitude vs Angle", "|S11| (dB)", (-40, 5)),
                (self.ax3, "TX / RX Power vs Angle", "Power (dBm)", (-30, 10)),
            ]:
                ax.clear()
                ax.set_xlim(0, 90)
                ax.set_ylim(*ylim)
                self._style_ax(ax, title, yl)
        else:
            # --- Graph 1: S21 magnitude (dB) vs angle, split by polarization ---
            self.ax1.clear()
            if pol0_m:
                a0  = [m.angle for m in pol0_m]
                s21_0 = [m.transmitted_power if m.transmitted_power is not None else -60.0 for m in pol0_m]
                self.ax1.plot(a0, s21_0, color=p1, linewidth=1.8, marker='o', markersize=4,
                              label='Pol 0°')
            if pol90_m:
                a90 = [m.angle for m in pol90_m]
                s21_90 = [m.transmitted_power if m.transmitted_power is not None else -60.0 for m in pol90_m]
                self.ax1.plot(a90, s21_90, color=p2, linewidth=1.8, marker='s', markersize=4,
                              linestyle='--', label='Pol 90°')
            if pol0_m or pol90_m:
                all_a = [m.angle for m in measurements]
                all_v = [m.transmitted_power for m in measurements if m.transmitted_power is not None]
                self.ax1.set_xlim(max(0, min(all_a)-5), min(90, max(all_a)+5))
                if all_v:
                    self.ax1.set_ylim(min(all_v)-3, max(all_v)+3)
                self.ax1.legend(loc='best', fontsize=8, framealpha=0.5)
            self._style_ax(self.ax1, f"S21 Magnitude vs Angle{sweep_prog}", "|S21| (dB)")

            # --- Graph 2: S11 magnitude (dB) vs angle, split by polarization ---
            self.ax2.clear()
            if pol0_m:
                a0  = [m.angle for m in pol0_m]
                s11_0 = [m.reflected_power if m.reflected_power is not None else -60.0 for m in pol0_m]
                self.ax2.plot(a0, s11_0, color=p1, linewidth=1.8, marker='o', markersize=4,
                              label='Pol 0°')
            if pol90_m:
                a90 = [m.angle for m in pol90_m]
                s11_90 = [m.reflected_power if m.reflected_power is not None else -60.0 for m in pol90_m]
                self.ax2.plot(a90, s11_90, color=p2, linewidth=1.8, marker='s', markersize=4,
                              linestyle='--', label='Pol 90°')
            if pol0_m or pol90_m:
                all_a = [m.angle for m in measurements]
                all_v = [m.reflected_power for m in measurements if m.reflected_power is not None]
                self.ax2.set_xlim(max(0, min(all_a)-5), min(90, max(all_a)+5))
                if all_v:
                    self.ax2.set_ylim(min(all_v)-3, max(all_v)+3)
                self.ax2.legend(loc='best', fontsize=8, framealpha=0.5)
            self._style_ax(self.ax2, "S11 Magnitude vs Angle", "|S11| (dB)")

            # --- Graph 3: TX/RX power with pol markers ---
            tx_pow = [m.transmitted_power if m.transmitted_power is not None else 0.0 for m in measurements]
            rx_pow = [m.reflected_power if m.reflected_power is not None else 0.0 for m in measurements]
            angles_all = [m.angle for m in measurements]
            self.ax3.clear()
            if pol0_m:
                a0 = [m.angle for m in pol0_m]
                self.ax3.plot(a0,
                    [m.transmitted_power if m.transmitted_power is not None else 0.0 for m in pol0_m],
                    color=p1, linewidth=1.8, marker='o', markersize=3, label='TX 0°')
                self.ax3.plot(a0,
                    [m.reflected_power if m.reflected_power is not None else 0.0 for m in pol0_m],
                    color=p1, linewidth=1.2, marker='o', markersize=3, linestyle=':', label='RX 0°', alpha=0.7)
            if pol90_m:
                a90 = [m.angle for m in pol90_m]
                self.ax3.plot(a90,
                    [m.transmitted_power if m.transmitted_power is not None else 0.0 for m in pol90_m],
                    color=p2, linewidth=1.8, marker='s', markersize=3, linestyle='--', label='TX 90°')
                self.ax3.plot(a90,
                    [m.reflected_power if m.reflected_power is not None else 0.0 for m in pol90_m],
                    color=p2, linewidth=1.2, marker='s', markersize=3, linestyle=':', label='RX 90°', alpha=0.7)
            self.ax3.legend(loc='best', fontsize=7, framealpha=0.5, ncol=2)
            if angles_all:
                self.ax3.set_xlim(max(0, min(angles_all)-5), min(90, max(angles_all)+5))
                all_p = [v for v in tx_pow + rx_pow if v != 0.0]
                if all_p:
                    self.ax3.set_ylim(min(all_p)-5, max(all_p)+5)
            self._style_ax(self.ax3, "TX / RX Power vs Angle", "Power (dBm)")

        # --- Graph 4: ADC live voltage — only redraw when ADC data changed ---
        if self.is_measuring or self.adc_demo_graph_enabled:
            self.ax4.clear()
            tt = self.adc_demo_t if self.adc_demo_t else []
            txv = self.adc_demo_tx_v if self.adc_demo_tx_v else []
            rxv = self.adc_demo_rx_v if self.adc_demo_rx_v else []
            tx_mv = self._adc_demo_volts_to_mv(txv)
            rx_mv = self._adc_demo_volts_to_mv(rxv)
            n_pts = min(len(tt), len(tx_mv), len(rxv))
            if n_pts > 0:
                tt_p = tt[-n_pts:]
                tx_p = tx_mv[-n_pts:]
                rx_p = rx_mv[-n_pts:]
                self.ax4.plot(tt_p, tx_p, color=p1, linewidth=1.8, label='TX')
                self.ax4.plot(tt_p, rx_p, color=p2, linewidth=1.8, label='RX')
                self.ax4.legend(loc='upper right', fontsize=8, framealpha=0.5)
                x0 = max(0.0, tt_p[-1] - self.adc_demo_window_sec)
                self.ax4.set_xlim(x0, max(x0 + 1.0, tt_p[-1] + 0.2))
                y0, y1 = self._adc_demo_ylim_mv(tx_p, rx_p)
                self.ax4.set_ylim(y0, y1)
            else:
                self.ax4.set_xlim(0, max(10.0, self.adc_demo_window_sec))
                self.ax4.set_ylim(0.0, 1000.0)
            adc_title = (
                f"ADC Live  "
                f"(N={self.adc_demo_sample_count}, "
                f"~{self.adc_demo_sample_rate_hz:.1f} samp/s)"
            )
            self._style_ax(self.ax4, adc_title, "Voltage (mV)", xlabel="Time (s)")
            self._render_adc_live_readout()
        else:
            self._render_adc_placeholder()

        for c in [self.canvas1, self.canvas2, self.canvas3, self.canvas4]:
            c.draw_idle()

    def _update_display(self):
        self._update_graphs()
        measurements = self._get_measurements_for_graph()
        if measurements:
            latest = measurements[-1]
            self.angle_var.set(f"{latest.angle:.1f}\u00b0")
            self.current_angle = latest.angle
        else:
            self.angle_var.set("0.0\u00b0")

        # Live S-param display
        self.s21_var.set(f"{self.s21_mag:.3f}\u2220{self.s21_phase:.1f}\u00b0")
        self.s11_var.set(f"{self.s11_mag:.3f}\u2220{self.s11_phase:.1f}\u00b0")
        self.s12_var.set(f"{self.s12_mag:.3f}\u2220{self.s12_phase:.1f}\u00b0")
        self.s22_var.set(f"{self.s22_mag:.3f}\u2220{self.s22_phase:.1f}\u00b0")

        # Polarization + sweep progress
        pol = getattr(self, 'current_polarization', 0.0)
        self.polarization_var.set(f"{pol:.0f}\u00b0")
        if self.is_measuring:
            pol0_count = getattr(self, '_sweep_pts_pol0', 0)
            pol90_count = getattr(self, '_sweep_pts_pol90', 0)
            if pol < 45.0:
                self.sweep_progress_var.set(f"Sweep 1/2 \u2014 {pol0_count}/17 pts")
            else:
                self.sweep_progress_var.set(f"Sweep 2/2 \u2014 {pol90_count}/17 pts")
        else:
            self.sweep_progress_var.set("Idle")

        self.motor_position_var.set(f"{self.current_angle:.1f}\u00b0")
        self.freq_var.set(f"{self.frequency:.1f} GHz")
        self.power_var.set(f"{self.power_level:.1f} dBm")
        self.angle_step_var.set(f"{self.angle_step:.1f}\u00b0")
        self.interval_var.set(f"{self.measurement_interval:.2f} s")
        self.thickness_var.set(f"{self.extraction_d_mil:.1f} mil")
        self.extract_type_var.set(self.extraction_tensor_type)
        if not self.is_measuring:
            self.calibration_error = 0.0
            self.noise_level = 0.0
        self.cal_error_var.set(f"{self.calibration_error:.2f}%")
        self.noise_var.set(f"{self.noise_level:.1f} dB")
        # Faster refresh during sweep, slower when idle
        interval = 500 if self.is_measuring else 2000
        self.after(interval, self._update_display)
