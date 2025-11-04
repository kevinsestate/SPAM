import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np


class SPAMGui(tk.Tk):
    """Main application window for the SPAM GUI mockup."""

    def __init__(self) -> None:
        super().__init__()
        self.title("SPAM - Scanner for Polarized Anisotropic Materials")
        # Set a reasonable window size; users can resize if needed
        self.geometry("1920x1080")
        # Use a light theme background
        self.configure(bg="#F5F5F5")

        # Build top‑level components
        self._create_menu()
        self._create_sidebar()
        self._create_info_panel()
        self._create_center_panel()
        self._create_status_bar()

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------
    def _create_menu(self) -> None:
        """Create the top menu bar with File, Settings and Help menus."""
        menubar = tk.Menu(self)
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Export Data", command=self._on_export)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)
        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Adjust Parameters",
                                  command=self._on_settings)
        settings_menu.add_command(label="Connection Setup",
                                  command=self._on_settings)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About SPAM", command=self._on_help)
        help_menu.add_command(label="User Guide", command=self._on_help)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    def _create_sidebar(self) -> None:
        """Create the left sidebar with large action buttons."""
        sidebar_frame = tk.Frame(self, bg="#F5F5FA", width=250)
        sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        sidebar_frame.pack_propagate(False)

        header = tk.Label(sidebar_frame, text="Controls", bg="#F5F5FA",
                          fg="black", font=("Arial", 14, "bold"))
        header.pack(padx=20, pady=(20, 10), anchor="w")

        # Define a common style for buttons
        button_style = {
            "font": ("Arial", 12),
            "bg": "#E0E0F0",
            "fg": "black",
            "relief": tk.FLAT,
            "activebackground": "#D0D0E0",
            "activeforeground": "black",
            "width": 20,
            "height": 2
        }

        # Create action buttons
        actions = [
            ("Calibrate", self._on_calibrate),
            ("Start Measurement", self._on_start_measurement),
            ("View Results", self._on_view_results),
            ("Export Data", self._on_export),
        ]
        for label, command in actions:
            btn = tk.Button(sidebar_frame, text=label, command=command,
                            **button_style)
            btn.pack(padx=20, pady=10, fill=tk.X)

        # Spacer to push content to top
        tk.Frame(sidebar_frame, bg="#F5F5FA").pack(expand=True)

        self.sidebar_frame = sidebar_frame

    # ------------------------------------------------------------------
    # Information panel
    # ------------------------------------------------------------------
    def _create_info_panel(self) -> None:
        """Create the right panel showing key measurement information."""
        info_frame = tk.Frame(self, bg="#F5F5FA", width=250)
        info_frame.pack(side=tk.RIGHT, fill=tk.Y)
        info_frame.pack_propagate(False)

        header = tk.Label(info_frame, text="Measurement Info",
                          bg="#F5F5FA", fg="black",
                          font=("Arial", 14, "bold"))
        header.pack(padx=20, pady=(20, 10), anchor="w")

        # Variables for live measurement results
        self.angle_var = tk.StringVar(value="-°")
        self.permittivity_var = tk.StringVar(value="-")
        self.permeability_var = tk.StringVar(value="-")
        self.status_var = tk.StringVar(value="-")

        info_items = [
            ("Current Angle", self.angle_var),
            ("Permittivity (ε)", self.permittivity_var),
            ("Permeability (μ)", self.permeability_var),
            ("Status", self.status_var)
        ]
        for label_text, var in info_items:
            row = tk.Frame(info_frame, bg="#F5F5FA")
            row.pack(padx=20, pady=5, anchor="w")
            lbl = tk.Label(row, text=f"{label_text}:", bg="#F5F5FA",
                           fg="black", font=("Arial", 12))
            lbl.pack(side=tk.LEFT)
            val = tk.Label(row, textvariable=var, bg="#F5F5FA",
                           fg="black", font=("Arial", 12, "bold"))
            val.pack(side=tk.LEFT, padx=(10, 0))

        # Spacer to push content to top
        tk.Frame(info_frame, bg="#F5F5FA").pack(expand=True)

        self.info_frame = info_frame

    # ------------------------------------------------------------------
    # Center panel with graphs
    # ------------------------------------------------------------------
    def _create_center_panel(self) -> None:
        """Create the central area containing two Matplotlib graphs."""
        center_frame = tk.Frame(self, bg="#FFFFFF")
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Generate simple placeholder flat-line data
        angles = np.linspace(0, 180, 100)
        permittivity = np.full_like(angles, 2.0)
        permeability = np.full_like(angles, 1.5)


        # Permittivity figure
        fig1 = Figure(figsize=(5, 2.5), dpi=100)
        ax1 = fig1.add_subplot(111)
        ax1.plot(angles, permittivity)
        ax1.set_title("Permittivity (ε) vs Angle")
        ax1.set_xlabel("Angle (degrees)")
        ax1.set_ylabel("Permittivity (ε)")
        fig1.tight_layout()
        canvas1 = FigureCanvasTkAgg(fig1, master=center_frame)
        canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True, pady=(20, 10))
        canvas1.draw()

        # Permeability figure
        fig2 = Figure(figsize=(5, 2.5), dpi=100)
        ax2 = fig2.add_subplot(111)
        ax2.plot(angles, permeability)
        ax2.set_title("Permeability (μ) vs Angle")
        ax2.set_xlabel("Angle (degrees)")
        ax2.set_ylabel("Permeability (μ)")
        fig2.tight_layout()
        canvas2 = FigureCanvasTkAgg(fig2, master=center_frame)
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True, pady=(10, 20))
        canvas2.draw()

        self.center_frame = center_frame

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _create_status_bar(self) -> None:
        """Create the bottom status bar."""
        status_frame = tk.Frame(self, bg="#F5F5F5", height=30)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_frame.pack_propagate(False)
        status_label = tk.Label(status_frame, text="System Ready",
                                bg="#F5F5F5", fg="#008000",
                                font=("Arial", 12))
        status_label.pack(padx=10, pady=5, anchor="w")
        self.status_frame = status_frame

    # ------------------------------------------------------------------
    # Placeholder command callbacks
    # ------------------------------------------------------------------
    def _on_calibrate(self) -> None:
        """Placeholder for calibration action."""
        self.status_var.set("Calibrating…")
        # In a real application, insert calibration logic here

    def _on_start_measurement(self) -> None:
        """Placeholder for starting a measurement."""
        self.status_var.set("Measuring…")
        # Real measurement start logic would go here

    def _on_view_results(self) -> None:
        """Placeholder for viewing results."""
        # In practice, this could open a new window or update the plots
        self.status_var.set("Displaying Results…")

    def _on_export(self) -> None:
        """Placeholder for exporting data."""
        self.status_var.set("Exporting Data…")

    def _on_settings(self) -> None:
        """Placeholder for settings adjustments."""
        self.status_var.set("Opening Settings…")

    def _on_help(self) -> None:
        """Placeholder for help/about dialogues."""
        self.status_var.set("Help Requested…")


def main() -> None:
    """Entrypoint for running the GUI directly."""
    app = SPAMGui()
    app.mainloop()


if __name__ == "__main__":
    main()