#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GLib, Adw, Gio, GObject, Gdk
import os
import subprocess
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('magi-launcher')

# Fix the import path
try:
    from magi_shell.core.theme import ThemeManager
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from magi_shell.core.theme import ThemeManager

class MAGILauncher(Adw.Window):
    def __init__(self, parent=None):
        super().__init__()
        
        # Window setup
        self.set_title("MAGI Launcher")
        self.set_default_size(600, 500)
        self.set_transient_for(parent)
        
        # Hide window initially
        self.set_opacity(0.0)
        
        # Register with theme manager
        ThemeManager().register_window(self)
        
        # Add focus tracking
        focus_controller = Gtk.EventControllerFocus.new()
        focus_controller.connect('leave', self._on_focus_lost)
        self.add_controller(focus_controller)
        
        # Add key events for Escape
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect('key-pressed', self._on_key_pressed)
        self.add_controller(key_controller)
        
        # Main layout
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.box.set_margin_top(8)
        self.box.set_margin_bottom(8)
        self.box.set_margin_start(8)
        self.box.set_margin_end(8)
        
        # Search entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.connect('search-changed', self._on_search_changed)
        self.search_entry.connect('activate', self._on_entry_activated)
        self.box.append(self.search_entry)
        
        # App list
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.list_box.connect('row-activated', self._on_row_activated)
        self.list_box.set_filter_func(self._filter_apps)
        self.list_box.set_sort_func(self._sort_apps)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self.list_box)
        self.box.append(scrolled)
        
        self.set_content(self.box)
        
        # Load apps
        self._apps = []
        GLib.idle_add(self._load_applications)

    def _on_focus_lost(self, controller):
        """Handle window losing focus."""
        logger.debug("Focus lost, closing launcher")
        self.close()

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events."""
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _on_entry_activated(self, entry):
        """Handle Enter key in search entry."""
        # Get first visible row
        for row in self.list_box.observe_children():
            if row.get_mapped():  # Check if row is visible (not filtered out)
                self._launch_app(row)
                break

    def _load_applications(self):
        """Load applications from standard locations."""
        desktop_dirs = [
            '/usr/share/applications',
            '/usr/local/share/applications',
            os.path.expanduser('~/.local/share/applications')
        ]
        
        added_apps = set()  # Track apps we've already added
        
        for directory in desktop_dirs:
            if not os.path.exists(directory):
                logger.debug(f"Skipping non-existent directory: {directory}")
                continue
                
            logger.debug(f"Scanning directory: {directory}")
            for file_name in os.listdir(directory):
                if not file_name.endswith('.desktop'):
                    continue
                    
                path = os.path.join(directory, file_name)
                logger.debug(f"Processing desktop file: {path}")
                
                try:
                    # Try to parse desktop file manually first
                    should_show = True
                    with open(path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip() == 'NoDisplay=true':
                                should_show = False
                                break
                            if line.strip() == 'Hidden=true':
                                should_show = False
                                break
                    
                    if not should_show:
                        logger.debug(f"Skipping hidden app: {file_name}")
                        continue
                    
                    # Now try to load as DesktopAppInfo
                    app_info = Gio.DesktopAppInfo.new_from_filename(path)
                    if not app_info:
                        logger.debug(f"Failed to load desktop file: {path}")
                        continue
                    
                    # Check if we already added this app
                    app_id = app_info.get_id()
                    if app_id in added_apps:
                        logger.debug(f"Skipping duplicate app: {app_id}")
                        continue
                    
                    # Create row
                    row = Gtk.ListBoxRow()
                    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                    box.set_margin_top(8)
                    box.set_margin_bottom(8)
                    box.set_margin_start(8)
                    box.set_margin_end(8)
                    
                    # App icon
                    icon = app_info.get_icon()
                    if icon:
                        image = Gtk.Image.new_from_gicon(icon)
                        image.set_pixel_size(32)
                        box.append(image)
                    else:
                        # Fallback icon
                        image = Gtk.Image.new_from_icon_name("application-x-executable")
                        image.set_pixel_size(32)
                        box.append(image)
                    
                    # App info box
                    info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                    info_box.set_hexpand(True)
                    
                    # App name
                    name = Gtk.Label(label=app_info.get_display_name() or file_name)
                    name.set_halign(Gtk.Align.START)
                    name.add_css_class('heading')
                    info_box.append(name)
                    
                    # App description
                    description = app_info.get_description()
                    if description:
                        desc_label = Gtk.Label(label=description)
                        desc_label.set_halign(Gtk.Align.START)
                        desc_label.add_css_class('caption')
                        desc_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
                        info_box.append(desc_label)
                    
                    box.append(info_box)
                    row.set_child(box)
                    
                    # Store app info
                    row.app_info = app_info
                    row.search_text = (
                        f"{app_info.get_display_name() or ''} {app_info.get_description() or ''}"
                    ).lower()
                    
                    self.list_box.append(row)
                    self._apps.append(row)
                    added_apps.add(app_id)
                    logger.debug(f"Added app: {app_id}")
                    
                except Exception as e:
                    logger.error(f"Error processing {path}: {e}")
        
        logger.info(f"Loaded {len(self._apps)} applications")
        
        # Focus search
        self.search_entry.grab_focus()
        return False
    
    def _filter_apps(self, row):
        """Filter apps based on search text."""
        text = self.search_entry.get_text().lower()
        if not text:
            return True
        return text in row.search_text
    
    def _sort_apps(self, row1, row2):
        """Sort apps alphabetically."""
        name1 = row1.app_info.get_display_name() or ""
        name2 = row2.app_info.get_display_name() or ""
        return name1.lower() > name2.lower()
    
    def _on_search_changed(self, entry):
        """Handle search text changes."""
        self.list_box.invalidate_filter()
    
    def _launch_app(self, row):
        """Launch application from row."""
        if row and row.app_info:
            try:
                row.app_info.launch()
                self.close()
            except Exception as e:
                logger.error(f"Failed to launch application: {e}")
    
    def _on_row_activated(self, list_box, row):
        """Launch selected application."""
        self._launch_app(row)
    
    def present(self):
        """Present window in top left corner."""
        super().present()
        
        # Position window in top left corner with slight offset from panel
        display = self.get_display()
        monitor = display.get_monitors()[0]  # Primary monitor
        geometry = monitor.get_geometry()
        
        # Position just below the top panel
        x = geometry.x + 2  # Small margin from left edge
        y = geometry.y + 30  # Below top panel
        
        self.set_default_size(600, 500)
        
        def position_window():
            try:
                window_id = subprocess.check_output(
                    ['xdotool', 'search', '--name', '^MAGI Launcher$']
                ).decode().strip()
                
                if window_id:
                    window_id = window_id.split('\n')[0]
                    subprocess.run(['wmctrl', '-i', '-r', window_id, 
                                 '-e', f'0,{x},{y},-1,-1'])
                    
                    # Show window after positioning
                    def show_window():
                        self.set_opacity(1.0)
                        return False
                    GLib.timeout_add(50, show_window)
                    
            except Exception as e:
                logger.error(f"Window positioning error: {e}")
                GLib.timeout_add(100, position_window)
                return False
            return False
        
        GLib.timeout_add(100, position_window)

# Allow running as standalone script for testing
if __name__ == '__main__':
    app = Adw.Application(application_id='com.system.magi.launcher')
    
    def on_activate(app):
        win = MAGILauncher()
        win.present()
    
    app.connect('activate', on_activate)
    app.run(None)
