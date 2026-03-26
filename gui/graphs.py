"""GraphsMixin: center panel, graph updates, _update_display."""

import tkinter as tk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .themes import _FONT, _MONO


class GraphsMixin:
    """Provides center panel creation, graph styling, graph updates, and periodic display refresh."""

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
        dpi = 100

        def make_graph(parent, row, col, title_text, ylabel_text):
            frame = tk.Frame(parent, bg=fc, highlightbackground=t['border'],
                             highlightthickness=1)
            frame.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
            fig = Figure(figsize=(5, 3), dpi=dpi, facecolor=fc)
            ax = fig.add_subplot(111, facecolor=fc)
            ax.set_xlim(0, 90)
            ax.set_title(title_text, color=tc, fontsize=10, fontweight='bold', pad=8)
            ax.set_xlabel("Angle (\u00b0)", color=sc, fontsize=9)
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
            "Permittivity (\u03b5) vs Angle", "Permittivity (\u03b5)")
        self.ax1.set_ylim(1.5, 2.5)

        self.fig2, self.ax2, self.canvas2 = make_graph(center, 0, 1,
            "Permeability (\u03bc) vs Angle", "Permeability (\u03bc)")
        self.ax2.set_ylim(1.0, 2.0)

        self.fig3, self.ax3, self.canvas3 = make_graph(center, 1, 0,
            "TX / RX Power vs Angle", "Power (dBm)")
        self.ax3.set_ylim(-30, 10)

        self.fig4, self.ax4, self.canvas4 = make_graph(center, 1, 1,
            "TX / RX Phase vs Angle", "Phase (\u00b0)")
        self.ax4.set_ylim(-180, 180)

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
                    for f in [self.fig1, self.fig2, self.fig3, self.fig4]:
                        f.tight_layout(pad=1.5)
                    for c in [self.canvas1, self.canvas2, self.canvas3, self.canvas4]:
                        c.draw_idle()
                except:
                    pass
                self.resize_timer = None
            self.resize_timer = self.after(self.resize_delay, do_resize)
        self.bind('<Configure>', on_resize)

    def _style_ax(self, ax, title, ylabel):
        t = self.theme
        ax.set_title(title, color=t['text'], fontsize=10, fontweight='bold', pad=8)
        ax.set_xlabel("Angle (\u00b0)", color=t['text_sec'], fontsize=9)
        ax.set_ylabel(ylabel, color=t['text_sec'], fontsize=9)
        ax.grid(True, alpha=0.4, color=t['grid'], linestyle='--', linewidth=0.5)
        ax.tick_params(colors=t['text_sec'], labelsize=8)
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)
        for sp in ['left', 'bottom']:
            ax.spines[sp].set_color(t['border'])

    def _update_graphs(self):
        measurements = self._get_measurements()
        n = len(measurements) if measurements else 0
        if n == self._last_graph_count and n > 0:
            return
        self._last_graph_count = n
        t = self.theme
        p1, p2 = t['plot1'], t['plot2']

        if not measurements:
            for ax, title, yl, ylim in [
                (self.ax1, "Permittivity (\u03b5) vs Angle", "Permittivity (\u03b5)", (1.5, 2.5)),
                (self.ax2, "Permeability (\u03bc) vs Angle", "Permeability (\u03bc)", (1.0, 2.0)),
                (self.ax3, "TX / RX Power vs Angle", "Power (dBm)", (-30, 10)),
                (self.ax4, "TX / RX Phase vs Angle", "Phase (\u00b0)", (-180, 180)),
            ]:
                ax.clear()
                ax.set_xlim(0, 90)
                ax.set_ylim(*ylim)
                self._style_ax(ax, title, yl)
        else:
            angles = [m.angle for m in measurements]
            perm = [m.permittivity for m in measurements]
            perm_b = [m.permeability for m in measurements]
            tx_pow = [m.transmitted_power if m.transmitted_power is not None else 0.0 for m in measurements]
            rx_pow = [m.reflected_power if m.reflected_power is not None else 0.0 for m in measurements]
            tx_ph = [m.transmitted_phase if m.transmitted_phase is not None else 0.0 for m in measurements]
            rx_ph = [m.reflected_phase if m.reflected_phase is not None else 0.0 for m in measurements]

            self.ax1.clear()
            self.ax1.plot(angles, perm, color=p1, linewidth=1.8, label='\u03b5')
            if angles:
                self.ax1.set_xlim(max(0, min(angles)-5), min(90, max(angles)+5))
                self.ax1.set_ylim(max(1.0, min(perm)-0.2), max(perm)+0.2)
            self._style_ax(self.ax1, "Permittivity (\u03b5) vs Angle", "Permittivity (\u03b5)")

            self.ax2.clear()
            self.ax2.plot(angles, perm_b, color=p2, linewidth=1.8, label='\u03bc')
            if angles:
                self.ax2.set_xlim(max(0, min(angles)-5), min(90, max(angles)+5))
                self.ax2.set_ylim(max(0.5, min(perm_b)-0.2), max(perm_b)+0.2)
            self._style_ax(self.ax2, "Permeability (\u03bc) vs Angle", "Permeability (\u03bc)")

            self.ax3.clear()
            self.ax3.plot(angles, tx_pow, color=p1, linewidth=1.8, label='TX', marker='o', markersize=3)
            self.ax3.plot(angles, rx_pow, color=p2, linewidth=1.8, label='RX', marker='s', markersize=3)
            self.ax3.legend(loc='best', fontsize=8, framealpha=0.5)
            if angles:
                self.ax3.set_xlim(max(0, min(angles)-5), min(90, max(angles)+5))
                all_p = [v for v in tx_pow + rx_pow if v != 0.0]
                if all_p:
                    self.ax3.set_ylim(min(all_p)-5, max(all_p)+5)
            self._style_ax(self.ax3, "TX / RX Power vs Angle", "Power (dBm)")

            self.ax4.clear()
            self.ax4.plot(angles, tx_ph, color=p1, linewidth=1.8, label='TX', marker='o', markersize=3)
            self.ax4.plot(angles, rx_ph, color=p2, linewidth=1.8, label='RX', marker='s', markersize=3)
            self.ax4.legend(loc='best', fontsize=8, framealpha=0.5)
            if angles:
                self.ax4.set_xlim(max(0, min(angles)-5), min(90, max(angles)+5))
            self.ax4.set_ylim(-180, 180)
            self._style_ax(self.ax4, "TX / RX Phase vs Angle", "Phase (\u00b0)")

        for f in [self.fig1, self.fig2, self.fig3, self.fig4]:
            f.tight_layout(pad=1.5)
        for c in [self.canvas1, self.canvas2, self.canvas3, self.canvas4]:
            c.draw_idle()

    def _update_display(self):
        self._update_graphs()
        measurements = self._get_measurements(limit=1)
        if measurements:
            latest = measurements[0]
            self.angle_var.set(f"{latest.angle:.1f}\u00b0")
            self.permittivity_var.set(f"{latest.permittivity:.4f}")
            self.permeability_var.set(f"{latest.permeability:.4f}")
            self.current_angle = latest.angle
            self.current_permittivity = latest.permittivity
            self.current_permeability = latest.permeability
        else:
            self.angle_var.set("0.0\u00b0")
            self.permittivity_var.set("0.00")
            self.permeability_var.set("0.00")
        self.s11_var.set(f"{self.s11_mag:.3f}\u2220{self.s11_phase:.1f}\u00b0")
        self.s12_var.set(f"{self.s12_mag:.3f}\u2220{self.s12_phase:.1f}\u00b0")
        self.s21_var.set(f"{self.s21_mag:.3f}\u2220{self.s21_phase:.1f}\u00b0")
        self.s22_var.set(f"{self.s22_mag:.3f}\u2220{self.s22_phase:.1f}\u00b0")
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
        self.after(2000, self._update_display)
