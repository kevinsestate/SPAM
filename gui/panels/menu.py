"""MenuMixin: top menu bar creation."""

import tkinter as tk

from ..themes import _FONT


class MenuMixin:
    """Provides _create_menu for the application menu bar."""

    def _create_menu(self) -> None:
        menubar = tk.Menu(self, bg=self._t('bg_elevated'), fg=self._t('text'),
                          activebackground=self._t('accent'), activeforeground=self._t('text_em'),
                          borderwidth=0)
        file_menu = tk.Menu(menubar, tearoff=0, bg=self._t('bg_panel'), fg=self._t('text'),
                            activebackground=self._t('accent'), activeforeground=self._t('text_em'))
        file_menu.add_command(label="Export Data", command=self._on_export)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)
        settings_menu = tk.Menu(menubar, tearoff=0, bg=self._t('bg_panel'), fg=self._t('text'),
                                activebackground=self._t('accent'), activeforeground=self._t('text_em'))
        settings_menu.add_command(label="Adjust Parameters", command=self._on_adjust_parameters)
        settings_menu.add_command(label="Connection Setup", command=self._on_connection_setup)
        settings_menu.add_command(label="Extraction Settings", command=self._on_extraction_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label="Toggle Dark/Light Theme", command=self._toggle_theme)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        view_menu = tk.Menu(menubar, tearoff=0, bg=self._t('bg_panel'), fg=self._t('text'),
                            activebackground=self._t('accent'), activeforeground=self._t('text_em'))
        view_menu.add_command(label="Debug Console", command=self._on_debug_console, accelerator="Ctrl+D")
        view_menu.add_separator()
        view_menu.add_command(label="Fullscreen", command=self._toggle_fullscreen, accelerator="F11")
        menubar.add_cascade(label="View", menu=view_menu)
        help_menu = tk.Menu(menubar, tearoff=0, bg=self._t('bg_panel'), fg=self._t('text'),
                            activebackground=self._t('accent'), activeforeground=self._t('text_em'))
        help_menu.add_command(label="About SPAM", command=self._on_help)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.bind('<Control-d>', lambda e: self._on_debug_console())
        self.bind('<F11>', lambda e: self._toggle_fullscreen())
        self.bind('<Escape>', lambda e: self._exit_fullscreen() if self.is_fullscreen else None)
        self.config(menu=menubar)
