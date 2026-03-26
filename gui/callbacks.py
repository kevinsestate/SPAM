"""CallbacksMixin: status, calibrate, export, help, fullscreen, debug log."""

import os
import json
import csv
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, filedialog


class CallbacksMixin:
    """Provides command callbacks: status update, calibrate, export, help, fullscreen, debug log."""

    def _update_status(self, message: str, status_type: str = "info"):
        self.status_text_var.set(message)
        ts = datetime.now().strftime("%H:%M:%S")
        self.time_label.config(text=ts)
        cmap = {"success": self._t('success'), "warning": self._t('warning'),
                "error": self._t('error'), "info": self._t('accent')}
        self._status_dot.config(fg=cmap.get(status_type, self._t('success')))

    def _on_calibrate(self):
        r = messagebox.askokcancel("Calibration - Step 1",
            "Ensure NO material is in the fixture.\nClick OK to begin empty calibration.")
        if not r:
            return
        self.status_var.set("Calibrating...")
        self._update_status("Empty calibration...", "warning")
        self._log_debug("Calibration Step 1 started", "INFO")
        def step1_complete():
            self._log_debug("Step 1 complete", "SUCCESS")
            r2 = messagebox.askokcancel("Calibration - Step 2",
                "Place material sample and click OK.")
            if not r2:
                self.status_var.set("Ready")
                return
            self._update_status("Material calibration...", "warning")
            def step2_complete():
                cal = self._create_calibration({"step1": "empty", "step2": "material",
                    "ts1": datetime.now().isoformat(), "ts2": datetime.now().isoformat()})
                if cal:
                    self._log_debug("Calibration complete", "SUCCESS")
                    self._update_status("Calibration complete", "success")
                    self.status_var.set("Ready")
                    messagebox.showinfo("Done", "Calibration complete.")
                else:
                    self._update_status("Calibration failed", "error")
            self.after(2000, step2_complete)
        self.after(2000, step1_complete)

    def _update_button_states(self):
        if hasattr(self, 'start_container') and hasattr(self, 'stop_container') and hasattr(self, 'clear_container'):
            if self.is_measuring:
                self.start_container.pack_forget()
                self.stop_container.pack(fill=tk.X, padx=6, pady=3, before=self.clear_container)
            else:
                self.stop_container.pack_forget()
                self.start_container.pack(fill=tk.X, padx=6, pady=3, before=self.clear_container)

    def _on_export(self):
        ms = self._get_measurements()
        if not ms:
            messagebox.showwarning("No Data", "Nothing to export.")
            return
        fp = filedialog.asksaveasfilename(defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV", "*.csv")])
        if not fp:
            return
        try:
            if fp.endswith('.csv'):
                with open(fp, 'w', newline='') as f:
                    w = csv.writer(f)
                    w.writerow(['id','angle','permittivity','permeability','timestamp'])
                    for m in ms:
                        w.writerow([m.id, m.angle, m.permittivity, m.permeability, m.timestamp.isoformat()])
            else:
                data = [{"id": m.id, "angle": m.angle, "permittivity": m.permittivity,
                         "permeability": m.permeability, "timestamp": m.timestamp.isoformat()} for m in ms]
                with open(fp, 'w') as f:
                    json.dump(data, f, indent=2)
            self._update_status(f"Exported to {os.path.basename(fp)}", "success")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes('-fullscreen', self.is_fullscreen)

    def _exit_fullscreen(self):
        if self.is_fullscreen:
            self._toggle_fullscreen()

    def _on_help(self):
        messagebox.showinfo("About SPAM",
            "SPAM - Scanner for Polarized Anisotropic Materials\nVersion 1.01\n\n"
            "Shortcuts: F11 Fullscreen, Ctrl+D Debug, Esc Exit fullscreen")

    def _on_debug_console(self):
        from .debug_console import DebugConsole
        if self.debug_window is None or not self.debug_window.winfo_exists():
            self.debug_window = DebugConsole(self)
        else:
            self.debug_window.lift()
            self.debug_window.focus()

    def _log_debug(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.debug_log.append(f"[{ts}] [{level}] {message}")
        if len(self.debug_log) > 1000:
            self.debug_log = self.debug_log[-1000:]
        if self.debug_window and self.debug_window.winfo_exists():
            self.debug_window.update_console_log()
