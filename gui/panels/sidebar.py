"""SidebarMixin: left icon rail."""

import tkinter as tk

from ..themes import _FONT, _ICON_FONT


class SidebarMixin:
    """Provides _create_sidebar for the 56px icon rail."""

    def _create_sidebar(self) -> None:
        rail = tk.Frame(self, bg=self._t('bg_sidebar'), width=56)
        rail.pack(side=tk.LEFT, fill=tk.Y)
        rail.pack_propagate(False)

        # branding
        tk.Label(rail, text="S", bg=self._t('bg_sidebar'), fg=self._t('accent'),
                 font=(_FONT, 18, "bold")).pack(pady=(12, 16))
        self._sep(rail)

        action_icons = [
            ("\u2699", "Calibrate",       self._on_calibrate,         "accent"),
            ("\u25b6", "Start",           self._on_start_measurement, "success"),
            ("\u25a0", "Stop",            self._on_stop_measurement,  "danger"),
            ("\u2715", "Clear",           self._on_clear_measurements,"warn"),
        ]
        utility_icons = [
            ("\u2302", "Home",            self._on_home,              "ghost"),
            ("\u2756", "Results",         self._on_view_results,      "ghost"),
            ("\u21a5", "Export",          self._on_export,            "ghost"),
            (">_",     "Debug",           self._on_debug_console,     "ghost"),
        ]

        self.buttons = []
        self.start_button = None; self.stop_button = None
        self.start_container = None; self.stop_container = None
        self.clear_container = None

        colors_map = {
            "accent":  (self._t('accent'), self._t('accent_hover'), self._t('text_em')),
            "success": (self._t('success'), '#3DAA9A',              self._t('text_em')),
            "danger":  (self._t('error'),  '#D32F2F',               self._t('text_em')),
            "warn":    (self._t('warning'),'#D4A017',               self._t('bg')),
            "ghost":   (self._t('bg_sidebar'), self._t('border_vis'), self._t('text_sec')),
        }

        for icon, tip, cmd, sty in action_icons:
            ctr = tk.Frame(rail, bg=self._t('bg_sidebar'))
            ctr.pack(fill=tk.X, padx=6, pady=3)
            bg_c, hover_c, fg_c = colors_map[sty]
            btn = tk.Button(ctr, text=icon, command=cmd, bg=bg_c, fg=fg_c,
                            activebackground=hover_c, activeforeground=fg_c,
                            font=(_ICON_FONT, 14), relief=tk.FLAT, bd=0,
                            highlightthickness=0, cursor="hand2")
            btn.pack(fill=tk.X, ipady=8)
            self._attach_tooltip(btn, tip, bg_c, hover_c)
            if tip == "Start":
                self.start_button = btn; self.start_container = ctr
            elif tip == "Stop":
                self.stop_button = btn; self.stop_container = ctr
                ctr.pack_forget()
            elif tip == "Clear":
                self.clear_container = ctr
            self.buttons.append(btn)

        self._sep(rail)

        for icon, tip, cmd, sty in utility_icons:
            ctr = tk.Frame(rail, bg=self._t('bg_sidebar'))
            ctr.pack(fill=tk.X, padx=6, pady=3)
            bg_c, hover_c, fg_c = colors_map[sty]
            font = (_FONT, 9, "bold") if icon == ">_" else (_ICON_FONT, 14)
            btn = tk.Button(ctr, text=icon, command=cmd, bg=bg_c, fg=fg_c,
                            activebackground=hover_c, activeforeground=fg_c,
                            font=font, relief=tk.FLAT, bd=0,
                            highlightthickness=0, cursor="hand2")
            btn.pack(fill=tk.X, ipady=8)
            self._attach_tooltip(btn, tip, bg_c, hover_c)
            self.buttons.append(btn)

        tk.Frame(rail, bg=self._t('bg_sidebar')).pack(expand=True)

        # theme toggle at bottom
        theme_icon = "\u263e" if self._theme_name == "dark" else "\u2600"
        tbtn = tk.Button(rail, text=theme_icon, command=self._toggle_theme,
                         bg=self._t('bg_sidebar'), fg=self._t('text_sec'),
                         font=(_ICON_FONT, 12), relief=tk.FLAT, bd=0,
                         highlightthickness=0, cursor="hand2")
        tbtn.pack(pady=(0, 4))

        tk.Label(rail, text="v1.01", bg=self._t('bg_sidebar'),
                 fg=self._t('text_sec'), font=(_FONT, 7)).pack(pady=(0, 8))

        self.sidebar_frame = rail
