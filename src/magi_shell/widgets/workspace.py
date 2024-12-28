# src/magi_shell/widgets/workspace.py
"""
Workspace management widgets for MAGI Shell.

Provides GUI components for managing and switching between virtual workspaces
using wmctrl and xdotool.
"""

from gi.repository import Gtk
import subprocess
from ..utils.cache import Cache
from ..utils.widget_pool import WidgetPool
from ..utils.config import load_config

class WorkspaceSwitcher(Gtk.Box):
    """
    Widget for switching between virtual workspaces.
    
    Provides buttons for each workspace and maintains their state based on
    the currently active workspace.
    
    Attributes:
        _update_manager: UpdateManager instance for scheduling updates
        _button_pool: WidgetPool for workspace buttons
        _active_buttons: Dictionary of active workspace buttons
        _cache: Cache instance for workspace state
    """
    
    def __init__(self, update_manager):
        print("Initializing WorkspaceSwitcher...")  # Debug print
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        
        self.config = load_config()  # Load config in init
        self._update_manager = update_manager
        self._button_pool = WidgetPool(Gtk.Button)
        self._active_buttons = {}
        self._cache = Cache()
        
        self._setup_workspace_buttons()
        print("WorkspaceSwitcher initialization complete")  # Debug print
    
    def _setup_workspace_buttons(self):
        """Initialize workspace buttons."""
        print("Setting up workspace buttons...")  # Debug print
        # Use self.config instead of calling load_config() again
        for realm_number in range(self.config['workspace_count']):
            portal_button = self._button_pool.acquire()
            portal_button.set_label(str(realm_number + 1))
            portal_button.connect('clicked', self._switch_workspace, realm_number)
            self.append(portal_button)
            self._active_buttons[realm_number] = portal_button
        
        self._update_manager.schedule(
            'workspaces',
            self._update_current_workspace,
            1000  # Update interval
        )
        print("Workspace buttons setup complete")  # Debug print
    
    def _switch_workspace(self, button, workspace_num):
        """Transport the user to another dimension"""
        try:
            # Find current dimension
            output = subprocess.check_output(['wmctrl', '-d']).decode()
            current_realm = None
            for line in output.splitlines():
                if '*' in line:
                    current_realm = int(line.split()[0])
                    break
            
            if current_realm != workspace_num:
                # Engage the dimensional transport
                subprocess.run(['wmctrl', '-s', str(workspace_num)], check=True)
                subprocess.run(['xdotool', 'set_desktop', str(workspace_num)], check=True)
                
                # Ensure reality stabilizes
                GLib.timeout_add(100, self._update_current_workspace)
        except Exception as dimensional_rift:
            print(f"Workspace transport malfunction: {dimensional_rift}")
    
    def _update_current_workspace(self):
        """Update our knowledge of the current dimension"""
        try:
            current_realm = self._cache.get('current_workspace')
            if current_realm is not None:
                return
            
            output = subprocess.check_output(['wmctrl', '-d']).decode()
            for line in output.splitlines():
                if '*' in line:
                    workspace = int(line.split()[0])
                    if workspace != current_realm:
                        self._cache.set('current_workspace', workspace)
                        self._update_buttons(workspace)
                    break
        except Exception as reality_glitch:
            print(f"Workspace reality check failed: {reality_glitch}")
    
    def _update_buttons(self, current_realm):
        """Update the appearance of dimensional portals"""
        for realm_num, button in self._active_buttons.items():
            if realm_num == current_realm:
                button.add_css_class('active-workspace')
            else:
                button.remove_css_class('active-workspace')
