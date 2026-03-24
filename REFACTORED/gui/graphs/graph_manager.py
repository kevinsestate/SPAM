"""
Graph creation, styling, and real-time update logic.
Manages all four Matplotlib graphs embedded in Tkinter.
"""
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

from gui.colors import COLORS


# Shared styling dict
GRAPH_STYLE = {
    'facecolor': COLORS['bg_panel'],
    'titlecolor': COLORS['text_dark'],
    'titlesize': 14,
    'titleweight': 'bold',
    'labelcolor': COLORS['text_dark'],
    'labelsize': 11,
    'linecolor': COLORS['secondary'],
    'linewidth': 2.5,
    'gridcolor': COLORS['border'],
    'gridalpha': 0.3,
    'dpi': 100,
}


def _style_ax(ax, title, xlabel, ylabel):
    """Apply common styling to a Matplotlib Axes."""
    ax.set_title(title, color=GRAPH_STYLE['titlecolor'],
                 fontsize=GRAPH_STYLE['titlesize'],
                 fontweight=GRAPH_STYLE['titleweight'], pad=15)
    ax.set_xlabel(xlabel, color=GRAPH_STYLE['labelcolor'],
                  fontsize=GRAPH_STYLE['labelsize'], fontweight='medium')
    ax.set_ylabel(ylabel, color=GRAPH_STYLE['labelcolor'],
                  fontsize=GRAPH_STYLE['labelsize'], fontweight='medium')
    ax.grid(True, alpha=GRAPH_STYLE['gridalpha'],
            color=GRAPH_STYLE['gridcolor'], linestyle='--')
    ax.tick_params(colors=GRAPH_STYLE['labelcolor'], labelsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(GRAPH_STYLE['gridcolor'])
    ax.spines['bottom'].set_color(GRAPH_STYLE['gridcolor'])


class GraphManager:
    """Creates and updates the four measurement graphs."""

    def __init__(self, parent_frame: tk.Frame):
        """Build the four graphs inside *parent_frame* (a scrollable frame)."""
        s = GRAPH_STYLE

        # --- Graph 1: Permittivity ---
        self.fig1, self.ax1, self.canvas1 = self._make_graph(
            parent_frame, "Permittivity (ε) vs Angle",
            "Angle (degrees)", "Permittivity (ε)", ylim=(1.5, 2.5))

        # --- Graph 2: Permeability ---
        self.fig2, self.ax2, self.canvas2 = self._make_graph(
            parent_frame, "Permeability (μ) vs Angle",
            "Angle (degrees)", "Permeability (μ)", ylim=(1.0, 2.0))

        # --- Graph 3: Power ---
        self.fig3, self.ax3, self.canvas3 = self._make_graph(
            parent_frame, "Transmitted & Reflected Power vs Angle",
            "Angle (degrees)", "Power (dBm)", ylim=(-30, 10))

        # --- Graph 4: Phase ---
        self.fig4, self.ax4, self.canvas4 = self._make_graph(
            parent_frame, "Transmitted & Reflected Phase vs Angle",
            "Angle (degrees)", "Phase (degrees)", ylim=(-180, 180))

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------
    def _make_graph(self, parent, title, xlabel, ylabel, ylim):
        container = tk.Frame(parent, bg=COLORS['bg_panel'],
                             relief=tk.FLAT, bd=0, height=400)
        container.pack(fill=tk.X, pady=(0, 15), padx=5)
        container.pack_propagate(False)

        fig = Figure(figsize=(6, 3.5), dpi=GRAPH_STYLE['dpi'],
                     facecolor=GRAPH_STYLE['facecolor'])
        ax = fig.add_subplot(111, facecolor=GRAPH_STYLE['facecolor'])
        ax.set_xlim(0, 90)
        ax.set_ylim(*ylim)
        _style_ax(ax, title, xlabel, ylabel)
        fig.tight_layout(pad=2.0)

        canvas = FigureCanvasTkAgg(fig, master=container)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        canvas.draw()
        return fig, ax, canvas

    # ------------------------------------------------------------------
    # Update from measurement list
    # ------------------------------------------------------------------
    def update(self, measurements):
        """Redraw all four graphs from a list of Measurement objects."""
        self._update_single_trace(
            self.ax1, measurements,
            y_attr='permittivity', color=COLORS['secondary'],
            title="Permittivity (ε) vs Angle",
            ylabel="Permittivity (ε)", default_ylim=(1.5, 2.5))

        self._update_single_trace(
            self.ax2, measurements,
            y_attr='permeability', color=COLORS['accent'],
            title="Permeability (μ) vs Angle",
            ylabel="Permeability (μ)", default_ylim=(1.0, 2.0))

        self._update_dual_trace(
            self.ax3, measurements,
            y1_attr='transmitted_power', y2_attr='reflected_power',
            label1='Transmitted', label2='Reflected',
            title="Transmitted & Reflected Power vs Angle",
            ylabel="Power (dBm)", default_ylim=(-30, 10))

        self._update_dual_trace(
            self.ax4, measurements,
            y1_attr='transmitted_phase', y2_attr='reflected_phase',
            label1='Transmitted', label2='Reflected',
            title="Transmitted & Reflected Phase vs Angle",
            ylabel="Phase (degrees)", default_ylim=(-180, 180))

        # Redraw
        for fig, canvas in [(self.fig1, self.canvas1),
                            (self.fig2, self.canvas2),
                            (self.fig3, self.canvas3),
                            (self.fig4, self.canvas4)]:
            fig.tight_layout(pad=2.0)
            canvas.draw()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _update_single_trace(self, ax, measurements, y_attr, color,
                             title, ylabel, default_ylim):
        ax.clear()
        if measurements:
            angles = [m.angle for m in measurements]
            values = [getattr(m, y_attr) for m in measurements]
            ax.plot(angles, values, color=color, linewidth=2.5)
            if angles:
                ax.set_xlim(max(0, min(angles) - 5), min(90, max(angles) + 5))
                ax.set_ylim(min(values) - 0.2, max(values) + 0.2)
        else:
            ax.set_xlim(0, 90)
            ax.set_ylim(*default_ylim)
        _style_ax(ax, title, "Angle (degrees)", ylabel)

    def _update_dual_trace(self, ax, measurements, y1_attr, y2_attr,
                           label1, label2, title, ylabel, default_ylim):
        ax.clear()
        if measurements:
            angles = [m.angle for m in measurements]
            v1 = [getattr(m, y1_attr) if getattr(m, y1_attr) is not None else 0.0
                  for m in measurements]
            v2 = [getattr(m, y2_attr) if getattr(m, y2_attr) is not None else 0.0
                  for m in measurements]
            ax.plot(angles, v1, color=COLORS['secondary'], linewidth=2.5,
                    label=label1, marker='o', markersize=4)
            ax.plot(angles, v2, color=COLORS['accent'], linewidth=2.5,
                    label=label2, marker='s', markersize=4)
            ax.legend(loc='best', fontsize=9)
            if angles:
                ax.set_xlim(max(0, min(angles) - 5), min(90, max(angles) + 5))
                all_vals = [v for v in v1 + v2 if v != 0.0]
                if all_vals:
                    ax.set_ylim(min(all_vals) - 5, max(all_vals) + 5)
                else:
                    ax.set_ylim(*default_ylim)
            else:
                ax.set_xlim(0, 90)
                ax.set_ylim(*default_ylim)
        else:
            ax.set_xlim(0, 90)
            ax.set_ylim(*default_ylim)
        _style_ax(ax, title, "Angle (degrees)", ylabel)

    # ------------------------------------------------------------------
    def relayout(self):
        """Call after window resize to reflow graphs."""
        for fig, canvas in [(self.fig1, self.canvas1),
                            (self.fig2, self.canvas2),
                            (self.fig3, self.canvas3),
                            (self.fig4, self.canvas4)]:
            try:
                fig.tight_layout(pad=2.0)
                canvas.draw()
            except Exception:
                pass
