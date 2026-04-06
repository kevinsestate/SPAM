"""WidgetsMixin: styled widget factory helpers."""

import tkinter as tk

from .themes import _FONT, _MONO, _ICON_FONT


class WidgetsMixin:
    """Provides _make_btn, _attach_tooltip, _sep, _t, _configure_ttk_style, _toggle_theme."""

    def _t(self, key):
        return self.theme[key]

    def _configure_ttk_style(self):
        from tkinter import ttk
        style = ttk.Style(self)
        style.theme_use('clam')
        t = self.theme
        style.configure(".", background=t['bg_panel'], foreground=t['text'],
                        fieldbackground=t['bg_input'], bordercolor=t['border'],
                        troughcolor=t['bg'], arrowcolor=t['text_sec'])
        style.configure("TNotebook", background=t['bg'], borderwidth=0)
        style.configure("TNotebook.Tab", background=t['bg_elevated'],
                        foreground=t['text_sec'], padding=[10, 4],
                        font=(_FONT, 9))
        style.map("TNotebook.Tab",
                  background=[("selected", t['bg_panel'])],
                  foreground=[("selected", t['text'])])
        style.configure("TCombobox", fieldbackground=t['bg_input'],
                        background=t['bg_elevated'], foreground=t['text'],
                        arrowcolor=t['text_sec'], borderwidth=1)
        style.configure("Treeview", background=t['bg_panel'],
                        foreground=t['text'], fieldbackground=t['bg_panel'],
                        borderwidth=0, font=(_MONO, 9))
        style.configure("Treeview.Heading", background=t['bg_elevated'],
                        foreground=t['text_sec'], font=(_FONT, 9, "bold"),
                        borderwidth=0)
        style.map("Treeview", background=[("selected", t['accent'])],
                  foreground=[("selected", t['text_em'])])
        style.configure("Vertical.TScrollbar", background=t['bg_elevated'],
                        troughcolor=t['bg'], borderwidth=0, arrowsize=12)
        style.configure("Horizontal.TScrollbar", background=t['bg_elevated'],
                        troughcolor=t['bg'], borderwidth=0, arrowsize=12)

    def _toggle_theme(self):
        from tkinter import messagebox
        from .themes import THEMES
        new = "light" if self._theme_name == "dark" else "dark"
        self._theme_name = new
        self.theme = THEMES[new]
        self.connection_settings['theme'] = new
        self._save_connection_settings()
        messagebox.showinfo("Theme Changed",
                            f"Switched to {new} theme.\n\nRestart the application for the theme to take full effect.")

    def _make_btn(self, parent, text, command, style="accent", width=None):
        colors = {
            "accent":  (self._t('accent'), self._t('accent_hover'), self._t('text_em')),
            "danger":  (self._t('error'),  '#D32F2F',               self._t('text_em')),
            "ghost":   (self._t('bg_elevated'), self._t('border_vis'), self._t('text')),
            "success": (self._t('success'), '#3DAA9A',              self._t('text_em')),
            "warn":    (self._t('warning'), '#D4A017',              self._t('bg')),
        }
        bg, hover, fg = colors.get(style, colors['accent'])
        kw = dict(text=text, command=command, bg=bg, fg=fg,
                  activebackground=hover, activeforeground=fg,
                  font=(_FONT, 9), relief=tk.FLAT, bd=0,
                  highlightthickness=0, cursor="hand2", padx=12, pady=4)
        if width:
            kw['width'] = width
        btn = tk.Button(parent, **kw)
        btn.bind('<Enter>', lambda e, b=btn, h=hover: b.config(bg=h))
        btn.bind('<Leave>', lambda e, b=btn, c=bg: b.config(bg=c))
        return btn

    def _attach_tooltip(self, widget, text, bg_normal, bg_hover):
        """Bind hover tooltip and color change to a widget, with proper closure capture."""
        def on_enter(e, w=widget, t=text, h=bg_hover):
            w.config(bg=h)
            tw = tk.Toplevel(w)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{e.x_root+20}+{e.y_root}")
            tk.Label(tw, text=t, bg=self._t('bg_elevated'), fg=self._t('text'),
                     font=(_FONT, 8), padx=6, pady=2, relief=tk.SOLID,
                     borderwidth=1).pack()
            w._tip = tw

        def on_leave(e, w=widget, c=bg_normal):
            w.config(bg=c)
            if hasattr(w, '_tip') and w._tip:
                w._tip.destroy()
                w._tip = None

        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def _sep(self, parent, orient="h"):
        f = tk.Frame(parent, bg=self._t('border'),
                     height=1 if orient == "h" else None,
                     width=1 if orient == "v" else None)
        f.pack(fill=tk.X if orient == "h" else tk.Y, padx=0, pady=0)
        return f
