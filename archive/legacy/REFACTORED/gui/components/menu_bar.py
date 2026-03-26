"""Menu bar creation."""
import tkinter as tk


def create_menu(root, callbacks):
    """Build and attach the top menu bar.

    *callbacks* is a dict with keys:
        export, adjust_params, connection_setup, debug_console,
        toggle_fullscreen, exit_fullscreen, help
    """
    from gui.colors import COLORS
    menubar = tk.Menu(root)

    # File
    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label="Export Data", command=callbacks['export'])
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.destroy)
    menubar.add_cascade(label="File", menu=file_menu)

    # Settings
    settings_menu = tk.Menu(menubar, tearoff=0)
    settings_menu.add_command(label="Adjust Parameters",
                              command=callbacks['adjust_params'])
    settings_menu.add_command(label="Connection Setup",
                              command=callbacks['connection_setup'])
    menubar.add_cascade(label="Settings", menu=settings_menu)

    # View
    view_menu = tk.Menu(menubar, tearoff=0)
    view_menu.add_command(label="Debug Console",
                          command=callbacks['debug_console'],
                          accelerator="Ctrl+D")
    view_menu.add_separator()
    view_menu.add_command(label="Fullscreen",
                          command=callbacks['toggle_fullscreen'],
                          accelerator="F11")
    menubar.add_cascade(label="View", menu=view_menu)

    # Help
    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(label="About SPAM", command=callbacks['help'])
    menubar.add_cascade(label="Help", menu=help_menu)

    # Keyboard shortcuts
    root.bind('<Control-d>', lambda e: callbacks['debug_console']())
    root.bind('<F11>', lambda e: callbacks['toggle_fullscreen']())
    root.bind('<Escape>', lambda e: callbacks.get('exit_fullscreen', lambda: None)())

    root.config(menu=menubar)
