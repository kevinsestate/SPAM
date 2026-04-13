"""StatusBarMixin: bottom status bar creation."""

import tkinter as tk
from datetime import datetime

from ..themes import _FONT


class StatusBarMixin:
    """Provides _create_status_bar for the bottom status bar."""

    def _create_status_bar(self) -> None:
        sf = tk.Frame(self, bg=self._t('bg_sidebar'), height=28)
        sf.pack(side=tk.BOTTOM, fill=tk.X)
        sf.pack_propagate(False)
        left = tk.Frame(sf, bg=self._t('bg_sidebar'))
        left.pack(side=tk.LEFT, fill=tk.Y)
        self._status_dot = tk.Label(left, text="\u25cf", bg=self._t('bg_sidebar'),
                                    fg=self._t('success'), font=(_FONT, 8))
        self._status_dot.pack(side=tk.LEFT, padx=(10, 4))
        self.status_text_var = tk.StringVar(value="System Ready")
        tk.Label(left, textvariable=self.status_text_var, bg=self._t('bg_sidebar'),
                 fg=self._t('text_sec'), font=(_FONT, 9)).pack(side=tk.LEFT)
        right = tk.Frame(sf, bg=self._t('bg_sidebar'))
        right.pack(side=tk.RIGHT, fill=tk.Y)
        self.time_label = tk.Label(right, text="", bg=self._t('bg_sidebar'),
                                   fg=self._t('text_sec'), font=(_FONT, 8))
        self.time_label.pack(side=tk.RIGHT, padx=10)
        self.status_frame = sf
        self._tick_clock()

    def _tick_clock(self):
        try:
            self.time_label.config(text=datetime.now().strftime("%H:%M:%S"))
            self.after(1000, self._tick_clock)
        except tk.TclError:
            pass
