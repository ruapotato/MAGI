# src/magi_shell/monitors/application.py
"""
Model manager application implementation.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GLib, Adw
import subprocess
import signal
import sys

from .window import ModelManager

class ModelManagerApplication(Adw.Application):
    """Application class for model management interface."""
    
    def __init__(self):
        super().__init__(application_id='com.system.magi.models')
    
    def do_activate(self):
        """Handle application activation."""
        window = ModelManager(self)
        window.present()
        
        # Position window
        display = window.get_display()
        monitor = display.get_monitors()[0]
        geometry = monitor.get_geometry()
        
        window_width, window_height = window.get_default_size()
        x_position = geometry.x + geometry.width - window_width - 10
        y_position = geometry.y + 10
        
        def position_window():
            try:
                window_id = subprocess.check_output(
                    ['xdotool', 'search', '--name', '^MAGI Model Status$']
                ).decode().strip()
                
                if window_id:
                    window_id = window_id.split('\n')[0]
                    
                    # Set window properties
                    subprocess.run(['wmctrl', '-i', '-r', window_id, '-t', '-1'])
                    subprocess.run(['wmctrl', '-i', '-r', window_id, '-b', 'add,below,sticky'])
                    subprocess.run(['wmctrl', '-i', '-r', window_id, '-e', f'0,{x_position},{y_position},-1,-1'])
                    subprocess.run(['wmctrl', '-i', '-r', window_id, '-b', 'add,sticky'])
            except Exception as e:
                print(f"Window positioning error: {e}")
                GLib.timeout_add(500, position_window)
                return False
            return False
        
        GLib.timeout_add(100, position_window)

def main():
    """Application entry point."""
    app = ModelManagerApplication()
    
    def cleanup(signum=None, frame=None):
        """Clean up application resources."""
        print("\nCleaning up...")
        for window in app.get_windows():
            if isinstance(window, ModelManager):
                window.cleanup()
                break
        app.quit()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    try:
        status = app.run(None)
        cleanup()
        return status
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1

# Run if executed directly
if __name__ == "__main__":
    sys.exit(main())
