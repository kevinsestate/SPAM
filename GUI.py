<<<<<<< Updated upstream
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import json
import csv
from datetime import datetime
import threading
import time
import platform

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# Enable DPI awareness on Windows for better resolution
if platform.system() == 'Windows':
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)  # Enable DPI awareness
    except:
        pass  # If DPI awareness fails, continue anyway

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
        
        # Get screen dimensions for better initial sizing
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Start in maximized state for better experience (Windows) or use geometry for others
        if platform.system() == 'Windows':
            self.state('zoomed')  # Windows maximized
        else:
            # For Linux/Mac, use a large window size
            self.geometry(f"{min(screen_width, 1920)}x{min(screen_height, 1080)}")
            self.update_idletasks()
            # Center the window
            x = (screen_width - self.winfo_width()) // 2
            y = (screen_height - self.winfo_height()) // 2
            self.geometry(f"+{x}+{y}")
        
        # Use a modern light theme background
        self.configure(bg=self.COLORS['bg_main'])
        
        # Track fullscreen state
        self.is_fullscreen = False

        # Initialize debug logging first (before any log calls)
        self.debug_log = []
        self.debug_window = None
        
        # Measurement state
        self.is_measuring = False
        self.measurement_thread = None
        self.current_angle = 0.0
        self.current_permittivity = 2.00
        self.current_permeability = 1.50

        # Initialize database
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self._log_debug("Application initialized", "INFO")
        self._log_debug(f"Database connection established: {engine.url}", "INFO")

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
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Debug Console", command=self._on_debug_console,
                             accelerator="Ctrl+D")
        view_menu.add_separator()
        view_menu.add_command(label="Fullscreen", command=self._toggle_fullscreen,
                             accelerator="F11")
        menubar.add_cascade(label="View", menu=view_menu)
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About SPAM", command=self._on_help)
        help_menu.add_command(label="User Guide", command=self._on_help)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        # Bind keyboard shortcuts
        self.bind('<Control-d>', lambda e: self._on_debug_console())
        self.bind('<F11>', lambda e: self._toggle_fullscreen())
        self.bind('<Escape>', lambda e: self._exit_fullscreen() if self.is_fullscreen else None)

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

        # Create action buttons (ordered: Calibrate, Start, Stop, Clear, View, Export, Debug)
        actions = [
            ("Calibrate", self._on_calibrate, self.COLORS['secondary']),
            ("Start Measurement", self._on_start_measurement, self.COLORS['success']),
            ("Stop Measurement", self._on_stop_measurement, self.COLORS['danger']),
            ("Clear Measurements", self._on_clear_measurements, self.COLORS['warning']),
            ("View Results", self._on_view_results, self.COLORS['secondary']),
            ("Export Data", self._on_export, self.COLORS['secondary']),
            ("Debug Console", self._on_debug_console, self.COLORS['text_muted']),
        ]
        
        self.buttons = []
        self.start_button = None
        self.stop_button = None
        self.start_container = None
        self.stop_container = None
        self.clear_container = None  # Reference for positioning
        
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
            
            # Store references to start/stop/clear buttons and their containers
            if "Start Measurement" in label:
                self.start_button = btn
                self.start_container = btn_container
            elif "Stop Measurement" in label:
                self.stop_button = btn
                self.stop_container = btn_container
                btn_container.pack_forget()  # Hide initially
            elif "Clear Measurements" in label:
                self.clear_container = btn_container
            
            self.buttons.append(btn)

        # Spacer to push content to top
        tk.Frame(sidebar_frame, bg=self.COLORS['bg_sidebar']).pack(expand=True)
        
        # Version info at bottom
        version_label = tk.Label(sidebar_frame, text="Version 1.01", 
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
            ("Current Angle", self.angle_var),
            ("Permittivity (ε)", self.permittivity_var),
            ("Permeability (μ)", self.permeability_var),
            ("Status", self.status_var)
        ]
        
        for label_text, var in info_items:
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
            
            # Label
            header_row = tk.Frame(content, bg=self.COLORS['bg_panel'])
            header_row.pack(fill=tk.X, pady=(0, 5))
            
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
        """Create the central area containing two Matplotlib graphs with scrolling."""
        center_frame = tk.Frame(self, bg=self.COLORS['bg_main'])
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 0), pady=15)

        # Title for the graphs section (fixed at top)
        title_frame = tk.Frame(center_frame, bg=self.COLORS['bg_main'])
        title_frame.pack(fill=tk.X, pady=(5, 10))
        
        title = tk.Label(title_frame, text="Real-Time Measurements",
                        bg=self.COLORS['bg_main'],
                        fg=self.COLORS['text_dark'],
                        font=("Segoe UI", 16, "bold"))
        title.pack(side=tk.LEFT)
        
        # Create scrollable frame for graphs
        # Create canvas and scrollbar
        canvas_container = tk.Frame(center_frame, bg=self.COLORS['bg_main'])
        canvas_container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(canvas_container, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        canvas = tk.Canvas(canvas_container, 
                          bg=self.COLORS['bg_main'],
                          yscrollcommand=scrollbar.set,
                          highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=canvas.yview)
        
        # Create scrollable frame inside canvas
        scrollable_frame = tk.Frame(canvas, bg=self.COLORS['bg_main'])
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Function to update scroll region and canvas width
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Make canvas width match scrollable_frame width
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
        
        def on_canvas_configure(event):
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
        
        scrollable_frame.bind("<Configure>", configure_scroll_region)
        canvas.bind("<Configure>", on_canvas_configure)
        
        # Enable mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # For Linux, use Button-4 and Button-5
        def on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
        
        canvas.bind_all("<Button-4>", on_mousewheel_linux)
        canvas.bind_all("<Button-5>", on_mousewheel_linux)

        # Initialize with empty data - will be populated from database
        angles = np.array([])
        permittivity = np.array([])
        permeability = np.array([])

        # Graph styling configuration - improved for better quality
        graph_style = {
            'facecolor': self.COLORS['bg_panel'],
            'titlecolor': self.COLORS['text_dark'],
            'titlesize': 14,  # Balanced size
            'titleweight': 'bold',
            'labelcolor': self.COLORS['text_dark'],
            'labelsize': 11,  # Balanced size
            'linecolor': self.COLORS['secondary'],
            'linewidth': 2.5,  # Good visibility without being too thick
            'gridcolor': self.COLORS['border'],
            'gridalpha': 0.3,
            'dpi': 100,  # Standard DPI for proper sizing
        }

        # Container for permittivity graph (inside scrollable frame)
        graph1_container = tk.Frame(scrollable_frame, bg=self.COLORS['bg_panel'], 
                                   relief=tk.FLAT, bd=0, height=400)
        graph1_container.pack(fill=tk.X, pady=(0, 15), padx=5)
        graph1_container.pack_propagate(False)  # Prevent shrinking
        
        # Permittivity figure - properly sized to fit container
        fig1 = Figure(figsize=(6, 3.5), dpi=graph_style['dpi'], facecolor=graph_style['facecolor'])
        ax1 = fig1.add_subplot(111, facecolor=graph_style['facecolor'])
        # Set axis limits before plotting (even if empty)
        ax1.set_xlim(0, 90)
        ax1.set_ylim(1.5, 2.5)  # Reasonable range for permittivity
        if len(angles) > 0:
            ax1.plot(angles, permittivity, color=graph_style['linecolor'], 
                    linewidth=graph_style['linewidth'], label='ε')
        ax1.set_title("Permittivity (ε) vs Angle", 
                     color=graph_style['titlecolor'],
                     fontsize=graph_style['titlesize'],
                     fontweight=graph_style['titleweight'],
                     pad=15)
        ax1.set_xlabel("Angle (degrees)", color=graph_style['labelcolor'],
                      fontsize=graph_style['labelsize'], fontweight='medium')
        ax1.set_ylabel("Permittivity (ε)", color=graph_style['labelcolor'],
                      fontsize=graph_style['labelsize'], fontweight='medium')
        ax1.grid(True, alpha=graph_style['gridalpha'], 
                color=graph_style['gridcolor'], linestyle='--')
        ax1.tick_params(colors=graph_style['labelcolor'], labelsize=9)
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.spines['left'].set_color(graph_style['gridcolor'])
        ax1.spines['bottom'].set_color(graph_style['gridcolor'])
        fig1.tight_layout(pad=2.0)
        
        canvas1 = FigureCanvasTkAgg(fig1, master=graph1_container)
        canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        canvas1.draw()

        # Container for permeability graph (inside scrollable frame)
        graph2_container = tk.Frame(scrollable_frame, bg=self.COLORS['bg_panel'], 
                                   relief=tk.FLAT, bd=0, height=400)
        graph2_container.pack(fill=tk.X, pady=(0, 15), padx=5)
        graph2_container.pack_propagate(False)  # Prevent shrinking

        # Permeability figure - properly sized to fit container
        fig2 = Figure(figsize=(6, 3.5), dpi=graph_style['dpi'], facecolor=graph_style['facecolor'])
        ax2 = fig2.add_subplot(111, facecolor=graph_style['facecolor'])
        # Set axis limits before plotting (even if empty)
        ax2.set_xlim(0, 90)
        ax2.set_ylim(1.0, 2.0)  # Reasonable range for permeability
        if len(angles) > 0:
            ax2.plot(angles, permeability, color=self.COLORS['accent'], 
                    linewidth=graph_style['linewidth'], label='μ')
        ax2.set_title("Permeability (μ) vs Angle", 
                     color=graph_style['titlecolor'],
                     fontsize=graph_style['titlesize'],
                     fontweight=graph_style['titleweight'],
                     pad=15)
        ax2.set_xlabel("Angle (degrees)", color=graph_style['labelcolor'],
                      fontsize=graph_style['labelsize'], fontweight='medium')
        ax2.set_ylabel("Permeability (μ)", color=graph_style['labelcolor'],
                      fontsize=graph_style['labelsize'], fontweight='medium')
        ax2.grid(True, alpha=graph_style['gridalpha'], 
                color=graph_style['gridcolor'], linestyle='--')
        ax2.tick_params(colors=graph_style['labelcolor'], labelsize=9)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.spines['left'].set_color(graph_style['gridcolor'])
        ax2.spines['bottom'].set_color(graph_style['gridcolor'])
        fig2.tight_layout(pad=2.0)
        
        canvas2 = FigureCanvasTkAgg(fig2, master=graph2_container)
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        canvas2.draw()

        self.center_frame = center_frame
        self.scrollable_frame = scrollable_frame
        self.graphs_canvas = canvas
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
        
        # Bind resize event to update graphs for better responsiveness
        def on_resize(event):
            if hasattr(self, 'fig1') and hasattr(self, 'fig2'):
                try:
                    self.fig1.tight_layout(pad=2.0)
                    self.fig2.tight_layout(pad=2.0)
                    self.canvas1.draw()
                    self.canvas2.draw()
                    # Update scroll region after resize
                    if hasattr(self, 'graphs_canvas'):
                        self.graphs_canvas.configure(scrollregion=self.graphs_canvas.bbox("all"))
                except:
                    pass  # Ignore errors during resize
        
        self.bind('<Configure>', on_resize)

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
        
        status_indicator = tk.Label(left_frame, text="*", 
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
            self._log_debug(f"Measurement recorded: Angle={angle:.2f}°, ε={permittivity:.4f}, μ={permeability:.4f}", "DEBUG")
            return measurement
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error creating measurement: {e}"
            print(error_msg)
            self._log_debug(error_msg, "ERROR")
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
            # Show empty graphs with proper axis limits
            self.ax1.clear()
            self.ax2.clear()
            self.ax1.set_xlim(0, 90)
            self.ax1.set_ylim(1.5, 2.5)
            self.ax1.set_title("Permittivity (ε) vs Angle", 
                             color=self.COLORS['text_dark'],
                             fontsize=14, fontweight='bold', pad=15)
            self.ax1.set_xlabel("Angle (degrees)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax1.set_ylabel("Permittivity (ε)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax1.grid(True, alpha=0.3, color=self.COLORS['border'], linestyle='--')
            self.ax1.tick_params(colors=self.COLORS['text_dark'], labelsize=9)
            self.ax1.spines['top'].set_visible(False)
            self.ax1.spines['right'].set_visible(False)
            self.ax1.spines['left'].set_color(self.COLORS['border'])
            self.ax1.spines['bottom'].set_color(self.COLORS['border'])
            
            self.ax2.set_xlim(0, 90)
            self.ax2.set_ylim(1.0, 2.0)
            self.ax2.set_title("Permeability (μ) vs Angle",
                             color=self.COLORS['text_dark'],
                             fontsize=14, fontweight='bold', pad=15)
            self.ax2.set_xlabel("Angle (degrees)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax2.set_ylabel("Permeability (μ)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax2.grid(True, alpha=0.3, color=self.COLORS['border'], linestyle='--')
            self.ax2.tick_params(colors=self.COLORS['text_dark'], labelsize=9)
            self.ax2.spines['top'].set_visible(False)
            self.ax2.spines['right'].set_visible(False)
            self.ax2.spines['left'].set_color(self.COLORS['border'])
            self.ax2.spines['bottom'].set_color(self.COLORS['border'])
        else:
            # Extract data
            angles = [m.angle for m in measurements]
            permittivity = [m.permittivity for m in measurements]
            permeability = [m.permeability for m in measurements]
            
            # Update permittivity graph
            self.ax1.clear()
            self.ax1.plot(angles, permittivity, color=self.COLORS['secondary'], 
                         linewidth=2.5, label='ε')
            # Set axis limits based on data with some padding
            if angles:
                self.ax1.set_xlim(max(0, min(angles) - 5), min(90, max(angles) + 5))
                self.ax1.set_ylim(max(1.0, min(permittivity) - 0.2), max(permittivity) + 0.2)
            else:
                self.ax1.set_xlim(0, 90)
                self.ax1.set_ylim(1.5, 2.5)
            self.ax1.set_title("Permittivity (ε) vs Angle", 
                             color=self.COLORS['text_dark'],
                             fontsize=14, fontweight='bold', pad=15)
            self.ax1.set_xlabel("Angle (degrees)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax1.set_ylabel("Permittivity (ε)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax1.grid(True, alpha=0.3, color=self.COLORS['border'], linestyle='--')
            self.ax1.tick_params(colors=self.COLORS['text_dark'], labelsize=9)
            self.ax1.spines['top'].set_visible(False)
            self.ax1.spines['right'].set_visible(False)
            self.ax1.spines['left'].set_color(self.COLORS['border'])
            self.ax1.spines['bottom'].set_color(self.COLORS['border'])
            
            # Update permeability graph
            self.ax2.clear()
            self.ax2.plot(angles, permeability, color=self.COLORS['accent'], 
                         linewidth=2.5, label='μ')
            # Set axis limits based on data with some padding
            if angles:
                self.ax2.set_xlim(max(0, min(angles) - 5), min(90, max(angles) + 5))
                self.ax2.set_ylim(max(0.5, min(permeability) - 0.2), max(permeability) + 0.2)
            else:
                self.ax2.set_xlim(0, 90)
                self.ax2.set_ylim(1.0, 2.0)
            self.ax2.set_title("Permeability (μ) vs Angle",
                             color=self.COLORS['text_dark'],
                             fontsize=14, fontweight='bold', pad=15)
            self.ax2.set_xlabel("Angle (degrees)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax2.set_ylabel("Permeability (μ)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax2.grid(True, alpha=0.3, color=self.COLORS['border'], linestyle='--')
            self.ax2.tick_params(colors=self.COLORS['text_dark'], labelsize=9)
            self.ax2.spines['top'].set_visible(False)
            self.ax2.spines['right'].set_visible(False)
            self.ax2.spines['left'].set_color(self.COLORS['border'])
            self.ax2.spines['bottom'].set_color(self.COLORS['border'])
        
        self.fig1.tight_layout(pad=2.0)
        self.fig2.tight_layout(pad=2.0)
        self.canvas1.draw()
        self.canvas2.draw()
        # Update scroll region after drawing
        if hasattr(self, 'graphs_canvas'):
            self.graphs_canvas.configure(scrollregion=self.graphs_canvas.bbox("all"))
    
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
            measurement = self._create_measurement(self.current_angle, permittivity, permeability)
            
            # Update current values
            self.current_permittivity = permittivity
            self.current_permeability = permeability
            
            # Increment angle
            self.current_angle += angle_step
            
            # Log progress every 10 degrees
            if int(self.current_angle) % 10 == 0:
                self.after(0, lambda: self._log_debug(f"Measurement progress: {self.current_angle:.1f}° / 90°", "INFO"))
            
            # Wait before next measurement (adjust based on hardware response time)
            time.sleep(0.5)
        
        # Measurement complete or stopped
        self.is_measuring = False
        if self.current_angle > max_angle:
            self.after(0, lambda: self._log_debug("Measurement completed successfully (0-90°)", "SUCCESS"))
            self.after(0, lambda: self._update_status("Measurement completed (0-90°)", "success"))
        else:
            self.after(0, lambda: self._log_debug(f"Measurement stopped at {self.current_angle:.1f}°", "INFO"))
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
        self._log_debug("Calibration started", "INFO")
        
        # Create calibration record
        calibration = self._create_calibration()
        
        if calibration:
            self._log_debug(f"Calibration completed successfully (ID: {calibration.id})", "SUCCESS")
            self.after(1500, lambda: self._update_status("Calibration completed successfully", "success"))
            self.after(1500, lambda: self.status_var.set("Ready"))
        else:
            self._log_debug("Calibration failed", "ERROR")
            self.after(0, lambda: self._update_status("Calibration failed", "error"))
            self.after(0, lambda: self.status_var.set("Error"))

    def _update_button_states(self):
        """Update button visibility based on measurement state."""
        if hasattr(self, 'start_container') and hasattr(self, 'stop_container') and hasattr(self, 'clear_container'):
            if self.is_measuring:
                # Hide start, show stop in the same position (before Clear)
                self.start_container.pack_forget()
                self.stop_container.pack(padx=20, pady=8, fill=tk.X, before=self.clear_container)
            else:
                # Show start, hide stop (start goes back to its position before Clear)
                self.stop_container.pack_forget()
                self.start_container.pack(padx=20, pady=8, fill=tk.X, before=self.clear_container)
    
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
        self._log_debug("Measurement session started - sweeping 0° to 90°", "INFO")
        
        # Start measurement thread
        self.measurement_thread = threading.Thread(target=self._measurement_worker, daemon=True)
        self.measurement_thread.start()
        self._log_debug("Measurement thread started", "INFO")
    
    def _on_stop_measurement(self) -> None:
        """Stop the current measurement session."""
        if not self.is_measuring:
            return
        
        # Stop measurement
        self.is_measuring = False
        self.status_var.set("Stopping...")
        self._update_status("Stopping measurement...", "warning")
        self._update_button_states()
        self._log_debug(f"Measurement stopped at angle {self.current_angle:.2f}°", "INFO")
        
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
        summary = f"""Measurement Results Summary:

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
        
        self._log_debug(f"Exporting {len(measurements)} measurements to {file_path}", "INFO")
        
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
            self._log_debug(f"Export completed successfully: {len(measurements)} records", "SUCCESS")
            self._update_status(f"Data exported successfully to {os.path.basename(file_path)}", "success")
            self.after(2000, lambda: self.status_var.set("Ready"))
        except Exception as e:
            error_msg = f"Export failed: {str(e)}"
            self._log_debug(error_msg, "ERROR")
            messagebox.showerror("Export Error", f"Failed to export data: {str(e)}")
            self._update_status("Export failed", "error")

    def _on_settings(self) -> None:
        """Open settings dialog."""
        self.status_var.set("Settings")
        self._update_status("Opening settings...", "info")
        # Settings dialog can be implemented here

    def _toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        self.is_fullscreen = not self.is_fullscreen
        self.attributes('-fullscreen', self.is_fullscreen)
        if self.is_fullscreen:
            self._update_status("Fullscreen mode - Press F11 or Esc to exit", "info")
        else:
            self._update_status("Windowed mode", "info")
    
    def _exit_fullscreen(self) -> None:
        """Exit fullscreen mode."""
        if self.is_fullscreen:
            self._toggle_fullscreen()
    
    def _on_help(self) -> None:
        """Show help/about dialog."""
        about_text = """SPAM - Scanner for Polarized Anisotropic Materials
        
Version 1.01

A local desktop application for scanning and analyzing polarized anisotropic materials.

Features:
- Real-time measurement visualization
- Data storage and management
- Calibration functionality
- Data export (JSON/CSV)
- Fullscreen mode (F11)

Keyboard Shortcuts:
- F11: Toggle fullscreen
- Ctrl+D: Debug Console
- Esc: Exit fullscreen

For use on Raspberry Pi and other local systems."""
        messagebox.showinfo("About SPAM", about_text)
        self.status_var.set("Help")
        self._update_status("Help requested", "info")
    
    def _on_debug_console(self) -> None:
        """Open debug/advanced console window."""
        if self.debug_window is None or not self.debug_window.winfo_exists():
            self.debug_window = DebugConsole(self)
        else:
            self.debug_window.lift()
            self.debug_window.focus()
    
    def _log_debug(self, message: str, level: str = "INFO") -> None:
        """Add a message to the debug log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.debug_log.append(log_entry)
        # Keep only last 1000 entries
        if len(self.debug_log) > 1000:
            self.debug_log = self.debug_log[-1000:]
        # Update debug window if open
        if self.debug_window and self.debug_window.winfo_exists():
            self.debug_window.update_console_log()
    
    def _on_close(self):
        """Handle window close event."""
        # Stop any ongoing measurements
        self.is_measuring = False
        
        # Close database connection
        if hasattr(self, 'db'):
            self.db.close()
        
        # Destroy window
        self.destroy()


class DebugConsole(tk.Toplevel):
    """Advanced debug console window for system diagnostics."""
    
    def __init__(self, parent: SPAMGui):
        super().__init__(parent)
        self.parent = parent
        self.title("SPAM - Debug Console")
        self.geometry("900x700")
        self.configure(bg=parent.COLORS['bg_main'])
        
        # Make it a modal-like window (stays on top)
        self.transient(parent)
        self.grab_set()
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self._create_system_info_tab()
        self._create_database_tab()
        self._create_measurement_log_tab()
        self._create_console_tab()
        self._create_config_tab()
        
        # Close button
        btn_frame = tk.Frame(self, bg=parent.COLORS['bg_main'])
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        close_btn = tk.Button(btn_frame, text="Close", command=self.destroy,
                            bg=parent.COLORS['secondary'],
                            fg=parent.COLORS['text_light'],
                            font=("Segoe UI", 10, "bold"),
                            relief=tk.FLAT, cursor="hand2",
                            padx=20, pady=5)
        close_btn.pack(side=tk.RIGHT)
        
        refresh_btn = tk.Button(btn_frame, text="Refresh All", command=self._refresh_all,
                              bg=parent.COLORS['accent'],
                              fg=parent.COLORS['text_light'],
                              font=("Segoe UI", 10, "bold"),
                              relief=tk.FLAT, cursor="hand2",
                              padx=20, pady=5)
        refresh_btn.pack(side=tk.RIGHT, padx=(0, 10))
        
        # Initial refresh
        self._refresh_all()
        
        # Set up periodic refresh for measurement log
        self._schedule_refresh()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _schedule_refresh(self):
        """Schedule periodic refresh of measurement log."""
        if self.winfo_exists():
            # Refresh measurement log every 2 seconds
            self._update_measurement_log()
            self.after(2000, self._schedule_refresh)
    
    def _create_system_info_tab(self):
        """Create system information tab."""
        frame = tk.Frame(self.notebook, bg=self.parent.COLORS['bg_main'])
        self.notebook.add(frame, text="System Info")
        
        # Scrollable text widget
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(frame, 
                            bg=self.parent.COLORS['bg_panel'],
                            fg=self.parent.COLORS['text_dark'],
                            font=("Consolas", 9),
                            yscrollcommand=scrollbar.set,
                            wrap=tk.WORD,
                            padx=10, pady=10)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        
        self.system_info_text = text_widget
    
    def _create_database_tab(self):
        """Create database status tab."""
        frame = tk.Frame(self.notebook, bg=self.parent.COLORS['bg_main'])
        self.notebook.add(frame, text="Database")
        
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(frame,
                            bg=self.parent.COLORS['bg_panel'],
                            fg=self.parent.COLORS['text_dark'],
                            font=("Consolas", 9),
                            yscrollcommand=scrollbar.set,
                            wrap=tk.WORD,
                            padx=10, pady=10)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        
        self.database_text = text_widget
    
    def _create_measurement_log_tab(self):
        """Create measurement log tab."""
        frame = tk.Frame(self.notebook, bg=self.parent.COLORS['bg_main'])
        self.notebook.add(frame, text="Measurement Log")
        
        # Treeview for structured display
        tree_frame = tk.Frame(frame, bg=self.parent.COLORS['bg_main'])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar_y = tk.Scrollbar(tree_frame)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        scrollbar_x = tk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        tree = ttk.Treeview(tree_frame,
                          columns=("ID", "Angle", "Permittivity", "Permeability", "Timestamp"),
                          show="headings",
                          yscrollcommand=scrollbar_y.set,
                          xscrollcommand=scrollbar_x.set)
        
        tree.heading("ID", text="ID")
        tree.heading("Angle", text="Angle (°)")
        tree.heading("Permittivity", text="Permittivity (ε)")
        tree.heading("Permeability", text="Permeability (μ)")
        tree.heading("Timestamp", text="Timestamp")
        
        tree.column("ID", width=50)
        tree.column("Angle", width=80)
        tree.column("Permittivity", width=120)
        tree.column("Permeability", width=120)
        tree.column("Timestamp", width=200)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.config(command=tree.yview)
        scrollbar_x.config(command=tree.xview)
        
        self.measurement_tree = tree
    
    def _create_console_tab(self):
        """Create console output tab."""
        frame = tk.Frame(self.notebook, bg=self.parent.COLORS['bg_main'])
        self.notebook.add(frame, text="Console")
        
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(frame,
                            bg="#1E1E1E",  # Dark background for console
                            fg="#00FF00",  # Green text
                            font=("Consolas", 9),
                            yscrollcommand=scrollbar.set,
                            wrap=tk.WORD,
                            padx=10, pady=10)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        
        self.console_text = text_widget
    
    def _create_config_tab(self):
        """Create configuration tab."""
        frame = tk.Frame(self.notebook, bg=self.parent.COLORS['bg_main'])
        self.notebook.add(frame, text="Configuration")
        
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(frame,
                            bg=self.parent.COLORS['bg_panel'],
                            fg=self.parent.COLORS['text_dark'],
                            font=("Consolas", 9),
                            yscrollcommand=scrollbar.set,
                            wrap=tk.WORD,
                            padx=10, pady=10)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        
        self.config_text = text_widget
    
    def _refresh_all(self):
        """Refresh all tabs with current data."""
        self._update_system_info()
        self._update_database_info()
        self._update_measurement_log()
        self.update_console_log()
        self._update_config()
    
    def _update_system_info(self):
        """Update system information tab."""
        import platform
        import sqlalchemy
        import matplotlib
        import numpy
        
        info = []
        info.append("=" * 70)
        info.append("SYSTEM INFORMATION")
        info.append("=" * 70)
        info.append("")
        
        info.append("Python Version:")
        info.append(f"  {sys.version}")
        info.append("")
        
        info.append("Platform:")
        info.append(f"  System: {platform.system()}")
        info.append(f"  Release: {platform.release()}")
        info.append(f"  Version: {platform.version()}")
        info.append(f"  Machine: {platform.machine()}")
        info.append(f"  Processor: {platform.processor()}")
        info.append("")
        
        info.append("Python Path:")
        for path in sys.path:
            info.append(f"  {path}")
        info.append("")
        
        info.append("=" * 70)
        info.append("DEPENDENCIES")
        info.append("=" * 70)
        info.append("")
        info.append(f"SQLAlchemy: {sqlalchemy.__version__}")
        info.append(f"Matplotlib: {matplotlib.__version__}")
        info.append(f"NumPy: {numpy.__version__}")
        info.append("")
        
        info.append("=" * 70)
        info.append("APPLICATION STATE")
        info.append("=" * 70)
        info.append("")
        info.append(f"Measurement Active: {self.parent.is_measuring}")
        info.append(f"Current Angle: {self.parent.current_angle:.2f}°")
        info.append(f"Current Permittivity: {self.parent.current_permittivity:.4f}")
        info.append(f"Current Permeability: {self.parent.current_permeability:.4f}")
        info.append(f"Measurement Thread: {'Running' if self.parent.measurement_thread and self.parent.measurement_thread.is_alive() else 'Not Running'}")
        info.append("")
        
        self.system_info_text.config(state=tk.NORMAL)
        self.system_info_text.delete(1.0, tk.END)
        self.system_info_text.insert(1.0, "\n".join(info))
        self.system_info_text.config(state=tk.DISABLED)
    
    def _update_database_info(self):
        """Update database information tab."""
        from database import engine, SQLALCHEMY_DATABASE_URL
        
        info = []
        info.append("=" * 70)
        info.append("DATABASE INFORMATION")
        info.append("=" * 70)
        info.append("")
        
        info.append("Database URL:")
        info.append(f"  {SQLALCHEMY_DATABASE_URL}")
        info.append("")
        
        # Database file location
        if "sqlite" in SQLALCHEMY_DATABASE_URL.lower():
            db_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
            if not os.path.isabs(db_path):
                # Get the directory of the main script
                main_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                db_path = os.path.join(main_dir, db_path)
            info.append("Database File:")
            info.append(f"  {os.path.abspath(db_path)}")
            if os.path.exists(db_path):
                size = os.path.getsize(db_path)
                info.append(f"  Size: {size:,} bytes ({size/1024:.2f} KB)")
            else:
                info.append("  Status: File does not exist yet")
            info.append("")
        
        # Connection status
        try:
            with engine.connect() as conn:
                info.append("Connection Status: ✓ Connected")
        except Exception as e:
            info.append(f"Connection Status: ✗ Error - {str(e)}")
        info.append("")
        
        # Table information
        info.append("=" * 70)
        info.append("TABLE STATISTICS")
        info.append("=" * 70)
        info.append("")
        
        try:
            # Measurement count
            measurement_count = self.parent.db.query(Measurement).count()
            info.append(f"Measurements Table:")
            info.append(f"  Total Records: {measurement_count}")
            
            if measurement_count > 0:
                latest = self.parent.db.query(Measurement).order_by(Measurement.timestamp.desc()).first()
                oldest = self.parent.db.query(Measurement).order_by(Measurement.timestamp.asc()).first()
                info.append(f"  Latest: {latest.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                info.append(f"  Oldest: {oldest.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            info.append("")
            
            # Calibration count
            calibration_count = self.parent.db.query(Calibration).count()
            info.append(f"Calibrations Table:")
            info.append(f"  Total Records: {calibration_count}")
            
            if calibration_count > 0:
                latest_cal = self.parent.db.query(Calibration).order_by(Calibration.timestamp.desc()).first()
                info.append(f"  Latest: {latest_cal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            info.append("")
            
        except Exception as e:
            info.append(f"Error querying database: {str(e)}")
            info.append("")
        
        self.database_text.config(state=tk.NORMAL)
        self.database_text.delete(1.0, tk.END)
        self.database_text.insert(1.0, "\n".join(info))
        self.database_text.config(state=tk.DISABLED)
    
    def _update_measurement_log(self):
        """Update measurement log tab."""
        # Clear existing items
        for item in self.measurement_tree.get_children():
            self.measurement_tree.delete(item)
        
        try:
            # Get last 100 measurements
            measurements = self.parent.db.query(Measurement).order_by(
                Measurement.timestamp.desc()
            ).limit(100).all()
            
            for m in measurements:
                self.measurement_tree.insert("", tk.END, values=(
                    m.id,
                    f"{m.angle:.2f}",
                    f"{m.permittivity:.4f}",
                    f"{m.permeability:.4f}",
                    m.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                ))
        except Exception as e:
            self.measurement_tree.insert("", tk.END, values=(
                "ERROR", "", "", "", str(e)
            ))
    
    def update_console_log(self):
        """Update console output tab."""
        self.console_text.config(state=tk.NORMAL)
        self.console_text.delete(1.0, tk.END)
        if self.parent.debug_log:
            self.console_text.insert(1.0, "\n".join(self.parent.debug_log[-100:]))  # Last 100 entries
        else:
            self.console_text.insert(1.0, "No log entries yet.")
        # Auto-scroll to bottom
        self.console_text.see(tk.END)
        self.console_text.config(state=tk.DISABLED)
    
    def _update_config(self):
        """Update configuration tab."""
        info = []
        info.append("=" * 70)
        info.append("CURRENT CONFIGURATION")
        info.append("=" * 70)
        info.append("")
        
        info.append("Measurement Settings:")
        info.append(f"  Angle Step: 5.0°")
        info.append(f"  Max Angle: 90.0°")
        info.append(f"  Measurement Interval: 0.5 seconds")
        info.append("")
        
        info.append("Database Settings:")
        from database import SQLALCHEMY_DATABASE_URL
        info.append(f"  Database URL: {SQLALCHEMY_DATABASE_URL}")
        info.append("")
        
        info.append("GUI Settings:")
        info.append(f"  Window Size: {self.parent.winfo_width()}x{self.parent.winfo_height()}")
        info.append(f"  Update Interval: 1 second")
        info.append("")
        
        info.append("Color Scheme:")
        for key, value in self.parent.COLORS.items():
            info.append(f"  {key}: {value}")
        info.append("")
        
        self.config_text.config(state=tk.NORMAL)
        self.config_text.delete(1.0, tk.END)
        self.config_text.insert(1.0, "\n".join(info))
        self.config_text.config(state=tk.DISABLED)
    
    def _on_close(self):
        """Handle window close."""
        self.grab_release()
        self.destroy()


def main() -> None:
    """Entrypoint for running the GUI directly."""
    app = SPAMGui()
    app.mainloop()


if __name__ == "__main__":
=======
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import json
import csv
from datetime import datetime
import threading
import time
import platform

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# Enable DPI awareness on Windows for better resolution
if platform.system() == 'Windows':
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)  # Enable DPI awareness
    except:
        pass  # If DPI awareness fails, continue anyway

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
        
        # Get screen dimensions for better initial sizing
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Start in maximized state for better experience (Windows) or use geometry for others
        if platform.system() == 'Windows':
            self.state('zoomed')  # Windows maximized
        else:
            # For Linux/Mac, use a large window size
            self.geometry(f"{min(screen_width, 1920)}x{min(screen_height, 1080)}")
            self.update_idletasks()
            # Center the window
            x = (screen_width - self.winfo_width()) // 2
            y = (screen_height - self.winfo_height()) // 2
            self.geometry(f"+{x}+{y}")
        
        # Use a modern light theme background
        self.configure(bg=self.COLORS['bg_main'])
        
        # Track fullscreen state
        self.is_fullscreen = False
        
        # Resize debouncing
        self.resize_timer = None
        self.resize_delay = 150  # milliseconds to wait after resize stops

        # Initialize debug logging first (before any log calls)
        self.debug_log = []
        self.debug_window = None
        
        # Measurement state
        self.is_measuring = False
        self.measurement_thread = None
        self.current_angle = 0.0
        self.current_permittivity = 0.00
        self.current_permeability = 0.00
        
        # S-parameters (mock data for display)
        self.s11_mag = 0.0
        self.s11_phase = 0.0
        self.s12_mag = 0.0
        self.s12_phase = 0.0
        self.s21_mag = 0.0
        self.s21_phase = 0.0
        self.s22_mag = 0.0
        self.s22_phase = 0.0
        
        # Control parameters
        self.frequency = 10.0  # GHz
        self.power_level = -10.0  # dBm
        self.angle_step = 5.0  # degrees
        self.measurement_interval = 0.5  # seconds
        
        # Non-idealities tracking
        self.calibration_error = 0.0  # %
        self.noise_level = 0.0  # dB
        self.temperature = 25.0  # °C
        self.humidity = 45.0  # %
        
        # Connection settings
        self.connection_settings = {
            'vna_address': '192.168.1.100',
            'vna_port': '5025',
            'serial_port': 'COM1',
            'baud_rate': '9600',
            'timeout': '5.0',
            'connection_type': 'VNA'
        }

        # Build top‑level components first (show UI quickly)
        self._create_menu()
        self._create_sidebar()
        self._create_info_panel()
        self._create_center_panel()
        self._create_control_panel()
        self._create_status_bar()
        
        # Initialize button states (after sidebar is created)
        if hasattr(self, 'start_container') and hasattr(self, 'stop_container'):
            self._update_button_states()
        
        # Defer heavy initialization until after window is shown
        self.after(100, self._initialize_background)
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _initialize_background(self):
        """Initialize database and start updates after UI is shown."""
        # Initialize database (can be slow on first run)
        try:
            Base.metadata.create_all(bind=engine)
            self.db = SessionLocal()
            self._log_debug("Application initialized", "INFO")
            self._log_debug(f"Database connection established: {engine.url}", "INFO")
        except Exception as e:
            self._log_debug(f"Database initialization error: {e}", "ERROR")
            # Continue anyway - database will be created on first use
        
        # Start periodic updates
        self._update_display()

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
                                  command=self._on_adjust_parameters)
        settings_menu.add_command(label="Connection Setup",
                                  command=self._on_connection_setup)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Debug Console", command=self._on_debug_console,
                             accelerator="Ctrl+D")
        view_menu.add_separator()
        view_menu.add_command(label="Fullscreen", command=self._toggle_fullscreen,
                             accelerator="F11")
        menubar.add_cascade(label="View", menu=view_menu)
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About SPAM", command=self._on_help)
        help_menu.add_command(label="User Guide", command=self._on_help)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        # Bind keyboard shortcuts
        self.bind('<Control-d>', lambda e: self._on_debug_console())
        self.bind('<F11>', lambda e: self._toggle_fullscreen())
        self.bind('<Escape>', lambda e: self._exit_fullscreen() if self.is_fullscreen else None)

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

        # Create action buttons (ordered: Calibrate, Start, Stop, Clear, View, Export, Debug)
        actions = [
            ("Calibrate", self._on_calibrate, self.COLORS['secondary']),
            ("Start Measurement", self._on_start_measurement, self.COLORS['success']),
            ("Stop Measurement", self._on_stop_measurement, self.COLORS['danger']),
            ("Clear Measurements", self._on_clear_measurements, self.COLORS['warning']),
            ("View Results", self._on_view_results, self.COLORS['secondary']),
            ("Export Data", self._on_export, self.COLORS['secondary']),
            ("Debug Console", self._on_debug_console, self.COLORS['text_muted']),
        ]
        
        self.buttons = []
        self.start_button = None
        self.stop_button = None
        self.start_container = None
        self.stop_container = None
        self.clear_container = None  # Reference for positioning
        
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
            
            # Store references to start/stop/clear buttons and their containers
            if "Start Measurement" in label:
                self.start_button = btn
                self.start_container = btn_container
            elif "Stop Measurement" in label:
                self.stop_button = btn
                self.stop_container = btn_container
                btn_container.pack_forget()  # Hide initially
            elif "Clear Measurements" in label:
                self.clear_container = btn_container
            
            self.buttons.append(btn)

        # Spacer to push content to top
        tk.Frame(sidebar_frame, bg=self.COLORS['bg_sidebar']).pack(expand=True)
        
        # Version info at bottom
        version_label = tk.Label(sidebar_frame, text="Version 1.01", 
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
                          font=("Segoe UI", 14, "bold"))
        header.pack(padx=0, pady=(10, 12), anchor="w")

        # Variables for live measurement results
        self.angle_var = tk.StringVar(value="0.0°")
        self.permittivity_var = tk.StringVar(value="0.00")
        self.permeability_var = tk.StringVar(value="0.00")
        self.status_var = tk.StringVar(value="Ready")
        
        # S-parameter variables
        self.s11_var = tk.StringVar(value="0.00∠0°")
        self.s12_var = tk.StringVar(value="0.00∠0°")
        self.s21_var = tk.StringVar(value="0.00∠0°")
        self.s22_var = tk.StringVar(value="0.00∠0°")

        info_items = [
            ("Current Angle", self.angle_var),
            ("Permittivity (ε)", self.permittivity_var),
            ("Permeability (μ)", self.permeability_var),
            ("Status", self.status_var)
        ]
        
        for label_text, var in info_items:
            # Create card-style container for each metric - compact uniform style
            card = tk.Frame(info_frame, bg=self.COLORS['bg_panel'], 
                           relief=tk.FLAT, bd=0)
            card.pack(fill=tk.X, pady=4)
            
            # Add subtle border effect
            border_frame = tk.Frame(card, bg=self.COLORS['secondary'], height=2)
            border_frame.pack(fill=tk.X)
            
            # Content container - more compact padding
            content = tk.Frame(card, bg=self.COLORS['bg_panel'])
            content.pack(fill=tk.BOTH, padx=12, pady=8)
            
            # Label and value in same row for compactness
            header_row = tk.Frame(content, bg=self.COLORS['bg_panel'])
            header_row.pack(fill=tk.X)
            
            lbl = tk.Label(header_row, text=label_text, 
                          bg=self.COLORS['bg_panel'],
                          fg=self.COLORS['text_muted'], 
                          font=("Segoe UI", 9))
            lbl.pack(side=tk.LEFT)
            
            # Value - smaller font, right-aligned
            val = tk.Label(header_row, textvariable=var, 
                          bg=self.COLORS['bg_panel'],
                          fg=self.COLORS['text_dark'], 
                          font=("Segoe UI", 12, "bold"))
            val.pack(side=tk.RIGHT)

        # S-Parameters section - same style as above
        sparam_header = tk.Label(info_frame, text="S-Parameters",
                                 bg=self.COLORS['bg_main'], 
                                 fg=self.COLORS['text_dark'],
                                 font=("Segoe UI", 14, "bold"))
        sparam_header.pack(padx=0, pady=(12, 12), anchor="w")
        
        sparam_items = [
            ("S₁₁", self.s11_var),
            ("S₁₂", self.s12_var),
            ("S₂₁", self.s21_var),
            ("S₂₂", self.s22_var)
        ]
        
        for label_text, var in sparam_items:
            card = tk.Frame(info_frame, bg=self.COLORS['bg_panel'], 
                           relief=tk.FLAT, bd=0)
            card.pack(fill=tk.X, pady=4)
            border_frame = tk.Frame(card, bg=self.COLORS['accent'], height=2)
            border_frame.pack(fill=tk.X)
            content = tk.Frame(card, bg=self.COLORS['bg_panel'])
            content.pack(fill=tk.BOTH, padx=12, pady=8)
            lbl = tk.Label(content, text=label_text, 
                          bg=self.COLORS['bg_panel'],
                          fg=self.COLORS['text_muted'], 
                          font=("Segoe UI", 9))
            lbl.pack(side=tk.LEFT)
            val = tk.Label(content, textvariable=var, 
                          bg=self.COLORS['bg_panel'],
                          fg=self.COLORS['text_dark'], 
                          font=("Segoe UI", 12, "bold"))
            val.pack(side=tk.RIGHT)

        # Spacer to push content to top
        tk.Frame(info_frame, bg=self.COLORS['bg_main']).pack(expand=True)
        
        # System info card at bottom - same compact style
        system_card = tk.Frame(info_frame, bg=self.COLORS['bg_panel'], 
                              relief=tk.FLAT, bd=0)
        system_card.pack(fill=tk.X, pady=(8, 0))
        
        system_header = tk.Frame(system_card, bg=self.COLORS['accent'], height=2)
        system_header.pack(fill=tk.X)
        
        system_content = tk.Frame(system_card, bg=self.COLORS['bg_panel'])
        system_content.pack(fill=tk.BOTH, padx=12, pady=8)
        
        sys_row = tk.Frame(system_content, bg=self.COLORS['bg_panel'])
        sys_row.pack(fill=tk.X)
        
        sys_title = tk.Label(sys_row, text="System Status",
                            bg=self.COLORS['bg_panel'],
                            fg=self.COLORS['text_muted'],
                            font=("Segoe UI", 9))
        sys_title.pack(side=tk.LEFT)
        
        self.system_status_var = tk.StringVar(value="Ready")
        sys_val = tk.Label(sys_row, textvariable=self.system_status_var,
                          bg=self.COLORS['bg_panel'],
                          fg=self.COLORS['success'],
                          font=("Segoe UI", 12, "bold"))
        sys_val.pack(side=tk.RIGHT)

        self.info_frame = info_frame

    # ------------------------------------------------------------------
    # Center panel with graphs
    # ------------------------------------------------------------------
    def _create_center_panel(self) -> None:
        """Create the central area containing two Matplotlib graphs with scrolling."""
        center_frame = tk.Frame(self, bg=self.COLORS['bg_main'])
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 0), pady=15)

        # Title for the graphs section (fixed at top)
        title_frame = tk.Frame(center_frame, bg=self.COLORS['bg_main'])
        title_frame.pack(fill=tk.X, pady=(5, 10))
        
        title = tk.Label(title_frame, text="Real-Time Measurements",
                        bg=self.COLORS['bg_main'],
                        fg=self.COLORS['text_dark'],
                        font=("Segoe UI", 16, "bold"))
        title.pack(side=tk.LEFT)
        
        # Create scrollable frame for graphs
        # Create canvas and scrollbar
        canvas_container = tk.Frame(center_frame, bg=self.COLORS['bg_main'])
        canvas_container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(canvas_container, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        canvas = tk.Canvas(canvas_container, 
                          bg=self.COLORS['bg_main'],
                          yscrollcommand=scrollbar.set,
                          highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=canvas.yview)
        
        # Create scrollable frame inside canvas
        scrollable_frame = tk.Frame(canvas, bg=self.COLORS['bg_main'])
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Function to update scroll region and canvas width
        # Use debouncing to prevent lag during resizing
        self.canvas_resize_timer = None
        
        def configure_scroll_region(event):
            # Debounce scroll region updates
            if self.canvas_resize_timer:
                self.after_cancel(self.canvas_resize_timer)
            
            def delayed_update():
                try:
                    canvas.configure(scrollregion=canvas.bbox("all"))
                    # Make canvas width match scrollable_frame width
                    canvas_width = event.width
                    canvas.itemconfig(canvas_window, width=canvas_width)
                except:
                    pass
                self.canvas_resize_timer = None
            
            self.canvas_resize_timer = self.after(50, delayed_update)  # Shorter delay for canvas
        
        def on_canvas_configure(event):
            # Immediate update for canvas width is fine, but debounce if needed
            try:
                canvas_width = event.width
                canvas.itemconfig(canvas_window, width=canvas_width)
            except:
                pass
        
        scrollable_frame.bind("<Configure>", configure_scroll_region)
        canvas.bind("<Configure>", on_canvas_configure)
        
        # Enable mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # For Linux, use Button-4 and Button-5
        def on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
        
        canvas.bind_all("<Button-4>", on_mousewheel_linux)
        canvas.bind_all("<Button-5>", on_mousewheel_linux)

        # Initialize with empty data - will be populated from database
        angles = np.array([])
        permittivity = np.array([])
        permeability = np.array([])

        # Graph styling configuration - improved for better quality
        graph_style = {
            'facecolor': self.COLORS['bg_panel'],
            'titlecolor': self.COLORS['text_dark'],
            'titlesize': 14,  # Balanced size
            'titleweight': 'bold',
            'labelcolor': self.COLORS['text_dark'],
            'labelsize': 11,  # Balanced size
            'linecolor': self.COLORS['secondary'],
            'linewidth': 2.5,  # Good visibility without being too thick
            'gridcolor': self.COLORS['border'],
            'gridalpha': 0.3,
            'dpi': 100,  # Standard DPI for proper sizing
        }

        # Container for permittivity graph (inside scrollable frame)
        graph1_container = tk.Frame(scrollable_frame, bg=self.COLORS['bg_panel'], 
                                   relief=tk.FLAT, bd=0, height=400)
        graph1_container.pack(fill=tk.X, pady=(0, 15), padx=5)
        graph1_container.pack_propagate(False)  # Prevent shrinking
        
        # Permittivity figure - properly sized to fit container
        fig1 = Figure(figsize=(6, 3.5), dpi=graph_style['dpi'], facecolor=graph_style['facecolor'])
        ax1 = fig1.add_subplot(111, facecolor=graph_style['facecolor'])
        # Set axis limits before plotting (even if empty)
        ax1.set_xlim(0, 90)
        ax1.set_ylim(1.5, 2.5)  # Reasonable range for permittivity
        if len(angles) > 0:
            ax1.plot(angles, permittivity, color=graph_style['linecolor'], 
                    linewidth=graph_style['linewidth'], label='ε')
        ax1.set_title("Permittivity (ε) vs Angle", 
                     color=graph_style['titlecolor'],
                     fontsize=graph_style['titlesize'],
                     fontweight=graph_style['titleweight'],
                     pad=15)
        ax1.set_xlabel("Angle (degrees)", color=graph_style['labelcolor'],
                      fontsize=graph_style['labelsize'], fontweight='medium')
        ax1.set_ylabel("Permittivity (ε)", color=graph_style['labelcolor'],
                      fontsize=graph_style['labelsize'], fontweight='medium')
        ax1.grid(True, alpha=graph_style['gridalpha'], 
                color=graph_style['gridcolor'], linestyle='--')
        ax1.tick_params(colors=graph_style['labelcolor'], labelsize=9)
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.spines['left'].set_color(graph_style['gridcolor'])
        ax1.spines['bottom'].set_color(graph_style['gridcolor'])
        fig1.tight_layout(pad=2.0)
        
        canvas1 = FigureCanvasTkAgg(fig1, master=graph1_container)
        canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        canvas1.draw()

        # Container for permeability graph (inside scrollable frame)
        graph2_container = tk.Frame(scrollable_frame, bg=self.COLORS['bg_panel'], 
                                   relief=tk.FLAT, bd=0, height=400)
        graph2_container.pack(fill=tk.X, pady=(0, 15), padx=5)
        graph2_container.pack_propagate(False)  # Prevent shrinking

        # Permeability figure - properly sized to fit container
        fig2 = Figure(figsize=(6, 3.5), dpi=graph_style['dpi'], facecolor=graph_style['facecolor'])
        ax2 = fig2.add_subplot(111, facecolor=graph_style['facecolor'])
        # Set axis limits before plotting (even if empty)
        ax2.set_xlim(0, 90)
        ax2.set_ylim(1.0, 2.0)  # Reasonable range for permeability
        if len(angles) > 0:
            ax2.plot(angles, permeability, color=self.COLORS['accent'], 
                    linewidth=graph_style['linewidth'], label='μ')
        ax2.set_title("Permeability (μ) vs Angle", 
                     color=graph_style['titlecolor'],
                     fontsize=graph_style['titlesize'],
                     fontweight=graph_style['titleweight'],
                     pad=15)
        ax2.set_xlabel("Angle (degrees)", color=graph_style['labelcolor'],
                      fontsize=graph_style['labelsize'], fontweight='medium')
        ax2.set_ylabel("Permeability (μ)", color=graph_style['labelcolor'],
                      fontsize=graph_style['labelsize'], fontweight='medium')
        ax2.grid(True, alpha=graph_style['gridalpha'], 
                color=graph_style['gridcolor'], linestyle='--')
        ax2.tick_params(colors=graph_style['labelcolor'], labelsize=9)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.spines['left'].set_color(graph_style['gridcolor'])
        ax2.spines['bottom'].set_color(graph_style['gridcolor'])
        fig2.tight_layout(pad=2.0)
        
        canvas2 = FigureCanvasTkAgg(fig2, master=graph2_container)
        canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        canvas2.draw()

        self.center_frame = center_frame
        self.scrollable_frame = scrollable_frame
        self.graphs_canvas = canvas
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
        
        # Bind resize event with debouncing to prevent lag during window resizing
        def on_resize(event):
            # Cancel any pending resize update
            if self.resize_timer:
                self.after_cancel(self.resize_timer)
            
            # Schedule update after user stops resizing (debounced)
            def delayed_resize_update():
                if hasattr(self, 'fig1') and hasattr(self, 'fig2'):
                    try:
                        # Only update layout and redraw after resize is complete
                        self.fig1.tight_layout(pad=2.0)
                        self.fig2.tight_layout(pad=2.0)
                        self.canvas1.draw()
                        self.canvas2.draw()
                        # Update scroll region after resize
                        if hasattr(self, 'graphs_canvas'):
                            self.graphs_canvas.configure(scrollregion=self.graphs_canvas.bbox("all"))
                    except:
                        pass  # Ignore errors during resize
                self.resize_timer = None
            
            # Schedule the update after a delay
            self.resize_timer = self.after(self.resize_delay, delayed_resize_update)
        
        self.bind('<Configure>', on_resize)

    # ------------------------------------------------------------------
    # Control Panel with Parameters and Non-Idealities
    # ------------------------------------------------------------------
    def _create_control_panel(self) -> None:
        """Create a panel showing control parameters and non-idealities."""
        
        # Control Parameters Section - Professional styling
        control_card = tk.Frame(self.scrollable_frame, bg=self.COLORS['bg_panel'], 
                               relief=tk.FLAT, bd=0)
        control_card.pack(fill=tk.X, pady=(0, 12), padx=5)
        
        control_header = tk.Frame(control_card, bg=self.COLORS['secondary'], height=2)
        control_header.pack(fill=tk.X)
        
        control_content = tk.Frame(control_card, bg=self.COLORS['bg_panel'])
        control_content.pack(fill=tk.BOTH, padx=18, pady=16)
        
        title = tk.Label(control_content, text="Control Parameters",
                        bg=self.COLORS['bg_panel'],
                        fg=self.COLORS['text_dark'],
                        font=("Segoe UI", 13, "bold"))
        title.pack(anchor="w", pady=(0, 14))
        
        # Control parameter variables
        self.freq_var = tk.StringVar(value="10.0 GHz")
        self.power_var = tk.StringVar(value="-10.0 dBm")
        self.angle_step_var = tk.StringVar(value="5.0°")
        self.interval_var = tk.StringVar(value="0.5 s")
        
        controls = [
            ("Frequency", self.freq_var),
            ("Power Level", self.power_var),
            ("Angle Step", self.angle_step_var),
            ("Measurement Interval", self.interval_var)
        ]
        
        # Use a more professional grid-like layout
        for i, (label_text, var) in enumerate(controls):
            row = tk.Frame(control_content, bg=self.COLORS['bg_panel'])
            row.pack(fill=tk.X, pady=6)
            
            # Label with consistent width for alignment
            lbl = tk.Label(row, text=label_text, 
                          bg=self.COLORS['bg_panel'],
                          fg=self.COLORS['text_muted'], 
                          font=("Segoe UI", 10),
                          width=20,
                          anchor="w")
            lbl.pack(side=tk.LEFT)
            
            # Value with consistent styling
            val = tk.Label(row, textvariable=var, 
                          bg=self.COLORS['bg_panel'],
                          fg=self.COLORS['text_dark'], 
                          font=("Segoe UI", 11, "bold"),
                          anchor="w")
            val.pack(side=tk.LEFT, padx=(10, 0))
        
        # Non-Idealities Section - Professional styling
        nonideal_card = tk.Frame(self.scrollable_frame, bg=self.COLORS['bg_panel'], 
                                relief=tk.FLAT, bd=0)
        nonideal_card.pack(fill=tk.X, pady=(0, 12), padx=5)
        
        nonideal_header = tk.Frame(nonideal_card, bg=self.COLORS['accent'], height=2)
        nonideal_header.pack(fill=tk.X)
        
        nonideal_content = tk.Frame(nonideal_card, bg=self.COLORS['bg_panel'])
        nonideal_content.pack(fill=tk.BOTH, padx=18, pady=16)
        
        nonideal_title = tk.Label(nonideal_content, text="Non-Idealities & Compensation",
                                 bg=self.COLORS['bg_panel'],
                                 fg=self.COLORS['text_dark'],
                                 font=("Segoe UI", 13, "bold"))
        nonideal_title.pack(anchor="w", pady=(0, 14))
        
        # Non-ideality variables
        self.cal_error_var = tk.StringVar(value="0.0%")
        self.noise_var = tk.StringVar(value="0.0 dB")
        self.temp_var = tk.StringVar(value="25.0°C")
        self.humidity_var = tk.StringVar(value="45.0%")
        
        nonideals = [
            ("Calibration Error", self.cal_error_var),
            ("Noise Level", self.noise_var),
            ("Temperature", self.temp_var),
            ("Humidity", self.humidity_var)
        ]
        
        # Use same professional layout as controls
        for label_text, var in nonideals:
            row = tk.Frame(nonideal_content, bg=self.COLORS['bg_panel'])
            row.pack(fill=tk.X, pady=6)
            
            lbl = tk.Label(row, text=label_text, 
                          bg=self.COLORS['bg_panel'],
                          fg=self.COLORS['text_muted'], 
                          font=("Segoe UI", 10),
                          width=20,
                          anchor="w")
            lbl.pack(side=tk.LEFT)
            
            val = tk.Label(row, textvariable=var, 
                          bg=self.COLORS['bg_panel'],
                          fg=self.COLORS['text_dark'], 
                          font=("Segoe UI", 11, "bold"),
                          anchor="w")
            val.pack(side=tk.LEFT, padx=(10, 0))
        
        # Compensation methods text - improved styling
        comp_text = tk.Text(nonideal_content,
                            bg=self.COLORS['bg_panel'],
                            fg=self.COLORS['text_dark'],
                            font=("Segoe UI", 9),
                            wrap=tk.WORD,
                            height=7,
                            padx=12, pady=12,
                            relief=tk.FLAT,
                            bd=0,
                            spacing1=2,
                            spacing2=1,
                            spacing3=2)
        comp_text.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        
        compensation_info = """Compensation Methods:

• Calibration Error: SOLT (Short-Open-Load-Thru) calibration applied
  to remove systematic errors from VNA measurements

• Noise Reduction: Averaging over multiple samples (default: 16 samples)
  and digital filtering applied to measurement data

• Temperature Effects: Temperature compensation applied using
  material-specific temperature coefficients

• Humidity Effects: Environmental chamber control or compensation
  algorithms account for moisture content variations

• Connector Repeatability: Multiple connection cycles used to
  assess and compensate for connector variations

• Cable Flexure: Fixed cable routing minimizes phase errors
  from cable movement during angle sweeps"""
        
        comp_text.insert(1.0, compensation_info)
        comp_text.config(state=tk.DISABLED)
        
        self.control_panel_frame = control_card

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
        
        status_indicator = tk.Label(left_frame, text="*", 
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
            self._log_debug(f"Measurement recorded: Angle={angle:.2f}°, ε={permittivity:.4f}, μ={permeability:.4f}", "DEBUG")
            return measurement
        except Exception as e:
            self.db.rollback()
            error_msg = f"Error creating measurement: {e}"
            print(error_msg)
            self._log_debug(error_msg, "ERROR")
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
            # Show empty graphs with proper axis limits
            self.ax1.clear()
            self.ax2.clear()
            self.ax1.set_xlim(0, 90)
            self.ax1.set_ylim(1.5, 2.5)
            self.ax1.set_title("Permittivity (ε) vs Angle", 
                             color=self.COLORS['text_dark'],
                             fontsize=14, fontweight='bold', pad=15)
            self.ax1.set_xlabel("Angle (degrees)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax1.set_ylabel("Permittivity (ε)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax1.grid(True, alpha=0.3, color=self.COLORS['border'], linestyle='--')
            self.ax1.tick_params(colors=self.COLORS['text_dark'], labelsize=9)
            self.ax1.spines['top'].set_visible(False)
            self.ax1.spines['right'].set_visible(False)
            self.ax1.spines['left'].set_color(self.COLORS['border'])
            self.ax1.spines['bottom'].set_color(self.COLORS['border'])
            
            self.ax2.set_xlim(0, 90)
            self.ax2.set_ylim(1.0, 2.0)
            self.ax2.set_title("Permeability (μ) vs Angle",
                             color=self.COLORS['text_dark'],
                             fontsize=14, fontweight='bold', pad=15)
            self.ax2.set_xlabel("Angle (degrees)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax2.set_ylabel("Permeability (μ)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax2.grid(True, alpha=0.3, color=self.COLORS['border'], linestyle='--')
            self.ax2.tick_params(colors=self.COLORS['text_dark'], labelsize=9)
            self.ax2.spines['top'].set_visible(False)
            self.ax2.spines['right'].set_visible(False)
            self.ax2.spines['left'].set_color(self.COLORS['border'])
            self.ax2.spines['bottom'].set_color(self.COLORS['border'])
        else:
            # Extract data
            angles = [m.angle for m in measurements]
            permittivity = [m.permittivity for m in measurements]
            permeability = [m.permeability for m in measurements]
            
            # Update permittivity graph
            self.ax1.clear()
            self.ax1.plot(angles, permittivity, color=self.COLORS['secondary'], 
                         linewidth=2.5, label='ε')
            # Set axis limits based on data with some padding
            if angles:
                self.ax1.set_xlim(max(0, min(angles) - 5), min(90, max(angles) + 5))
                self.ax1.set_ylim(max(1.0, min(permittivity) - 0.2), max(permittivity) + 0.2)
            else:
                self.ax1.set_xlim(0, 90)
                self.ax1.set_ylim(1.5, 2.5)
            self.ax1.set_title("Permittivity (ε) vs Angle", 
                             color=self.COLORS['text_dark'],
                             fontsize=14, fontweight='bold', pad=15)
            self.ax1.set_xlabel("Angle (degrees)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax1.set_ylabel("Permittivity (ε)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax1.grid(True, alpha=0.3, color=self.COLORS['border'], linestyle='--')
            self.ax1.tick_params(colors=self.COLORS['text_dark'], labelsize=9)
            self.ax1.spines['top'].set_visible(False)
            self.ax1.spines['right'].set_visible(False)
            self.ax1.spines['left'].set_color(self.COLORS['border'])
            self.ax1.spines['bottom'].set_color(self.COLORS['border'])
            
            # Update permeability graph
            self.ax2.clear()
            self.ax2.plot(angles, permeability, color=self.COLORS['accent'], 
                         linewidth=2.5, label='μ')
            # Set axis limits based on data with some padding
            if angles:
                self.ax2.set_xlim(max(0, min(angles) - 5), min(90, max(angles) + 5))
                self.ax2.set_ylim(max(0.5, min(permeability) - 0.2), max(permeability) + 0.2)
            else:
                self.ax2.set_xlim(0, 90)
                self.ax2.set_ylim(1.0, 2.0)
            self.ax2.set_title("Permeability (μ) vs Angle",
                             color=self.COLORS['text_dark'],
                             fontsize=14, fontweight='bold', pad=15)
            self.ax2.set_xlabel("Angle (degrees)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax2.set_ylabel("Permeability (μ)", color=self.COLORS['text_dark'], 
                              fontsize=11, fontweight='medium')
            self.ax2.grid(True, alpha=0.3, color=self.COLORS['border'], linestyle='--')
            self.ax2.tick_params(colors=self.COLORS['text_dark'], labelsize=9)
            self.ax2.spines['top'].set_visible(False)
            self.ax2.spines['right'].set_visible(False)
            self.ax2.spines['left'].set_color(self.COLORS['border'])
            self.ax2.spines['bottom'].set_color(self.COLORS['border'])
        
        self.fig1.tight_layout(pad=2.0)
        self.fig2.tight_layout(pad=2.0)
        self.canvas1.draw()
        self.canvas2.draw()
        # Update scroll region after drawing
        if hasattr(self, 'graphs_canvas'):
            self.graphs_canvas.configure(scrollregion=self.graphs_canvas.bbox("all"))
    
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
            self.permittivity_var.set("0.00")
            self.permeability_var.set("0.00")
        
        # Update S-parameters display
        self.s11_var.set(f"{self.s11_mag:.3f}∠{self.s11_phase:.1f}°")
        self.s12_var.set(f"{self.s12_mag:.3f}∠{self.s12_phase:.1f}°")
        self.s21_var.set(f"{self.s21_mag:.3f}∠{self.s21_phase:.1f}°")
        self.s22_var.set(f"{self.s22_mag:.3f}∠{self.s22_phase:.1f}°")
        
        # Update control parameters
        self.freq_var.set(f"{self.frequency:.1f} GHz")
        self.power_var.set(f"{self.power_level:.1f} dBm")
        self.angle_step_var.set(f"{self.angle_step:.1f}°")
        self.interval_var.set(f"{self.measurement_interval:.2f} s")
        
        # Update non-idealities (mock values - would come from sensors in real system)
        if self.is_measuring:
            # Simulate small variations during measurement
            self.calibration_error = 0.5 + 0.2 * np.sin(time.time() * 0.1)
            self.noise_level = -80.0 + 2.0 * np.sin(time.time() * 0.15)
            self.temperature = 25.0 + 0.5 * np.sin(time.time() * 0.05)
            self.humidity = 45.0 + 2.0 * np.cos(time.time() * 0.08)
        else:
            self.calibration_error = 0.0
            self.noise_level = 0.0
        
        self.cal_error_var.set(f"{self.calibration_error:.2f}%")
        self.noise_var.set(f"{self.noise_level:.1f} dB")
        self.temp_var.set(f"{self.temperature:.1f}°C")
        self.humidity_var.set(f"{self.humidity:.1f}%")
        
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
        angle_step = self.angle_step  # degrees per measurement
        max_angle = 90.0
        
        while self.is_measuring and self.current_angle <= max_angle:
            # TODO: Replace this with actual hardware reading
            # Example hardware integration:
            #   s_params = read_s_parameters_from_vna(self.current_angle)
            #   permittivity, permeability = convert_s_to_material_props(s_params)
            
            # Simulate S-parameter measurement (replace with actual VNA reading)
            # Generate realistic S-parameters based on material properties
            angle_rad = np.radians(self.current_angle)
            
            # Simulate S-parameters with angle-dependent variation
            # S11 and S22 (reflection coefficients)
            s11_mag = 0.15 + 0.05 * np.sin(angle_rad) + np.random.normal(0, 0.01)
            s11_phase = 180 * np.sin(angle_rad * 0.5) + np.random.normal(0, 2)
            s22_mag = 0.12 + 0.04 * np.cos(angle_rad) + np.random.normal(0, 0.01)
            s22_phase = -180 * np.cos(angle_rad * 0.5) + np.random.normal(0, 2)
            
            # S12 and S21 (transmission coefficients)
            s12_mag = 0.85 - 0.1 * np.sin(angle_rad) + np.random.normal(0, 0.01)
            s12_phase = -45 * np.sin(angle_rad) + np.random.normal(0, 2)
            s21_mag = s12_mag + np.random.normal(0, 0.005)  # S21 ≈ S12 for reciprocal networks
            s21_phase = s12_phase + np.random.normal(0, 1)
            
            # Store S-parameters
            self.s11_mag = s11_mag
            self.s11_phase = s11_phase
            self.s12_mag = s12_mag
            self.s12_phase = s12_phase
            self.s21_mag = s21_mag
            self.s21_phase = s21_phase
            self.s22_mag = s22_mag
            self.s22_phase = s22_phase
            
            # Convert S-parameters to material properties (simplified model)
            # In real implementation, this would use the formulas shown in the GUI
            # For mock data, generate permittivity/permeability from S-parameters
            # Using simplified conversion: ε ≈ f(S11, S21), μ ≈ f(S22, S12)
            permittivity = 2.0 + 0.1 * np.sin(angle_rad) + 0.5 * (s11_mag - 0.15) + np.random.normal(0, 0.02)
            permeability = 1.5 + 0.08 * np.cos(angle_rad) + 0.3 * (s22_mag - 0.12) + np.random.normal(0, 0.02)
            
            # Apply non-ideality corrections (mock)
            # Calibration error compensation
            cal_correction = 1.0 - (self.calibration_error / 100.0)
            permittivity *= cal_correction
            permeability *= cal_correction
            
            # Temperature compensation (mock)
            temp_coeff_eps = -0.001  # per °C
            temp_coeff_mu = -0.0005  # per °C
            temp_diff = self.temperature - 25.0
            permittivity *= (1.0 + temp_coeff_eps * temp_diff)
            permeability *= (1.0 + temp_coeff_mu * temp_diff)
            
            # Save to database
            measurement = self._create_measurement(self.current_angle, permittivity, permeability)
            
            # Update current values
            self.current_permittivity = permittivity
            self.current_permeability = permeability
            
            # Increment angle
            self.current_angle += angle_step
            
            # Log progress every 10 degrees
            if int(self.current_angle) % 10 == 0:
                self.after(0, lambda: self._log_debug(f"Measurement progress: {self.current_angle:.1f}° / 90°", "INFO"))
            
            # Wait before next measurement (adjust based on hardware response time)
            time.sleep(self.measurement_interval)
        
        # Measurement complete or stopped
        self.is_measuring = False
        if self.current_angle > max_angle:
            self.after(0, lambda: self._log_debug("Measurement completed successfully (0-90°)", "SUCCESS"))
            self.after(0, lambda: self._update_status("Measurement completed (0-90°)", "success"))
        else:
            self.after(0, lambda: self._log_debug(f"Measurement stopped at {self.current_angle:.1f}°", "INFO"))
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
        """Perform calibration with two-step process: empty measurement, then material placement."""
        # Step 1: Empty/air calibration
        result = messagebox.askokcancel(
            "Calibration - Step 1",
            "Step 1: Empty Measurement\n\n"
            "Please ensure NO material is in the measurement fixture.\n"
            "The system will now calibrate with air/empty fixture.\n\n"
            "Click OK to begin empty calibration, or Cancel to abort.",
            icon='info'
        )
        
        if not result:
            return  # User cancelled
        
        # Start empty calibration
        self.status_var.set("Calibrating (Empty)...")
        self._update_status("Calibrating with empty fixture...", "warning")
        self._log_debug("Calibration Step 1: Empty measurement started", "INFO")
        
        # Simulate empty calibration measurement
        # In real system, this would take S-parameter measurements with no material
        def step1_complete():
            self._log_debug("Calibration Step 1: Empty measurement completed", "SUCCESS")
            
            # Step 2: Material placement
            result2 = messagebox.askokcancel(
                "Calibration - Step 2",
                "Step 2: Material Placement\n\n"
                "Please place your material sample in the measurement fixture.\n"
                "Ensure it is properly positioned and secured.\n\n"
                "Click OK to continue with material calibration, or Cancel to abort.",
                icon='info'
            )
            
            if not result2:
                self.status_var.set("Ready")
                self._update_status("Calibration cancelled by user", "info")
                self._log_debug("Calibration cancelled at Step 2", "INFO")
                return
            
            # Start material calibration
            self.status_var.set("Calibrating (Material)...")
            self._update_status("Calibrating with material sample...", "warning")
            self._log_debug("Calibration Step 2: Material measurement started", "INFO")
            
            # Simulate material calibration measurement
            # In real system, this would take S-parameter measurements with material
            def step2_complete():
                # Create calibration record with both steps
                calibration_params = {
                    "step1": "empty_measurement",
                    "step2": "material_measurement",
                    "timestamp_step1": datetime.now().isoformat(),
                    "timestamp_step2": datetime.now().isoformat()
                }
                
                calibration = self._create_calibration(parameters=calibration_params)
                
                if calibration:
                    self._log_debug(f"Calibration completed successfully (ID: {calibration.id})", "SUCCESS")
                    self._update_status("Calibration completed successfully", "success")
                    self.status_var.set("Ready")
                    messagebox.showinfo(
                        "Calibration Complete",
                        "Calibration completed successfully!\n\n"
                        "The system is now ready for measurements.\n"
                        "You can start taking measurements with the calibrated system."
                    )
                else:
                    self._log_debug("Calibration failed", "ERROR")
                    self._update_status("Calibration failed", "error")
                    self.status_var.set("Error")
                    messagebox.showerror("Calibration Error", "Calibration failed. Please try again.")
            
            # Simulate calibration delay (2 seconds for material measurement)
            self.after(2000, step2_complete)
        
        # Simulate calibration delay (2 seconds for empty measurement)
        self.after(2000, step1_complete)

    def _update_button_states(self):
        """Update button visibility based on measurement state."""
        if hasattr(self, 'start_container') and hasattr(self, 'stop_container') and hasattr(self, 'clear_container'):
            if self.is_measuring:
                # Hide start, show stop in the same position (before Clear)
                self.start_container.pack_forget()
                self.stop_container.pack(padx=20, pady=8, fill=tk.X, before=self.clear_container)
            else:
                # Show start, hide stop (start goes back to its position before Clear)
                self.stop_container.pack_forget()
                self.start_container.pack(padx=20, pady=8, fill=tk.X, before=self.clear_container)
    
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
        self._log_debug("Measurement session started - sweeping 0° to 90°", "INFO")
        
        # Start measurement thread
        self.measurement_thread = threading.Thread(target=self._measurement_worker, daemon=True)
        self.measurement_thread.start()
        self._log_debug("Measurement thread started", "INFO")
    
    def _on_stop_measurement(self) -> None:
        """Stop the current measurement session."""
        if not self.is_measuring:
            return
        
        # Stop measurement
        self.is_measuring = False
        self.status_var.set("Stopping...")
        self._update_status("Stopping measurement...", "warning")
        self._update_button_states()
        self._log_debug(f"Measurement stopped at angle {self.current_angle:.2f}°", "INFO")
        
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
                self.permittivity_var.set("0.00")
                self.permeability_var.set("0.00")
                
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
        summary = f"""Measurement Results Summary:

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
        
        self._log_debug(f"Exporting {len(measurements)} measurements to {file_path}", "INFO")
        
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
            self._log_debug(f"Export completed successfully: {len(measurements)} records", "SUCCESS")
            self._update_status(f"Data exported successfully to {os.path.basename(file_path)}", "success")
            self.after(2000, lambda: self.status_var.set("Ready"))
        except Exception as e:
            error_msg = f"Export failed: {str(e)}"
            self._log_debug(error_msg, "ERROR")
            messagebox.showerror("Export Error", f"Failed to export data: {str(e)}")
            self._update_status("Export failed", "error")

    def _on_adjust_parameters(self) -> None:
        """Open parameters adjustment dialog."""
        dialog = tk.Toplevel(self)
        dialog.title("Adjust Parameters")
        dialog.geometry("450x400")
        dialog.configure(bg=self.COLORS['bg_main'])
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (450 // 2)
        y = (dialog.winfo_screenheight() // 2) - (400 // 2)
        dialog.geometry(f"450x400+{x}+{y}")
        
        # Header
        header = tk.Label(dialog, text="Measurement Parameters",
                         bg=self.COLORS['bg_main'],
                         fg=self.COLORS['text_dark'],
                         font=("Segoe UI", 14, "bold"))
        header.pack(pady=(20, 20))
        
        # Content frame
        content = tk.Frame(dialog, bg=self.COLORS['bg_panel'], padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Parameter variables
        freq_var = tk.StringVar(value=str(self.frequency))
        power_var = tk.StringVar(value=str(self.power_level))
        angle_step_var = tk.StringVar(value=str(self.angle_step))
        interval_var = tk.StringVar(value=str(self.measurement_interval))
        max_angle_var = tk.StringVar(value="90.0")
        
        # Parameter inputs
        params = [
            ("Frequency (GHz):", freq_var, 1.0, 100.0),
            ("Power Level (dBm):", power_var, -50.0, 20.0),
            ("Angle Step (degrees):", angle_step_var, 0.1, 45.0),
            ("Measurement Interval (s):", interval_var, 0.1, 10.0),
            ("Max Angle (degrees):", max_angle_var, 0.0, 180.0),
        ]
        
        entries = []
        for i, (label, var, min_val, max_val) in enumerate(params):
            row = tk.Frame(content, bg=self.COLORS['bg_panel'])
            row.pack(fill=tk.X, pady=8)
            
            lbl = tk.Label(row, text=label, 
                          bg=self.COLORS['bg_panel'],
                          fg=self.COLORS['text_dark'],
                          font=("Segoe UI", 10),
                          width=22,
                          anchor="w")
            lbl.pack(side=tk.LEFT, padx=(0, 10))
            
            entry = tk.Entry(row, textvariable=var,
                           bg=self.COLORS['bg_panel'],
                           fg=self.COLORS['text_dark'],
                           font=("Segoe UI", 10),
                           width=15,
                           relief=tk.SOLID,
                           bd=1)
            entry.pack(side=tk.LEFT)
            entries.append((entry, var, min_val, max_val))
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.COLORS['bg_main'])
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        def save_params():
            try:
                # Validate and save parameters
                self.frequency = float(freq_var.get())
                self.power_level = float(power_var.get())
                self.angle_step = float(angle_step_var.get())
                self.measurement_interval = float(interval_var.get())
                
                # Validate ranges
                if not (1.0 <= self.frequency <= 100.0):
                    raise ValueError("Frequency must be between 1.0 and 100.0 GHz")
                if not (-50.0 <= self.power_level <= 20.0):
                    raise ValueError("Power level must be between -50.0 and 20.0 dBm")
                if not (0.1 <= self.angle_step <= 45.0):
                    raise ValueError("Angle step must be between 0.1 and 45.0 degrees")
                if not (0.1 <= self.measurement_interval <= 10.0):
                    raise ValueError("Measurement interval must be between 0.1 and 10.0 seconds")
                
                self._log_debug(f"Parameters updated: f={self.frequency}GHz, P={self.power_level}dBm, step={self.angle_step}°, interval={self.measurement_interval}s", "INFO")
                self._update_status("Parameters updated successfully", "success")
                dialog.destroy()
            except ValueError as e:
                messagebox.showerror("Invalid Parameter", str(e))
        
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                              bg=self.COLORS['text_muted'],
                              fg=self.COLORS['text_light'],
                              font=("Segoe UI", 10, "bold"),
                              relief=tk.FLAT,
                              padx=20, pady=8,
                              cursor="hand2")
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        save_btn = tk.Button(btn_frame, text="Save", command=save_params,
                            bg=self.COLORS['success'],
                            fg=self.COLORS['text_light'],
                            font=("Segoe UI", 10, "bold"),
                            relief=tk.FLAT,
                            padx=20, pady=8,
                            cursor="hand2")
        save_btn.pack(side=tk.RIGHT)
    
    def _on_connection_setup(self) -> None:
        """Open connection setup dialog."""
        dialog = tk.Toplevel(self)
        dialog.title("Connection Setup")
        dialog.geometry("500x450")
        dialog.configure(bg=self.COLORS['bg_main'])
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (450 // 2)
        dialog.geometry(f"500x450+{x}+{y}")
        
        # Header
        header = tk.Label(dialog, text="Connection Configuration",
                         bg=self.COLORS['bg_main'],
                         fg=self.COLORS['text_dark'],
                         font=("Segoe UI", 14, "bold"))
        header.pack(pady=(20, 20))
        
        # Content frame
        content = tk.Frame(dialog, bg=self.COLORS['bg_panel'], padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # VNA Connection Section
        vna_frame = tk.LabelFrame(content, text="VNA Connection",
                                 bg=self.COLORS['bg_panel'],
                                 fg=self.COLORS['text_dark'],
                                 font=("Segoe UI", 11, "bold"),
                                 padx=15, pady=15)
        vna_frame.pack(fill=tk.X, pady=(0, 15))
        
        vna_address_var = tk.StringVar(value=self.connection_settings.get('vna_address', '192.168.1.100'))
        vna_port_var = tk.StringVar(value=self.connection_settings.get('vna_port', '5025'))
        
        tk.Label(vna_frame, text="VNA IP Address:", 
                bg=self.COLORS['bg_panel'],
                fg=self.COLORS['text_dark'],
                font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", pady=5, padx=(0, 10))
        tk.Entry(vna_frame, textvariable=vna_address_var,
                bg=self.COLORS['bg_panel'],
                fg=self.COLORS['text_dark'],
                font=("Segoe UI", 10),
                width=20).grid(row=0, column=1, sticky="w", pady=5)
        
        tk.Label(vna_frame, text="VNA Port:", 
                bg=self.COLORS['bg_panel'],
                fg=self.COLORS['text_dark'],
                font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=5, padx=(0, 10))
        tk.Entry(vna_frame, textvariable=vna_port_var,
                bg=self.COLORS['bg_panel'],
                fg=self.COLORS['text_dark'],
                font=("Segoe UI", 10),
                width=20).grid(row=1, column=1, sticky="w", pady=5)
        
        # Serial Connection Section
        serial_frame = tk.LabelFrame(content, text="Serial Connection",
                                     bg=self.COLORS['bg_panel'],
                                     fg=self.COLORS['text_dark'],
                                     font=("Segoe UI", 11, "bold"),
                                     padx=15, pady=15)
        serial_frame.pack(fill=tk.X, pady=(0, 15))
        
        serial_port_var = tk.StringVar(value=self.connection_settings.get('serial_port', 'COM1'))
        baud_rate_var = tk.StringVar(value=self.connection_settings.get('baud_rate', '9600'))
        timeout_var = tk.StringVar(value=self.connection_settings.get('timeout', '5.0'))
        
        tk.Label(serial_frame, text="Serial Port:", 
                bg=self.COLORS['bg_panel'],
                fg=self.COLORS['text_dark'],
                font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", pady=5, padx=(0, 10))
        tk.Entry(serial_frame, textvariable=serial_port_var,
                bg=self.COLORS['bg_panel'],
                fg=self.COLORS['text_dark'],
                font=("Segoe UI", 10),
                width=20).grid(row=0, column=1, sticky="w", pady=5)
        
        tk.Label(serial_frame, text="Baud Rate:", 
                bg=self.COLORS['bg_panel'],
                fg=self.COLORS['text_dark'],
                font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=5, padx=(0, 10))
        tk.Entry(serial_frame, textvariable=baud_rate_var,
                bg=self.COLORS['bg_panel'],
                fg=self.COLORS['text_dark'],
                font=("Segoe UI", 10),
                width=20).grid(row=1, column=1, sticky="w", pady=5)
        
        tk.Label(serial_frame, text="Timeout (s):", 
                bg=self.COLORS['bg_panel'],
                fg=self.COLORS['text_dark'],
                font=("Segoe UI", 10)).grid(row=2, column=0, sticky="w", pady=5, padx=(0, 10))
        tk.Entry(serial_frame, textvariable=timeout_var,
                bg=self.COLORS['bg_panel'],
                fg=self.COLORS['text_dark'],
                font=("Segoe UI", 10),
                width=20).grid(row=2, column=1, sticky="w", pady=5)
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.COLORS['bg_main'])
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        def save_connection():
            try:
                # Save connection settings
                self.connection_settings = {
                    'vna_address': vna_address_var.get(),
                    'vna_port': vna_port_var.get(),
                    'serial_port': serial_port_var.get(),
                    'baud_rate': baud_rate_var.get(),
                    'timeout': timeout_var.get(),
                    'connection_type': 'VNA'
                }
                
                # Validate
                if not vna_address_var.get():
                    raise ValueError("VNA IP address is required")
                if not vna_port_var.get().isdigit():
                    raise ValueError("VNA port must be a number")
                if not baud_rate_var.get().isdigit():
                    raise ValueError("Baud rate must be a number")
                
                self._log_debug(f"Connection settings updated: VNA={vna_address_var.get()}:{vna_port_var.get()}, Serial={serial_port_var.get()}@{baud_rate_var.get()}", "INFO")
                self._update_status("Connection settings saved", "success")
                dialog.destroy()
            except ValueError as e:
                messagebox.showerror("Invalid Setting", str(e))
        
        def test_connection():
            messagebox.showinfo("Connection Test", 
                              "Connection test functionality would be implemented here.\n\n"
                              "This would test the connection to the VNA and serial devices.")
        
        test_btn = tk.Button(btn_frame, text="Test Connection", command=test_connection,
                            bg=self.COLORS['accent'],
                            fg=self.COLORS['text_light'],
                            font=("Segoe UI", 10, "bold"),
                            relief=tk.FLAT,
                            padx=20, pady=8,
                            cursor="hand2")
        test_btn.pack(side=tk.LEFT)
        
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                              bg=self.COLORS['text_muted'],
                              fg=self.COLORS['text_light'],
                              font=("Segoe UI", 10, "bold"),
                              relief=tk.FLAT,
                              padx=20, pady=8,
                              cursor="hand2")
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        save_btn = tk.Button(btn_frame, text="Save", command=save_connection,
                            bg=self.COLORS['success'],
                            fg=self.COLORS['text_light'],
                            font=("Segoe UI", 10, "bold"),
                            relief=tk.FLAT,
                            padx=20, pady=8,
                            cursor="hand2")
        save_btn.pack(side=tk.RIGHT)

    def _toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        self.is_fullscreen = not self.is_fullscreen
        self.attributes('-fullscreen', self.is_fullscreen)
        if self.is_fullscreen:
            self._update_status("Fullscreen mode - Press F11 or Esc to exit", "info")
        else:
            self._update_status("Windowed mode", "info")
    
    def _exit_fullscreen(self) -> None:
        """Exit fullscreen mode."""
        if self.is_fullscreen:
            self._toggle_fullscreen()
    
    def _on_help(self) -> None:
        """Show help/about dialog."""
        about_text = """SPAM - Scanner for Polarized Anisotropic Materials
        
Version 1.01

A local desktop application for scanning and analyzing polarized anisotropic materials.

Features:
- Real-time measurement visualization
- Data storage and management
- Calibration functionality
- Data export (JSON/CSV)
- Fullscreen mode (F11)

Keyboard Shortcuts:
- F11: Toggle fullscreen
- Ctrl+D: Debug Console
- Esc: Exit fullscreen

For use on Raspberry Pi and other local systems."""
        messagebox.showinfo("About SPAM", about_text)
        self.status_var.set("Help")
        self._update_status("Help requested", "info")
    
    def _on_debug_console(self) -> None:
        """Open debug/advanced console window."""
        if self.debug_window is None or not self.debug_window.winfo_exists():
            self.debug_window = DebugConsole(self)
        else:
            self.debug_window.lift()
            self.debug_window.focus()
    
    def _log_debug(self, message: str, level: str = "INFO") -> None:
        """Add a message to the debug log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.debug_log.append(log_entry)
        # Keep only last 1000 entries
        if len(self.debug_log) > 1000:
            self.debug_log = self.debug_log[-1000:]
        # Update debug window if open
        if self.debug_window and self.debug_window.winfo_exists():
            self.debug_window.update_console_log()
    
    def _on_close(self):
        """Handle window close event."""
        # Stop any ongoing measurements
        self.is_measuring = False
        
        # Close database connection
        if hasattr(self, 'db'):
            self.db.close()
        
        # Destroy window
        self.destroy()


class DebugConsole(tk.Toplevel):
    """Advanced debug console window for system diagnostics."""
    
    def __init__(self, parent: SPAMGui):
        super().__init__(parent)
        self.parent = parent
        self.title("SPAM - Debug Console")
        self.geometry("900x700")
        self.configure(bg=parent.COLORS['bg_main'])
        
        # Make it a modal-like window (stays on top)
        self.transient(parent)
        self.grab_set()
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self._create_system_info_tab()
        self._create_database_tab()
        self._create_measurement_log_tab()
        self._create_console_tab()
        self._create_config_tab()
        
        # Close button
        btn_frame = tk.Frame(self, bg=parent.COLORS['bg_main'])
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        close_btn = tk.Button(btn_frame, text="Close", command=self.destroy,
                            bg=parent.COLORS['secondary'],
                            fg=parent.COLORS['text_light'],
                            font=("Segoe UI", 10, "bold"),
                            relief=tk.FLAT, cursor="hand2",
                            padx=20, pady=5)
        close_btn.pack(side=tk.RIGHT)
        
        refresh_btn = tk.Button(btn_frame, text="Refresh All", command=self._refresh_all,
                              bg=parent.COLORS['accent'],
                              fg=parent.COLORS['text_light'],
                              font=("Segoe UI", 10, "bold"),
                              relief=tk.FLAT, cursor="hand2",
                              padx=20, pady=5)
        refresh_btn.pack(side=tk.RIGHT, padx=(0, 10))
        
        # Initial refresh
        self._refresh_all()
        
        # Set up periodic refresh for measurement log
        self._schedule_refresh()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _schedule_refresh(self):
        """Schedule periodic refresh of measurement log."""
        if self.winfo_exists():
            # Refresh measurement log every 2 seconds
            self._update_measurement_log()
            self.after(2000, self._schedule_refresh)
    
    def _create_system_info_tab(self):
        """Create system information tab."""
        frame = tk.Frame(self.notebook, bg=self.parent.COLORS['bg_main'])
        self.notebook.add(frame, text="System Info")
        
        # Scrollable text widget
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(frame, 
                            bg=self.parent.COLORS['bg_panel'],
                            fg=self.parent.COLORS['text_dark'],
                            font=("Consolas", 9),
                            yscrollcommand=scrollbar.set,
                            wrap=tk.WORD,
                            padx=10, pady=10)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        
        self.system_info_text = text_widget
    
    def _create_database_tab(self):
        """Create database status tab."""
        frame = tk.Frame(self.notebook, bg=self.parent.COLORS['bg_main'])
        self.notebook.add(frame, text="Database")
        
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(frame,
                            bg=self.parent.COLORS['bg_panel'],
                            fg=self.parent.COLORS['text_dark'],
                            font=("Consolas", 9),
                            yscrollcommand=scrollbar.set,
                            wrap=tk.WORD,
                            padx=10, pady=10)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        
        self.database_text = text_widget
    
    def _create_measurement_log_tab(self):
        """Create measurement log tab."""
        frame = tk.Frame(self.notebook, bg=self.parent.COLORS['bg_main'])
        self.notebook.add(frame, text="Measurement Log")
        
        # Treeview for structured display
        tree_frame = tk.Frame(frame, bg=self.parent.COLORS['bg_main'])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar_y = tk.Scrollbar(tree_frame)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        scrollbar_x = tk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        tree = ttk.Treeview(tree_frame,
                          columns=("ID", "Angle", "Permittivity", "Permeability", "Timestamp"),
                          show="headings",
                          yscrollcommand=scrollbar_y.set,
                          xscrollcommand=scrollbar_x.set)
        
        tree.heading("ID", text="ID")
        tree.heading("Angle", text="Angle (°)")
        tree.heading("Permittivity", text="Permittivity (ε)")
        tree.heading("Permeability", text="Permeability (μ)")
        tree.heading("Timestamp", text="Timestamp")
        
        tree.column("ID", width=50)
        tree.column("Angle", width=80)
        tree.column("Permittivity", width=120)
        tree.column("Permeability", width=120)
        tree.column("Timestamp", width=200)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.config(command=tree.yview)
        scrollbar_x.config(command=tree.xview)
        
        self.measurement_tree = tree
    
    def _create_console_tab(self):
        """Create console output tab."""
        frame = tk.Frame(self.notebook, bg=self.parent.COLORS['bg_main'])
        self.notebook.add(frame, text="Console")
        
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(frame,
                            bg="#1E1E1E",  # Dark background for console
                            fg="#00FF00",  # Green text
                            font=("Consolas", 9),
                            yscrollcommand=scrollbar.set,
                            wrap=tk.WORD,
                            padx=10, pady=10)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        
        self.console_text = text_widget
    
    def _create_config_tab(self):
        """Create configuration tab."""
        frame = tk.Frame(self.notebook, bg=self.parent.COLORS['bg_main'])
        self.notebook.add(frame, text="Configuration")
        
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(frame,
                            bg=self.parent.COLORS['bg_panel'],
                            fg=self.parent.COLORS['text_dark'],
                            font=("Consolas", 9),
                            yscrollcommand=scrollbar.set,
                            wrap=tk.WORD,
                            padx=10, pady=10)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        
        self.config_text = text_widget
    
    def _refresh_all(self):
        """Refresh all tabs with current data."""
        self._update_system_info()
        self._update_database_info()
        self._update_measurement_log()
        self.update_console_log()
        self._update_config()
    
    def _update_system_info(self):
        """Update system information tab."""
        import platform
        import sqlalchemy
        import matplotlib
        import numpy
        
        info = []
        info.append("=" * 70)
        info.append("SYSTEM INFORMATION")
        info.append("=" * 70)
        info.append("")
        
        info.append("Python Version:")
        info.append(f"  {sys.version}")
        info.append("")
        
        info.append("Platform:")
        info.append(f"  System: {platform.system()}")
        info.append(f"  Release: {platform.release()}")
        info.append(f"  Version: {platform.version()}")
        info.append(f"  Machine: {platform.machine()}")
        info.append(f"  Processor: {platform.processor()}")
        info.append("")
        
        info.append("Python Path:")
        for path in sys.path:
            info.append(f"  {path}")
        info.append("")
        
        info.append("=" * 70)
        info.append("DEPENDENCIES")
        info.append("=" * 70)
        info.append("")
        info.append(f"SQLAlchemy: {sqlalchemy.__version__}")
        info.append(f"Matplotlib: {matplotlib.__version__}")
        info.append(f"NumPy: {numpy.__version__}")
        info.append("")
        
        info.append("=" * 70)
        info.append("APPLICATION STATE")
        info.append("=" * 70)
        info.append("")
        info.append(f"Measurement Active: {self.parent.is_measuring}")
        info.append(f"Current Angle: {self.parent.current_angle:.2f}°")
        info.append(f"Current Permittivity: {self.parent.current_permittivity:.4f}")
        info.append(f"Current Permeability: {self.parent.current_permeability:.4f}")
        info.append(f"Measurement Thread: {'Running' if self.parent.measurement_thread and self.parent.measurement_thread.is_alive() else 'Not Running'}")
        info.append("")
        
        self.system_info_text.config(state=tk.NORMAL)
        self.system_info_text.delete(1.0, tk.END)
        self.system_info_text.insert(1.0, "\n".join(info))
        self.system_info_text.config(state=tk.DISABLED)
    
    def _update_database_info(self):
        """Update database information tab."""
        from database import engine, SQLALCHEMY_DATABASE_URL
        
        info = []
        info.append("=" * 70)
        info.append("DATABASE INFORMATION")
        info.append("=" * 70)
        info.append("")
        
        info.append("Database URL:")
        info.append(f"  {SQLALCHEMY_DATABASE_URL}")
        info.append("")
        
        # Database file location
        if "sqlite" in SQLALCHEMY_DATABASE_URL.lower():
            db_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
            if not os.path.isabs(db_path):
                # Get the directory of the main script
                main_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                db_path = os.path.join(main_dir, db_path)
            info.append("Database File:")
            info.append(f"  {os.path.abspath(db_path)}")
            if os.path.exists(db_path):
                size = os.path.getsize(db_path)
                info.append(f"  Size: {size:,} bytes ({size/1024:.2f} KB)")
            else:
                info.append("  Status: File does not exist yet")
            info.append("")
        
        # Connection status
        try:
            with engine.connect() as conn:
                info.append("Connection Status: ✓ Connected")
        except Exception as e:
            info.append(f"Connection Status: ✗ Error - {str(e)}")
        info.append("")
        
        # Table information
        info.append("=" * 70)
        info.append("TABLE STATISTICS")
        info.append("=" * 70)
        info.append("")
        
        try:
            # Measurement count
            measurement_count = self.parent.db.query(Measurement).count()
            info.append(f"Measurements Table:")
            info.append(f"  Total Records: {measurement_count}")
            
            if measurement_count > 0:
                latest = self.parent.db.query(Measurement).order_by(Measurement.timestamp.desc()).first()
                oldest = self.parent.db.query(Measurement).order_by(Measurement.timestamp.asc()).first()
                info.append(f"  Latest: {latest.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                info.append(f"  Oldest: {oldest.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            info.append("")
            
            # Calibration count
            calibration_count = self.parent.db.query(Calibration).count()
            info.append(f"Calibrations Table:")
            info.append(f"  Total Records: {calibration_count}")
            
            if calibration_count > 0:
                latest_cal = self.parent.db.query(Calibration).order_by(Calibration.timestamp.desc()).first()
                info.append(f"  Latest: {latest_cal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            info.append("")
            
        except Exception as e:
            info.append(f"Error querying database: {str(e)}")
            info.append("")
        
        self.database_text.config(state=tk.NORMAL)
        self.database_text.delete(1.0, tk.END)
        self.database_text.insert(1.0, "\n".join(info))
        self.database_text.config(state=tk.DISABLED)
    
    def _update_measurement_log(self):
        """Update measurement log tab."""
        # Clear existing items
        for item in self.measurement_tree.get_children():
            self.measurement_tree.delete(item)
        
        try:
            # Get last 100 measurements
            measurements = self.parent.db.query(Measurement).order_by(
                Measurement.timestamp.desc()
            ).limit(100).all()
            
            for m in measurements:
                self.measurement_tree.insert("", tk.END, values=(
                    m.id,
                    f"{m.angle:.2f}",
                    f"{m.permittivity:.4f}",
                    f"{m.permeability:.4f}",
                    m.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                ))
        except Exception as e:
            self.measurement_tree.insert("", tk.END, values=(
                "ERROR", "", "", "", str(e)
            ))
    
    def update_console_log(self):
        """Update console output tab."""
        self.console_text.config(state=tk.NORMAL)
        self.console_text.delete(1.0, tk.END)
        if self.parent.debug_log:
            self.console_text.insert(1.0, "\n".join(self.parent.debug_log[-100:]))  # Last 100 entries
        else:
            self.console_text.insert(1.0, "No log entries yet.")
        # Auto-scroll to bottom
        self.console_text.see(tk.END)
        self.console_text.config(state=tk.DISABLED)
    
    def _update_config(self):
        """Update configuration tab."""
        info = []
        info.append("=" * 70)
        info.append("CURRENT CONFIGURATION")
        info.append("=" * 70)
        info.append("")
        
        info.append("Measurement Settings:")
        info.append(f"  Angle Step: 5.0°")
        info.append(f"  Max Angle: 90.0°")
        info.append(f"  Measurement Interval: 0.5 seconds")
        info.append("")
        
        info.append("Database Settings:")
        from database import SQLALCHEMY_DATABASE_URL
        info.append(f"  Database URL: {SQLALCHEMY_DATABASE_URL}")
        info.append("")
        
        info.append("GUI Settings:")
        info.append(f"  Window Size: {self.parent.winfo_width()}x{self.parent.winfo_height()}")
        info.append(f"  Update Interval: 1 second")
        info.append("")
        
        info.append("Color Scheme:")
        for key, value in self.parent.COLORS.items():
            info.append(f"  {key}: {value}")
        info.append("")
        
        self.config_text.config(state=tk.NORMAL)
        self.config_text.delete(1.0, tk.END)
        self.config_text.insert(1.0, "\n".join(info))
        self.config_text.config(state=tk.DISABLED)
    
    def _on_close(self):
        """Handle window close."""
        self.grab_release()
        self.destroy()


def main() -> None:
    """Entrypoint for running the GUI directly."""
    app = SPAMGui()
    app.mainloop()


if __name__ == "__main__":
>>>>>>> Stashed changes
    main()