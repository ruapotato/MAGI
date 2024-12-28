# src/magi_shell/core/application.py
"""
Core application implementation for MAGI Shell.

Provides the main application class that initializes and manages
the MAGI Shell interface panels.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw
import signal
import sys
from .panel import MAGIPanel

class MAGIApplication(Adw.Application):
    """
    Main MAGI Shell application.
    
    Initializes and manages the top and bottom panels, handles
    application lifecycle and cleanup.
    
    Attributes:
        top_panel: Top panel window instance
        bottom_panel: Bottom panel window instance
    """
    
    def __init__(self):
        """Initialize the MAGI Shell application."""
        super().__init__(application_id='com.system.magi.shell')
        
    def do_activate(self):
        """Handle application activation."""
        try:
            # Create panels
            self.top_panel = MAGIPanel(self, position='top')
            self.bottom_panel = MAGIPanel(self, position='bottom')
            
            # Show panels
            for panel in (self.top_panel, self.bottom_panel):
                panel.present()
                
        except Exception as e:
            print(f"Application activation error: {e}")
            sys.exit(1)

def main():
    """Main entry point for the MAGI Shell application."""
    try:
        app = MAGIApplication()
        
        def cleanup(signum=None, frame=None):
            """Clean up resources on exit."""
            print("\nCleaning up...")
            sys.exit(0)
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, cleanup)
        signal.signal(signal.SIGTERM, cleanup)
        
        # Run application
        exit_code = app.run(sys.argv)
        cleanup()
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
