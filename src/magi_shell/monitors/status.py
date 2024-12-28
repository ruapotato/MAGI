# src/magi_shell/monitors/status.py
"""
Status monitoring components for MAGI Shell.
"""

from gi.repository import Gtk, GLib

class ServiceStatusDisplay:
    """Display component for service status with indicator and progress bar."""
    
    def __init__(self, service_name):
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        # Header with status indicator
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.indicator = Gtk.Label(label="●")
        header.append(self.indicator)
        header.append(Gtk.Label(label=service_name))
        self.box.append(header)
        
        # Progress bar
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_hexpand(True)
        self.box.append(self.progress_bar)
        
        # Status message
        self.status_label = Gtk.Label()
        self.status_label.set_xalign(0)
        self.box.append(self.status_label)
    
    def update_status(self, status, progress=0, message=""):
        """Update display status."""
        self.progress_bar.set_fraction(progress / 100)
        self.status_label.set_text(message)
        self._update_indicator(status)
    
    def _update_indicator(self, status):
        """Update the status indicator style."""
        self.indicator.remove_css_class('status-running')
        self.indicator.remove_css_class('status-error')
        self.indicator.remove_css_class('status-loading')
        
        if status == "Running":
            self.indicator.add_css_class('status-running')
        elif status == "Error":
            self.indicator.add_css_class('status-error')
        else:
            self.indicator.add_css_class('status-loading')
