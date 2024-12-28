# src/magi_shell/widgets/window.py
"""
Window management widgets for MAGI Shell.

Provides components for managing and switching between windows
using wmctrl and related window management tools.
"""

from gi.repository import Gtk, GLib
import subprocess
from ..utils.cache import Cache
from ..utils.widget_pool import WidgetPool

class WindowList(Gtk.Box):
    """
    Widget displaying a list of all windows as buttons.
    
    Provides a dynamic list of buttons representing all open windows,
    allowing quick switching between them. Windows are updated in real-time
    as they are opened, closed, or their titles change.
    
    Attributes:
        _update_manager: UpdateManager instance for scheduling updates
        _button_pool: WidgetPool for window buttons
        _window_buttons: Dictionary mapping window IDs to their buttons
        _cache: Cache instance for window state
    """
    
    def __init__(self, update_manager):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        self.set_hexpand(True)
        
        self._update_manager = update_manager
        self._button_pool = WidgetPool(Gtk.Button)
        self._window_buttons = {}
        self._cache = Cache()
        
        self._update_window_list()
        GLib.timeout_add(1000, self._update_window_list)
    
    def _update_window_list(self):
        """Update the list of windows and their buttons."""
        try:
            window_census = subprocess.check_output(['wmctrl', '-l']).decode()
            surviving_windows = set()
            
            for window_scroll in window_census.splitlines():
                window_parts = window_scroll.split(None, 3)
                if len(window_parts) >= 4:
                    window_id = window_parts[0]
                    window_realm = int(window_parts[1])
                    window_title = window_parts[3]
                    
                    if "MAGI" in window_title or "Desktop" in window_title:
                        continue
                        
                    surviving_windows.add(window_id)
                    if window_id not in self._window_buttons:
                        window_button = self._button_pool.acquire()
                        window_button.set_label(window_title[:30])
                        window_button.connect('clicked', self.summon_window, window_id)
                        self.append(window_button)
                        self._window_buttons[window_id] = window_button
                    else:
                        self._window_buttons[window_id].set_label(window_title[:30])
            
            # Remove buttons for closed windows
            for departed_id in list(self._window_buttons.keys()):
                if departed_id not in surviving_windows:
                    departed_button = self._window_buttons.pop(departed_id)
                    self.remove(departed_button)
                    self._button_pool.release(departed_button)
            
        except Exception as e:
            print(f"Window list update error: {e}")
        
        return True
    
    def summon_window(self, button, window_id):
        """
        Activate and raise the specified window.
        
        Args:
            button: The button that was clicked
            window_id: ID of the window to activate
        """
        try:
            subprocess.run(['wmctrl', '-ia', window_id], check=True)
        except Exception as e:
            print(f"Window activation error: {e}")
