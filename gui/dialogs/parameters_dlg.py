"""ParametersDialogMixin: adjust measurement parameters dialog."""

import tkinter as tk
from tkinter import messagebox

from ..themes import _FONT


class ParametersDialogMixin:
    """Provides _on_adjust_parameters dialog."""

    def _on_adjust_parameters(self):
        d = self._themed_dialog("Adjust Parameters", 440, 380)
        tk.Label(d, text="Measurement Parameters", bg=self._t('bg'),
                 fg=self._t('text'), font=(_FONT, 12, "bold")).pack(pady=(16, 12))
        content = tk.Frame(d, bg=self._t('bg_panel'), padx=16, pady=16)
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        content.columnconfigure(1, weight=1)
        step_v = tk.StringVar(value=str(self.angle_step))
        int_v = tk.StringVar(value=str(self.measurement_interval))
        for i, (lbl, v) in enumerate([("Angle Step (\u00b0):", step_v), ("Interval (s):", int_v)]):
            self._dialog_entry_row(content, lbl, v, i)
        def save():
            try:
                self.angle_step = float(step_v.get())
                self.measurement_interval = float(int_v.get())
                self._log_debug(f"Params: step={self.angle_step} int={self.measurement_interval}", "INFO")
                self._update_status("Parameters updated", "success")
                d.destroy()
            except ValueError as e:
                messagebox.showerror("Invalid", str(e), parent=d)
        bf = tk.Frame(d, bg=self._t('bg'))
        bf.pack(fill=tk.X, padx=16, pady=(0, 16))
        self._make_btn(bf, "Cancel", d.destroy, "ghost").pack(side=tk.RIGHT, padx=(4, 0))
        self._make_btn(bf, "Save", save, "accent").pack(side=tk.RIGHT)
