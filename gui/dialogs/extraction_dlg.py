"""ExtractionDialogMixin: extraction settings dialog."""

import tkinter as tk
from tkinter import ttk, messagebox

from ..themes import _FONT


class ExtractionDialogMixin:
    """Provides _on_extraction_settings dialog."""

    def _on_extraction_settings(self):
        d = self._themed_dialog("Extraction Settings", 430, 360)
        tk.Label(d, text="Material Extraction Settings", bg=self._t('bg'),
                 fg=self._t('text'), font=(_FONT, 12, "bold")).pack(pady=(16, 12))
        content = tk.Frame(d, bg=self._t('bg_panel'), padx=16, pady=16)
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        content.columnconfigure(1, weight=1)
        f0_var = tk.StringVar(value=str(self.extraction_f0_ghz))
        d_var = tk.StringVar(value=str(self.extraction_d_mil))
        type_var = tk.StringVar(value=self.extraction_tensor_type)
        self._dialog_entry_row(content, "Frequency (GHz):", f0_var, 0)
        self._dialog_entry_row(content, "Thickness (mil, 1-500):", d_var, 1)
        tk.Label(content,
                 text="Advisory: choose thickness to avoid resonance-sensitive regimes.",
                 bg=self._t('bg_panel'), fg=self._t('text_sec'), font=(_FONT, 8),
                 anchor="w").grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 6))
        tk.Label(content, text="Tensor Type:", bg=self._t('bg_panel'), fg=self._t('text'),
                 font=(_FONT, 9)).grid(row=3, column=0, sticky="w", pady=6, padx=(0, 8))
        ttk.Combobox(content, textvariable=type_var, state="readonly",
                     values=["isotropic", "diagonal", "symmetric"],
                     width=17).grid(row=3, column=1, sticky="ew", pady=6)
        def save():
            try:
                f0_ghz = float(f0_var.get())
                d_mil = float(d_var.get())
                tensor_type = type_var.get()
                if f0_ghz <= 0:
                    raise ValueError("Frequency must be greater than 0 GHz.")
                if d_mil < 1 or d_mil > 500:
                    raise ValueError("Thickness must be between 1 and 500 mil.")
                if tensor_type not in ("isotropic", "diagonal", "symmetric"):
                    raise ValueError("Tensor type must be isotropic, diagonal, or symmetric.")

                self.extraction_f0_ghz = f0_ghz
                self.extraction_d_mil = d_mil
                self.extraction_tensor_type = tensor_type

                self.connection_settings['extraction_f0_ghz'] = str(self.extraction_f0_ghz)
                self.connection_settings['extraction_d_mil'] = str(self.extraction_d_mil)
                self.connection_settings['extraction_tensor_type'] = self.extraction_tensor_type
                self._save_connection_settings()

                advisory = self._thickness_resonance_advisory(self.extraction_f0_ghz, self.extraction_d_mil)
                self._log_debug(
                    f"Extraction settings saved: f0={self.extraction_f0_ghz:.3f}GHz "
                    f"d={self.extraction_d_mil:.2f}mil k0d={advisory['k0d']:.4f} "
                    f"type={self.extraction_tensor_type}",
                    "INFO"
                )
                self._log_debug(advisory["message"], "WARNING" if advisory["level"] == "warning" else "INFO")
                if advisory["level"] == "warning":
                    messagebox.showwarning("Thickness Advisory", advisory["message"], parent=d)
                    self._update_status("Extraction settings saved (advisory issued)", "warning")
                else:
                    self._update_status("Extraction settings saved", "success")
                d.destroy()
            except ValueError as e:
                messagebox.showerror("Invalid Extraction Settings", str(e), parent=d)
        bf = tk.Frame(content, bg=self._t('bg_panel'))
        bf.grid(row=4, column=0, columnspan=2, pady=(12, 0), sticky="e")
        self._make_btn(bf, "Cancel", d.destroy, "ghost").pack(side=tk.RIGHT, padx=(4, 0))
        self._make_btn(bf, "Save", save, "accent").pack(side=tk.RIGHT)
