"""DialogBaseMixin: _themed_dialog, _dialog_entry_row."""

import tkinter as tk

from ..themes import _FONT, _MONO


class DialogBaseMixin:
    """Provides themed dialog window factory and entry row helper."""

    def _themed_dialog(self, title, width=420, height=340):
        d = tk.Toplevel(self)
        d.title(title)
        d.geometry(f"{width}x{height}")
        d.configure(bg=self._t('bg'))
        d.transient(self)
        d.grab_set()
        d.update_idletasks()
        x = (d.winfo_screenwidth() // 2) - (width // 2)
        y = (d.winfo_screenheight() // 2) - (height // 2)
        d.geometry(f"{width}x{height}+{x}+{y}")
        return d

    def _dialog_entry_row(self, parent, label_text, var, row):
        tk.Label(parent, text=label_text, bg=self._t('bg_panel'), fg=self._t('text'),
                 font=(_FONT, 9), anchor="w").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 8))
        e = tk.Entry(parent, textvariable=var, bg=self._t('bg_input'), fg=self._t('text'),
                     font=(_MONO, 9), width=20, relief=tk.FLAT,
                     insertbackground=self._t('text'), highlightbackground=self._t('border'),
                     highlightthickness=1)
        e.grid(row=row, column=1, sticky="ew", pady=6)
        return e
