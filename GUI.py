import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import json
import csv
from datetime import datetime
import threading
import time

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# Add backend directory to path to import database modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from database import SessionLocal, engine, Base
from models import Measurement, Calibration


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

        # Initialize database
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        
        # Measurement state
        self.is_measuring = False
        self.measurement_thread = None
        self.current_angle = 0.0
        self.current_permittivity = 2.00
        self.current_permeability = 1.50

        # Build top‑level components
        self._create_menu()
        self._create_sidebar()
        self._create_info_panel()
        self._create_center_panel()
        self._create_status_bar()
        
        # Initialize button states (after sidebar is created)
        if hasattr(self, 'start_container') and hasattr(self, 'stop_container'):
            self._update_button_states()
        
        # Start periodic updates
        self._update_display()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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
        title.pack(pady=20)

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
            ("⚙  Calibrate", self._on_calibrate, self.COLORS['secondary']),
            ("▶  Start Measurement", self._on_start_measurement, self.COLORS['success']),
            ("🛑  Stop Measurement", self._on_stop_measurement, self.COLORS['danger']),
            ("🗑️  Clear Measurements", self._on_clear_measurements, self.COLORS['warning']),
            ("📊  View Results", self._on_view_results, self.COLORS['secondary']),
            ("💾  Export Data", self._on_export, self.COLORS['secondary']),
        ]
        
        self.buttons = []
        self.start_button = None
        self.stop_button = None
        self.start_container = None
        self.stop_container = None
        
        for label, command, bg_color in actions:
            # Container for button with padding
            btn_container = tk.Frame(sidebar_frame, bg=self.COLORS['bg_sidebar'])
            btn_container.pack(padx=20, pady=8, fill=tk.X)
            
            # Use custom background color
            btn_style = {**button_style, "bg": bg_color}
            
            btn = tk.Button(btn_container, text=label, command=command,
                           **btn_style)
            btn.pack(fill=tk.BOTH, ipady=12)
            
            # Add hover effects
            hover_color = self.COLORS['hover']
            btn.bind('<Enter>', lambda e, b=btn, h=hover_color: b.config(bg=h))
            btn.bind('<Leave>', lambda e, b=btn, c=bg_color: b.config(bg=c))
            
            # Store references to start/stop buttons and their containers
            if "Start Measurement" in label:
                self.start_button = btn
                self.start_container = btn_container
            elif "Stop Measurement" in label:
                self.stop_button = btn
                self.stop_container = btn_container
                btn_container.pack_forget()  # Hide initially
            
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

        # Initialize with empty data - will be populated from database
        angles = np.array([])
        permittivity = np.array([])
        permeability = np.array([])

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
        
        # Store data arrays for updates
        self.measurement_angles = []
        self.measurement_permittivity = []
        self.measurement_permeability = []

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
    # Database and data management methods
    # ------------------------------------------------------------------
    def _get_measurements(self, limit=1000):
        """Retrieve measurements from database."""
        try:
            measurements = self.db.query(Measurement).order_by(Measurement.timestamp.desc()).limit(limit).all()
            return measurements
        except Exception as e:
            print(f"Error retrieving measurements: {e}")
            return []
    
    def _create_measurement(self, angle, permittivity, permeability):
        """Create a new measurement record."""
        try:
            measurement = Measurement(
                angle=angle,
                permittivity=permittivity,
                permeability=permeability,
                timestamp=datetime.now()
            )
            self.db.add(measurement)
            self.db.commit()
            self.db.refresh(measurement)
            return measurement
        except Exception as e:
            self.db.rollback()
            print(f"Error creating measurement: {e}")
            return None
    
    def _create_calibration(self, parameters=None):
        """Create a calibration record."""
        try:
            calibration = Calibration(
                timestamp=datetime.now(),
                parameters=parameters or {},
                status="completed"
            )
            self.db.add(calibration)
            self.db.commit()
            self.db.refresh(calibration)
            return calibration
        except Exception as e:
            self.db.rollback()
            print(f"Error creating calibration: {e}")
            return None
    
    def _update_graphs(self):
        """Update graphs with latest measurement data."""
        measurements = self._get_measurements()
        
        if not measurements:
            # Show empty graphs
            self.ax1.clear()
            self.ax2.clear()
            self.ax1.set_title("Permittivity (ε) vs Angle", 
                             color=self.COLORS['text_dark'],
                             fontsize=14, fontweight='bold', pad=15)
            self.ax1.set_xlabel("Angle (degrees)", color=self.COLORS['text_dark'], fontsize=11)
            self.ax1.set_ylabel("Permittivity (ε)", color=self.COLORS['text_dark'], fontsize=11)
            self.ax1.grid(True, alpha=0.3, color=self.COLORS['border'], linestyle='--')
            
            self.ax2.set_title("Permeability (μ) vs Angle",
                             color=self.COLORS['text_dark'],
                             fontsize=14, fontweight='bold', pad=15)
            self.ax2.set_xlabel("Angle (degrees)", color=self.COLORS['text_dark'], fontsize=11)
            self.ax2.set_ylabel("Permeability (μ)", color=self.COLORS['text_dark'], fontsize=11)
            self.ax2.grid(True, alpha=0.3, color=self.COLORS['border'], linestyle='--')
        else:
            # Extract data
            angles = [m.angle for m in measurements]
            permittivity = [m.permittivity for m in measurements]
            permeability = [m.permeability for m in measurements]
            
            # Update permittivity graph
            self.ax1.clear()
            self.ax1.plot(angles, permittivity, color=self.COLORS['secondary'], 
                         linewidth=2.5, label='ε')
            self.ax1.set_title("Permittivity (ε) vs Angle", 
                             color=self.COLORS['text_dark'],
                             fontsize=14, fontweight='bold', pad=15)
            self.ax1.set_xlabel("Angle (degrees)", color=self.COLORS['text_dark'], fontsize=11)
            self.ax1.set_ylabel("Permittivity (ε)", color=self.COLORS['text_dark'], fontsize=11)
            self.ax1.grid(True, alpha=0.3, color=self.COLORS['border'], linestyle='--')
            self.ax1.tick_params(colors=self.COLORS['text_dark'])
            self.ax1.spines['top'].set_visible(False)
            self.ax1.spines['right'].set_visible(False)
            self.ax1.spines['left'].set_color(self.COLORS['border'])
            self.ax1.spines['bottom'].set_color(self.COLORS['border'])
            
            # Update permeability graph
            self.ax2.clear()
            self.ax2.plot(angles, permeability, color=self.COLORS['accent'], 
                         linewidth=2.5, label='μ')
            self.ax2.set_title("Permeability (μ) vs Angle",
                             color=self.COLORS['text_dark'],
                             fontsize=14, fontweight='bold', pad=15)
            self.ax2.set_xlabel("Angle (degrees)", color=self.COLORS['text_dark'], fontsize=11)
            self.ax2.set_ylabel("Permeability (μ)", color=self.COLORS['text_dark'], fontsize=11)
            self.ax2.grid(True, alpha=0.3, color=self.COLORS['border'], linestyle='--')
            self.ax2.tick_params(colors=self.COLORS['text_dark'])
            self.ax2.spines['top'].set_visible(False)
            self.ax2.spines['right'].set_visible(False)
            self.ax2.spines['left'].set_color(self.COLORS['border'])
            self.ax2.spines['bottom'].set_color(self.COLORS['border'])
        
        self.fig1.tight_layout(pad=2.0)
        self.fig2.tight_layout(pad=2.0)
        self.canvas1.draw()
        self.canvas2.draw()
    
    def _update_display(self):
        """Periodically update the display with latest data."""
        # Update graphs
        self._update_graphs()
        
        # Update info panel with latest measurement
        measurements = self._get_measurements(limit=1)
        if measurements:
            latest = measurements[0]
            self.angle_var.set(f"{latest.angle:.1f}°")
            self.permittivity_var.set(f"{latest.permittivity:.2f}")
            self.permeability_var.set(f"{latest.permeability:.2f}")
            self.current_angle = latest.angle
            self.current_permittivity = latest.permittivity
            self.current_permeability = latest.permeability
        else:
            self.angle_var.set("0.0°")
            self.permittivity_var.set("2.00")
            self.permeability_var.set("1.50")
        
        # Schedule next update
        self.after(1000, self._update_display)
    
    def _measurement_worker(self):
        """
        Background thread for continuous measurements.
        
        This function calculates permittivity (ε) and permeability (μ) at different angles.
        Currently uses simulated data, but ready for hardware integration.
        
        What it measures:
        - Permittivity (ε): Electrical property - how much electric field is affected by material
        - Permeability (μ): Magnetic property - how much magnetic field is affected by material
        - Angle: Rotation angle of the material (0-90 degrees)
        
        The measurement sweeps through angles from 0° to 90° in steps (default 5°),
        taking measurements at each angle to characterize anisotropic material properties.
        """
        angle_step = 5.0  # degrees per measurement
        max_angle = 90.0
        
        while self.is_measuring and self.current_angle <= max_angle:
            # TODO: Replace this with actual hardware reading
            # Example hardware integration:
            #   permittivity = read_permittivity_from_sensor(self.current_angle)
            #   permeability = read_permeability_from_sensor(self.current_angle)
            
            # Simulate measurement (replace with actual hardware reading)
            # For now, generate realistic-looking data with sinusoidal variation
            # This simulates how anisotropic materials change properties with rotation angle
            permittivity = 2.0 + 0.1 * np.sin(self.current_angle * np.pi / 90) + np.random.normal(0, 0.02)
            permeability = 1.5 + 0.08 * np.cos(self.current_angle * np.pi / 90) + np.random.normal(0, 0.02)
            
            # Save to database
            self._create_measurement(self.current_angle, permittivity, permeability)
            
            # Update current values
            self.current_permittivity = permittivity
            self.current_permeability = permeability
            
            # Increment angle
            self.current_angle += angle_step
            
            # Wait before next measurement (adjust based on hardware response time)
            time.sleep(0.5)
        
        # Measurement complete or stopped
        self.is_measuring = False
        if self.current_angle > max_angle:
            self.after(0, lambda: self._update_status("Measurement completed (0-90°)", "success"))
        else:
            self.after(0, lambda: self._update_status(f"Measurement stopped at {self.current_angle:.1f}°", "info"))
        self.after(0, lambda: self.status_var.set("Ready"))
        self.after(0, self._update_button_states)
    
    # ------------------------------------------------------------------
    # Command callbacks
    # ------------------------------------------------------------------
    def _update_status(self, message: str, status_type: str = "info") -> None:
        """Update the status bar with a message and color."""
        self.status_text_var.set(message)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
        """Perform calibration."""
        self.status_var.set("Calibrating...")
        self._update_status("Calibration in progress...", "warning")
        
        # Create calibration record
        calibration = self._create_calibration()
        
        if calibration:
            self.after(1500, lambda: self._update_status("Calibration completed successfully", "success"))
            self.after(1500, lambda: self.status_var.set("Ready"))
        else:
            self.after(0, lambda: self._update_status("Calibration failed", "error"))
            self.after(0, lambda: self.status_var.set("Error"))

    def _update_button_states(self):
        """Update button visibility based on measurement state."""
        if hasattr(self, 'start_container') and hasattr(self, 'stop_container'):
            if self.is_measuring:
                # Hide start, show stop
                self.start_container.pack_forget()
                self.stop_container.pack(padx=20, pady=8, fill=tk.X)
            else:
                # Show start, hide stop
                self.stop_container.pack_forget()
                self.start_container.pack(padx=20, pady=8, fill=tk.X)
    
    def _on_start_measurement(self) -> None:
        """Start a new measurement session."""
        if self.is_measuring:
            return  # Should not happen, but safety check
        
        # Start measurement
        self.is_measuring = True
        self.current_angle = 0.0
        self.status_var.set("Measuring...")
        self._update_status("Measurement started - sweeping 0° to 90°", "info")
        self._update_button_states()
        
        # Start measurement thread
        self.measurement_thread = threading.Thread(target=self._measurement_worker, daemon=True)
        self.measurement_thread.start()
    
    def _on_stop_measurement(self) -> None:
        """Stop the current measurement session."""
        if not self.is_measuring:
            return
        
        # Stop measurement
        self.is_measuring = False
        self.status_var.set("Stopping...")
        self._update_status("Stopping measurement...", "warning")
        self._update_button_states()
        
        # Wait a moment for thread to finish current measurement
        self.after(500, lambda: self.status_var.set("Ready"))

    def _on_clear_measurements(self) -> None:
        """Clear all measurements from the database."""
        measurements = self._get_measurements()
        count = len(measurements)
        
        if count == 0:
            messagebox.showinfo("No Data", "No measurements to clear.")
            return
        
        # Confirm deletion
        result = messagebox.askyesno(
            "Confirm Clear",
            f"Are you sure you want to delete all {count} measurements?\n\nThis action cannot be undone.",
            icon='warning'
        )
        
        if result:
            try:
                # Delete all measurements
                self.db.query(Measurement).delete()
                self.db.commit()
                
                # Reset current angle
                self.current_angle = 0.0
                
                # Update display
                self._update_graphs()
                self.angle_var.set("0.0°")
                self.permittivity_var.set("2.00")
                self.permeability_var.set("1.50")
                
                self.status_var.set("Ready")
                self._update_status(f"Cleared {count} measurements", "success")
                messagebox.showinfo("Success", f"Successfully cleared {count} measurements.")
            except Exception as e:
                self.db.rollback()
                messagebox.showerror("Error", f"Failed to clear measurements: {str(e)}")
                self._update_status("Failed to clear measurements", "error")
    
    def _on_view_results(self) -> None:
        """View measurement results summary."""
        measurements = self._get_measurements()
        count = len(measurements)
        
        if count == 0:
            messagebox.showinfo("No Results", "No measurements available.\n\nStart a measurement to collect data.")
            return
        
        # Calculate statistics
        angles = [m.angle for m in measurements]
        permittivity_values = [m.permittivity for m in measurements]
        permeability_values = [m.permeability for m in measurements]
        
        angle_min = min(angles) if angles else 0
        angle_max = max(angles) if angles else 0
        permittivity_min = min(permittivity_values) if permittivity_values else 0
        permittivity_max = max(permittivity_values) if permittivity_values else 0
        permittivity_avg = sum(permittivity_values) / len(permittivity_values) if permittivity_values else 0
        permeability_min = min(permeability_values) if permeability_values else 0
        permeability_max = max(permeability_values) if permeability_values else 0
        permeability_avg = sum(permeability_values) / len(permeability_values) if permeability_values else 0
        
        # Get latest measurement
        latest = measurements[0] if measurements else None
        
        # Create summary message
        summary = f"""Measurement Results Summary
{'=' * 40}

Total Measurements: {count}
Angle Range: {angle_min:.1f}° to {angle_max:.1f}°

Permittivity (ε):
  Minimum: {permittivity_min:.4f}
  Maximum: {permittivity_max:.4f}
  Average: {permittivity_avg:.4f}

Permeability (μ):
  Minimum: {permeability_min:.4f}
  Maximum: {permeability_max:.4f}
  Average: {permeability_avg:.4f}
"""
        
        if latest:
            summary += f"""
Latest Measurement:
  Angle: {latest.angle:.1f}°
  Permittivity: {latest.permittivity:.4f}
  Permeability: {latest.permeability:.4f}
  Time: {latest.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        # Show dialog
        messagebox.showinfo("Measurement Results", summary)
        self.status_var.set("Displaying Results")
        self._update_status(f"Viewing results summary ({count} measurements)", "info")

    def _on_export(self) -> None:
        """Export measurement data to file."""
        measurements = self._get_measurements()
        
        if not measurements:
            messagebox.showwarning("No Data", "No measurements to export.")
            return
        
        # Ask user for file location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            if file_path.endswith('.csv'):
                # Export as CSV
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['id', 'angle', 'permittivity', 'permeability', 'timestamp'])
                    for m in measurements:
                        writer.writerow([
                            m.id,
                            m.angle,
                            m.permittivity,
                            m.permeability,
                            m.timestamp.isoformat()
                        ])
            else:
                # Export as JSON
                data = [
                    {
                        "id": m.id,
                        "angle": m.angle,
                        "permittivity": m.permittivity,
                        "permeability": m.permeability,
                        "timestamp": m.timestamp.isoformat()
                    }
                    for m in measurements
                ]
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
            
            self.status_var.set("Exporting...")
            self._update_status(f"Data exported successfully to {os.path.basename(file_path)}", "success")
            self.after(2000, lambda: self.status_var.set("Ready"))
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data: {str(e)}")
            self._update_status("Export failed", "error")

    def _on_settings(self) -> None:
        """Open settings dialog."""
        self.status_var.set("Settings")
        self._update_status("Opening settings...", "info")
        # Settings dialog can be implemented here

    def _on_help(self) -> None:
        """Show help/about dialog."""
        about_text = """SPAM - Scanner for Polarized Anisotropic Materials
        
Version 1.0.0

A local desktop application for scanning and analyzing polarized anisotropic materials.

Features:
- Real-time measurement visualization
- Data storage and management
- Calibration functionality
- Data export (JSON/CSV)

For use on Raspberry Pi and other local systems."""
        messagebox.showinfo("About SPAM", about_text)
        self.status_var.set("Help")
        self._update_status("Help requested", "info")
    
    def _on_close(self):
        """Handle window close event."""
        # Stop any ongoing measurements
        self.is_measuring = False
        
        # Close database connection
        if hasattr(self, 'db'):
            self.db.close()
        
        # Destroy window
        self.destroy()


def main() -> None:
    """Entrypoint for running the GUI directly."""
    app = SPAMGui()
    app.mainloop()


if __name__ == "__main__":
    main()