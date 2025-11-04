import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np


class SPAMGui(tk.Tk):
    """Main application window for the SPAM GUI mockup."""

    # Modern color palette
    COLORS = {
        'primary': '#2C3E50',           # Dark blue-gray
        'secondary': '#3498DB',         # Professional blue
        'accent': '#1ABC9C',            # Teal accent
        'success': '#27AE60',           # Green
        'warning': '#F39C12',           # Orange
        'danger': '#E74C3C',            # Red
        'bg_main': '#ECF0F1',           # Light gray background
        'bg_sidebar': '#34495E',        # Dark sidebar
        'bg_panel': '#FFFFFF',          # White panels
        'text_dark': '#2C3E50',         # Dark text
        'text_light': '#FFFFFF',        # Light text
        'text_muted': '#7F8C8D',        # Muted text
        'border': '#BDC3C7',            # Border color
        'hover': '#5DADE2',             # Hover blue
    }

    def __init__(self) -> None:
        super().__init__()
        self.title("SPAM - Scanner for Polarized Anisotropic Materials")
        # Set a reasonable window size; users can resize if needed
        self.geometry("1920x1080")
        # Use a modern light theme background
        self.configure(bg=self.COLORS['bg_main'])

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
        sidebar_frame = tk.Frame(self, bg=self.COLORS['bg_sidebar'], width=280)
        sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        sidebar_frame.pack_propagate(False)

        # Header section with logo/title
        header_frame = tk.Frame(sidebar_frame, bg=self.COLORS['primary'], height=80)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        header_frame.pack_propagate(False)
        
        title = tk.Label(header_frame, text="SPAM", 
                        bg=self.COLORS['primary'],
                        fg=self.COLORS['text_light'], 
                        font=("Segoe UI", 24, "bold"))
        title.pack(pady=(15, 0))
        
        subtitle = tk.Label(header_frame, text="Control Panel", 
                           bg=self.COLORS['primary'],
                           fg=self.COLORS['accent'], 
                           font=("Segoe UI", 10))
        subtitle.pack()

        # Controls label
        controls_label = tk.Label(sidebar_frame, text="CONTROLS", 
                                 bg=self.COLORS['bg_sidebar'],
                                 fg=self.COLORS['text_muted'], 
                                 font=("Segoe UI", 10, "bold"))
        controls_label.pack(padx=20, pady=(10, 15), anchor="w")

        # Define a common style for buttons
        button_style = {
            "font": ("Segoe UI", 11, "bold"),
            "bg": self.COLORS['secondary'],
            "fg": self.COLORS['text_light'],
            "relief": tk.FLAT,
            "activebackground": self.COLORS['hover'],
            "activeforeground": self.COLORS['text_light'],
            "cursor": "hand2",
            "bd": 0,
            "highlightthickness": 0,
        }

        # Create action buttons with icons/symbols
        actions = [
            ("⚙  Calibrate", self._on_calibrate),
            ("▶  Start Measurement", self._on_start_measurement),
            ("📊  View Results", self._on_view_results),
            ("💾  Export Data", self._on_export),
        ]
        
        self.buttons = []
        for label, command in actions:
            # Container for button with padding
            btn_container = tk.Frame(sidebar_frame, bg=self.COLORS['bg_sidebar'])
            btn_container.pack(padx=20, pady=8, fill=tk.X)
            
            btn = tk.Button(btn_container, text=label, command=command,
                           **button_style)
            btn.pack(fill=tk.BOTH, ipady=12)
            
            # Add hover effects
            btn.bind('<Enter>', lambda e, b=btn: b.config(bg=self.COLORS['hover']))
            btn.bind('<Leave>', lambda e, b=btn: b.config(bg=self.COLORS['secondary']))
            
            self.buttons.append(btn)

        # Spacer to push content to top
        tk.Frame(sidebar_frame, bg=self.COLORS['bg_sidebar']).pack(expand=True)
        
        # Version info at bottom
        version_label = tk.Label(sidebar_frame, text="Version 1.0.0", 
                                bg=self.COLORS['bg_sidebar'],
                                fg=self.COLORS['text_muted'], 
                                font=("Segoe UI", 8))
        version_label.pack(pady=(0, 10))

        self.sidebar_frame = sidebar_frame

    # ------------------------------------------------------------------
    # Information panel
    # ------------------------------------------------------------------
    def _create_info_panel(self) -> None:
        """Create the right panel showing key measurement information."""
        info_frame = tk.Frame(self, bg=self.COLORS['bg_main'], width=320)
        info_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=15, pady=15)
        info_frame.pack_propagate(False)

        header = tk.Label(info_frame, text="Measurement Data",
                          bg=self.COLORS['bg_main'], 
                          fg=self.COLORS['text_dark'],
                          font=("Segoe UI", 16, "bold"))
        header.pack(padx=0, pady=(10, 20), anchor="w")

        # Variables for live measurement results
        self.angle_var = tk.StringVar(value="0.0°")
        self.permittivity_var = tk.StringVar(value="2.00")
        self.permeability_var = tk.StringVar(value="1.50")
        self.status_var = tk.StringVar(value="Ready")

        info_items = [
            ("Current Angle", self.angle_var, "🔄"),
            ("Permittivity (ε)", self.permittivity_var, "⚡"),
            ("Permeability (μ)", self.permeability_var, "🧲"),
            ("Status", self.status_var, "●")
        ]
        
        for label_text, var, icon in info_items:
            # Create card-style container for each metric
            card = tk.Frame(info_frame, bg=self.COLORS['bg_panel'], 
                           relief=tk.FLAT, bd=0)
            card.pack(fill=tk.X, pady=8)
            
            # Add subtle border effect
            border_frame = tk.Frame(card, bg=self.COLORS['secondary'], height=3)
            border_frame.pack(fill=tk.X)
            
            # Content container
            content = tk.Frame(card, bg=self.COLORS['bg_panel'])
            content.pack(fill=tk.BOTH, padx=15, pady=12)
            
            # Icon and label
            header_row = tk.Frame(content, bg=self.COLORS['bg_panel'])
            header_row.pack(fill=tk.X, pady=(0, 5))
            
            icon_lbl = tk.Label(header_row, text=icon, 
                               bg=self.COLORS['bg_panel'],
                               fg=self.COLORS['secondary'],
                               font=("Segoe UI", 14))
            icon_lbl.pack(side=tk.LEFT, padx=(0, 8))
            
            lbl = tk.Label(header_row, text=label_text, 
                          bg=self.COLORS['bg_panel'],
                          fg=self.COLORS['text_muted'], 
                          font=("Segoe UI", 10))
            lbl.pack(side=tk.LEFT)
            
            # Value
            val = tk.Label(content, textvariable=var, 
                          bg=self.COLORS['bg_panel'],
                          fg=self.COLORS['text_dark'], 
                          font=("Segoe UI", 18, "bold"))
            val.pack(anchor="w")

        # Spacer to push content to top
        tk.Frame(info_frame, bg=self.COLORS['bg_main']).pack(expand=True)
        
        # System info card at bottom
        system_card = tk.Frame(info_frame, bg=self.COLORS['bg_panel'], 
                              relief=tk.FLAT, bd=0)
        system_card.pack(fill=tk.X, pady=(10, 0))
        
        system_header = tk.Frame(system_card, bg=self.COLORS['accent'], height=3)
        system_header.pack(fill=tk.X)
        
        system_content = tk.Frame(system_card, bg=self.COLORS['bg_panel'])
        system_content.pack(fill=tk.BOTH, padx=15, pady=12)
        
        sys_title = tk.Label(system_content, text="System Status",
                            bg=self.COLORS['bg_panel'],
                            fg=self.COLORS['text_muted'],
                            font=("Segoe UI", 10))
        sys_title.pack(anchor="w")
        
        self.system_status_var = tk.StringVar(value="All Systems Operational")
        sys_val = tk.Label(system_content, textvariable=self.system_status_var,
                          bg=self.COLORS['bg_panel'],
                          fg=self.COLORS['success'],
                          font=("Segoe UI", 11, "bold"))
        sys_val.pack(anchor="w", pady=(3, 0))

        self.info_frame = info_frame

    # ------------------------------------------------------------------
    # Center panel with graphs
    # ------------------------------------------------------------------
    def _create_center_panel(self) -> None:
        """Create the central area containing two Matplotlib graphs."""
        center_frame = tk.Frame(self, bg=self.COLORS['bg_main'])
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 0), pady=15)

        # Title for the graphs section
        title_frame = tk.Frame(center_frame, bg=self.COLORS['bg_main'])
        title_frame.pack(fill=tk.X, pady=(5, 15))
        
        title = tk.Label(title_frame, text="Real-Time Measurements",
                        bg=self.COLORS['bg_main'],
                        fg=self.COLORS['text_dark'],
                        font=("Segoe UI", 16, "bold"))
        title.pack(side=tk.LEFT)

        # Generate simple placeholder data with slight variation for visual interest
        angles = np.linspace(0, 180, 100)
        permittivity = 2.0 + 0.1 * np.sin(angles * np.pi / 90)
        permeability = 1.5 + 0.08 * np.cos(angles * np.pi / 90)

        # Graph styling configuration
        graph_style = {
            'facecolor': self.COLORS['bg_panel'],
            'titlecolor': self.COLORS['text_dark'],
            'titlesize': 14,
            'titleweight': 'bold',
            'labelcolor': self.COLORS['text_dark'],
            'labelsize': 11,
            'linecolor': self.COLORS['secondary'],
            'linewidth': 2.5,
            'gridcolor': self.COLORS['border'],
            'gridalpha': 0.3,
        }

        # Container for permittivity graph
        graph1_container = tk.Frame(center_frame, bg=self.COLORS['bg_panel'], 
                                   relief=tk.FLAT, bd=0)
        graph1_container.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Permittivity figure
        fig1 = Figure(figsize=(5, 2.5), dpi=100, facecolor=graph_style['facecolor'])
        ax1 = fig1.add_subplot(111, facecolor=graph_style['facecolor'])
        ax1.plot(angles, permittivity, color=graph_style['linecolor'], 
                linewidth=graph_style['linewidth'], label='ε')
        ax1.set_title("Permittivity (ε) vs Angle", 
                     color=graph_style['titlecolor'],
                     fontsize=graph_style['titlesize'],
                     fontweight=graph_style['titleweight'],
                     pad=15)
        ax1.set_xlabel("Angle (degrees)", color=graph_style['labelcolor'],
                      fontsize=graph_style['labelsize'])
        ax1.set_ylabel("Permittivity (ε)", color=graph_style['labelcolor'],
                      fontsize=graph_style['labelsize'])
        ax1.grid(True, alpha=graph_style['gridalpha'], 
                color=graph_style['gridcolor'], linestyle='--')
        ax1.tick_params(colors=graph_style['labelcolor'])
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.spines['left'].set_color(graph_style['gridcolor'])
        ax1.spines['bottom'].set_color(graph_style['gridcolor'])
        fig1.tight_layout(pad=2.0)
        
        canvas1 = FigureCanvasTkAgg(fig1, master=graph1_container)
        canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        canvas1.draw()

        # Container for permeability graph
        graph2_container = tk.Frame(center_frame, bg=self.COLORS['bg_panel'], 
                                   relief=tk.FLAT, bd=0)
        graph2_container.pack(fill=tk.BOTH, expand=True)

        # Permeability figure
        fig2 = Figure(figsize=(5, 2.5), dpi=100, facecolor=graph_style['facecolor'])
        ax2 = fig2.add_subplot(111, facecolor=graph_style['facecolor'])
        ax2.plot(angles, permeability, color=self.COLORS['accent'], 
                linewidth=graph_style['linewidth'], label='μ')
        ax2.set_title("Permeability (μ) vs Angle", 
                     color=graph_style['titlecolor'],
                     fontsize=graph_style['titlesize'],
                     fontweight=graph_style['titleweight'],
                     pad=15)
        ax2.set_xlabel("Angle (degrees)", color=graph_style['labelcolor'],
                      fontsize=graph_style['labelsize'])
        ax2.set_ylabel("Permeability (μ)", color=graph_style['labelcolor'],
                      fontsize=graph_style['labelsize'])
        ax2.grid(True, alpha=graph_style['gridalpha'], 
                color=graph_style['gridcolor'], linestyle='--')
        ax2.tick_params(colors=graph_style['labelcolor'])
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.spines['left'].set_color(graph_style['gridcolor'])
        ax2.spines['bottom'].set_color(graph_style['gridcolor'])
        fig2.tight_layout(pad=2.0)
        
        canvas2 = FigureCanvasTkAgg(fig2, master=graph2_container)
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        canvas2.draw()

        self.center_frame = center_frame
        self.fig1 = fig1
        self.ax1 = ax1
        self.canvas1 = canvas1
        self.fig2 = fig2
        self.ax2 = ax2
        self.canvas2 = canvas2

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _create_status_bar(self) -> None:
        """Create the bottom status bar."""
        status_frame = tk.Frame(self, bg=self.COLORS['primary'], height=35)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_frame.pack_propagate(False)
        
        # Left side - status indicator
        left_frame = tk.Frame(status_frame, bg=self.COLORS['primary'])
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        status_indicator = tk.Label(left_frame, text="●", 
                                   bg=self.COLORS['primary'],
                                   fg=self.COLORS['success'],
                                   font=("Segoe UI", 14))
        status_indicator.pack(side=tk.LEFT, padx=(15, 5))
        
        self.status_text_var = tk.StringVar(value="System Ready")
        status_label = tk.Label(left_frame, textvariable=self.status_text_var,
                               bg=self.COLORS['primary'], 
                               fg=self.COLORS['text_light'],
                               font=("Segoe UI", 10))
        status_label.pack(side=tk.LEFT, pady=5)
        
        # Right side - timestamp
        right_frame = tk.Frame(status_frame, bg=self.COLORS['primary'])
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        time_label = tk.Label(right_frame, text=f"Last Update: {timestamp}",
                             bg=self.COLORS['primary'],
                             fg=self.COLORS['text_muted'],
                             font=("Segoe UI", 9))
        time_label.pack(side=tk.RIGHT, padx=15, pady=5)
        
        self.status_frame = status_frame
        self.status_indicator = status_indicator
        self.time_label = time_label

    # ------------------------------------------------------------------
    # Placeholder command callbacks
    # ------------------------------------------------------------------
    def _update_status(self, message: str, status_type: str = "info") -> None:
        """Update the status bar with a message and color."""
        self.status_text_var.set(message)
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.config(text=f"Last Update: {timestamp}")
        
        # Update status indicator color based on type
        color_map = {
            "success": self.COLORS['success'],
            "warning": self.COLORS['warning'],
            "error": self.COLORS['danger'],
            "info": self.COLORS['secondary'],
        }
        self.status_indicator.config(fg=color_map.get(status_type, self.COLORS['success']))

    def _on_calibrate(self) -> None:
        """Placeholder for calibration action."""
        self.status_var.set("Calibrating...")
        self._update_status("Calibration in progress...", "warning")
        # Simulate calibration completion
        self.after(1500, lambda: self._update_status("Calibration completed successfully", "success"))
        # In a real application, insert calibration logic here

    def _on_start_measurement(self) -> None:
        """Placeholder for starting a measurement."""
        self.status_var.set("Measuring...")
        self._update_status("Measurement started", "info")
        # Real measurement start logic would go here

    def _on_view_results(self) -> None:
        """Placeholder for viewing results."""
        # In practice, this could open a new window or update the plots
        self.status_var.set("Displaying Results")
        self._update_status("Results displayed", "success")

    def _on_export(self) -> None:
        """Placeholder for exporting data."""
        self.status_var.set("Exporting...")
        self._update_status("Exporting data...", "warning")
        self.after(1000, lambda: self._update_status("Data exported successfully", "success"))

    def _on_settings(self) -> None:
        """Placeholder for settings adjustments."""
        self.status_var.set("Settings")
        self._update_status("Opening settings...", "info")

    def _on_help(self) -> None:
        """Placeholder for help/about dialogues."""
        self.status_var.set("Help")
        self._update_status("Help requested", "info")


def main() -> None:
    """Entrypoint for running the GUI directly."""
    app = SPAMGui()
    app.mainloop()


if __name__ == "__main__":
    main()