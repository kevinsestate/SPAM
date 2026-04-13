"""DetailPanelMixin: right detail panel + all StringVars."""

import tkinter as tk
from tkinter import ttk

from ..themes import _FONT, _MONO


class DetailPanelMixin:
    """Provides _create_detail_panel for the right-side info panel with StringVars."""

    def _create_detail_panel(self) -> None:
        pf = tk.Frame(self, bg=self._t('bg_panel'), width=280)
        pf.pack(side=tk.RIGHT, fill=tk.Y)
        pf.pack_propagate(False)

        # scrollable interior
        canvas = tk.Canvas(pf, bg=self._t('bg_panel'), highlightthickness=0, width=280)
        sb = ttk.Scrollbar(pf, orient=tk.VERTICAL, command=canvas.yview)
        inner = tk.Frame(canvas, bg=self._t('bg_panel'))
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        def _resize_inner(e):
            canvas.itemconfig("inner", width=e.width)
        canvas.bind("<Configure>", _resize_inner)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # scoped mousewheel
        def _on_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        def _bind_wheel(e):
            canvas.bind_all("<MouseWheel>", _on_wheel)
        def _unbind_wheel(e):
            canvas.unbind_all("<MouseWheel>")
        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)

        self._collapsed = {}

        def section(parent, title, items, mono_val=True):
            hdr = tk.Frame(parent, bg=self._t('bg_panel'))
            hdr.pack(fill=tk.X, padx=10, pady=(10, 0))
            tk.Label(hdr, text=title.upper(), bg=self._t('bg_panel'),
                     fg=self._t('text_sec'), font=(_FONT, 8, "bold"),
                     anchor="w").pack(side=tk.LEFT)
            body = tk.Frame(parent, bg=self._t('bg_panel'))
            body.pack(fill=tk.X, padx=10, pady=(2, 0))
            self._sep(parent)
            val_font = (_MONO, 10) if mono_val else (_FONT, 10, "bold")
            for lbl_text, var in items:
                row = tk.Frame(body, bg=self._t('bg_panel'))
                row.pack(fill=tk.X, pady=2)
                tk.Label(row, text=lbl_text, bg=self._t('bg_panel'),
                         fg=self._t('text_sec'), font=(_FONT, 9),
                         anchor="w").pack(side=tk.LEFT)
                tk.Label(row, textvariable=var, bg=self._t('bg_panel'),
                         fg=self._t('text'), font=val_font,
                         anchor="e").pack(side=tk.RIGHT)

        # -- StringVars --
        self.angle_var = tk.StringVar(value="0.0\u00b0")
        self.permittivity_var = tk.StringVar(value="--")
        self.permeability_var = tk.StringVar(value="--")
        self.polarization_var = tk.StringVar(value="0\u00b0")
        self.sweep_progress_var = tk.StringVar(value="Idle")
        self.cal_status_var = tk.StringVar(value="\u2717 None")
        self.status_var = tk.StringVar(value="Ready")
        self.s11_var = tk.StringVar(value="0.000\u22200.0\u00b0")
        self.s12_var = tk.StringVar(value="0.000\u22200.0\u00b0")
        self.s21_var = tk.StringVar(value="0.000\u22200.0\u00b0")
        self.s22_var = tk.StringVar(value="0.000\u22200.0\u00b0")
        self.system_status_var = tk.StringVar(value="Ready")

        self.freq_var = tk.StringVar(value="10.0 GHz")
        self.power_var = tk.StringVar(value="-10.0 dBm")
        self.angle_step_var = tk.StringVar(value="5.0\u00b0")
        self.interval_var = tk.StringVar(value="0.50 s")
        self.thickness_var = tk.StringVar(value=f"{self.extraction_d_mil:.1f} mil")
        self.extract_type_var = tk.StringVar(value=self.extraction_tensor_type)
        self.cal_error_var = tk.StringVar(value="0.00%")
        self.noise_var = tk.StringVar(value="0.0 dB")

        section(inner, "Measurement", [
            ("Angle", self.angle_var),
            ("Polarization", self.polarization_var),
            ("Sweep", self.sweep_progress_var),
            ("Cal Data", self.cal_status_var),
            ("Status", self.status_var),
        ])
        section(inner, "Extracted Material", [
            ("\u03b5r diag", self.extraction_eps_var),
            ("\u03bcr diag", self.extraction_mu_var),
            ("Fit Error", self.extraction_error_var),
        ])
        section(inner, "Motor", [
            ("Status", self.motor_status_var),
            ("Position", self.motor_position_var),
        ])
        section(inner, "S-Parameters", [
            ("S\u2081\u2081", self.s11_var), ("S\u2081\u2082", self.s12_var),
            ("S\u2082\u2081", self.s21_var), ("S\u2082\u2082", self.s22_var),
        ])
        section(inner, "Extraction Config", [
            ("Status", self.extraction_status_var),
            ("Thickness (mil)", self.thickness_var),
            ("Tensor Type", self.extract_type_var),
        ])
        section(inner, "Parameters", [
            ("Frequency", self.freq_var), ("Power", self.power_var),
            ("Angle Step", self.angle_step_var), ("Interval", self.interval_var),
        ])
        section(inner, "Environment", [
            ("Cal Error", self.cal_error_var), ("Noise", self.noise_var),
        ])

        # system status at bottom
        tk.Frame(inner, bg=self._t('bg_panel')).pack(expand=True)
        row = tk.Frame(inner, bg=self._t('bg_panel'))
        row.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(row, text="System", bg=self._t('bg_panel'),
                 fg=self._t('text_sec'), font=(_FONT, 8)).pack(side=tk.LEFT)
        tk.Label(row, textvariable=self.system_status_var, bg=self._t('bg_panel'),
                 fg=self._t('success'), font=(_MONO, 10)).pack(side=tk.RIGHT)

        self.info_frame = pf
