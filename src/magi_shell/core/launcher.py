#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GLib, Adw, Gio, GObject, Gdk
import os
import subprocess
import sys
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('magi-launcher')

# Fix the import path
try:
    from magi_shell.core.theme import ThemeManager
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from magi_shell.core.theme import ThemeManager

class MAGILauncher(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        
        # Window setup
        self.set_title("MAGI Launcher")
        self.set_default_size(600, 500)
        self.set_opacity(0.0)
        
        # Register with theme manager
        ThemeManager().register_window(self)
        
        self.setup_ui()
        GLib.timeout_add(50, self.setup_position)
        
        # Add focus-out event controller
        focus_controller = Gtk.EventControllerFocus.new()
        focus_controller.connect('leave', self._on_focus_lost)
        self.add_controller(focus_controller)

    def setup_ui(self):
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

    def setup_position(self):
        display = self.get_display()
        monitor = display.get_monitors()[0]
        geometry = monitor.get_geometry()
        x = geometry.x + 2  # Small margin from left edge
        y = geometry.y + 30  # Below top panel
        
        self.present()
        GLib.idle_add(self.move_and_show_window, x, y)
        return False

    def move_and_show_window(self, x, y):
        try:
            out = subprocess.check_output(['xdotool', 'search', '--name', '^MAGI Launcher$']).decode().strip()
            if out:
                window_id = out.split('\n')[0]
                subprocess.run(['wmctrl', '-i', '-r', window_id, '-e', f'0,{x},{y},-1,-1'], check=True)
                subprocess.run(['wmctrl', '-i', '-a', window_id], check=True)
        except Exception as e:
            logger.error(f"Failed to position window: {e}")
        
        GLib.timeout_add(50, self.fade_in_window)
        return False

    def fade_in_window(self):
        current_opacity = self.get_opacity()
        if current_opacity < 1.0:
            self.set_opacity(min(current_opacity + 0.2, 1.0))
            return True
        return False

    def _on_focus_lost(self, controller):
            self.close()
    
    def _on_entry_activated(self, entry):
        for row in self.list_box.observe_children():
            if row.get_mapped():  # Check if row is visible (not filtered out)
                self._launch_app(row)
                break

    def _load_applications(self):
        desktop_dirs = [
            '/usr/share/applications',
            '/usr/local/share/applications',
            os.path.expanduser('~/.local/share/applications')
        ]
        
        added_apps = set()
        
        for directory in desktop_dirs:
            if not os.path.exists(directory):
                continue
                
            for file_name in os.listdir(directory):
                if not file_name.endswith('.desktop'):
                    continue
                    
                path = os.path.join(directory, file_name)
                
                try:
                    app_info = Gio.DesktopAppInfo.new_from_filename(path)
                    if not app_info or app_info.get_id() in added_apps:
                        continue
                    
                    row = self._create_app_row(app_info)
                    self.list_box.append(row)
                    self._apps.append(row)
                    added_apps.add(app_info.get_id())
                    
                except Exception:
                    pass
        
        # Load Flatpak applications
        try:
            flatpak_output = subprocess.check_output(['flatpak', 'list', '--columns=application,name,description,arch'], text=True)
            logger.info(f"Flatpak list output:\n{flatpak_output}")
            
            flatpak_apps = [line.split('\t') for line in flatpak_output.strip().split('\n')[1:]]  # Skip header
            
            logger.info(f"Parsed Flatpak apps: {flatpak_apps}")
            
            for app_data in flatpak_apps:
                # Debugging: log each app data entry
                logger.debug(f"Processing app data: {app_data}")
                
                # Ensure we have at least 2 values and skip non-application entries
                if len(app_data) < 2:
                    logger.warning(f"Skipping app data with insufficient columns: {app_data}")
                    continue
                
                # Skip platform, runtime, and GL entries
                if any(x in app_data[0] for x in [
                    'Platform', 'Platform.GL', 'freedesktop', 'nvidia', 'runtime'
                ]):
                    logger.debug(f"Skipping platform/runtime entry: {app_data[0]}")
                    continue
                
                # Use the first two columns as app_id and name
                app_id = app_data[0]
                name = app_data[1]
                
                # Try to get a description if available
                description = app_data[2] if len(app_data) > 2 else ""
                
                if app_id in added_apps:
                    logger.debug(f"App {app_id} already added")
                    continue
                
                # Construct a .desktop file path for Flatpak app
                desktop_file_path = os.path.expanduser(f'~/.local/share/applications/{app_id}.desktop')
                logger.debug(f"Attempting to create/use desktop file: {desktop_file_path}")
                
                # Check if a .desktop file already exists for the Flatpak app
                existing_desktop_files = [
                    f'/var/lib/flatpak/exports/share/applications/{app_id}.desktop',
                    f'/usr/local/share/applications/{app_id}.desktop',
                    desktop_file_path
                ]
                
                desktop_file_to_use = None
                for possible_file in existing_desktop_files:
                    if os.path.exists(possible_file):
                        desktop_file_to_use = possible_file
                        logger.debug(f"Found existing desktop file: {possible_file}")
                        break
                
                # If no existing desktop file, create a new one
                if not desktop_file_to_use:
                    try:
                        with open(desktop_file_path, 'w') as f:
                            f.write(f'[Desktop Entry]\n')
                            f.write(f'Type=Application\n')
                            f.write(f'Name={name}\n')
                            f.write(f'Comment={description}\n')
                            f.write(f'Exec=flatpak run {app_id}\n')
                            f.write(f'Icon=package-x-generic\n')
                            f.write(f'Categories=Utility;\n')
                        desktop_file_to_use = desktop_file_path
                        logger.debug(f"Created new desktop file: {desktop_file_path}")
                    except IOError as io_err:
                        logger.error(f"Failed to create desktop file for {app_id}: {io_err}")
                        continue
                
                # Try to create DesktopAppInfo
                try:
                    # Use the full path to the .desktop file
                    app_info = Gio.DesktopAppInfo.new_from_filename(desktop_file_to_use)
                    
                    if not app_info:
                        logger.error(f"Failed to create DesktopAppInfo for {app_id} using file {desktop_file_to_use}")
                        continue
                    
                    row = self._create_app_row(app_info)
                    self.list_box.append(row)
                    self._apps.append(row)
                    added_apps.add(app_id)
                    logger.info(f"Successfully added Flatpak app: {app_id}")
                
                except Exception as info_err:
                    logger.error(f"Error processing Flatpak app {app_id}: {info_err}")
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to load Flatpak applications: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading Flatpak applications: {e}")
        
        # Log final apps added
        logger.info(f"Total Flatpak apps added: {len(added_apps)}")

    def _create_app_row(self, app_info):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        
        icon = app_info.get_icon()
        if icon:
            image = Gtk.Image.new_from_gicon(icon)
            image.set_pixel_size(32)
            box.append(image)
        else:
            image = Gtk.Image.new_from_icon_name("application-x-executable")
            image.set_pixel_size(32)
            box.append(image)
        
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_hexpand(True)
        
        name = Gtk.Label(label=app_info.get_display_name())
        name.set_halign(Gtk.Align.START)
        name.add_css_class('heading')
        info_box.append(name)
        
        description = app_info.get_description()
        if description:
            desc_label = Gtk.Label(label=description)
            desc_label.set_halign(Gtk.Align.START)
            desc_label.add_css_class('caption')
            desc_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
            info_box.append(desc_label)
        
        box.append(info_box)
        row.set_child(box)
        
        row.app_info = app_info
        row.search_text = (
            f"{app_info.get_display_name() or ''} {app_info.get_description() or ''}"
        ).lower()
        
        return row
    
    def _filter_apps(self, row):
        text = self.search_entry.get_text().lower()
        if not text:
            return True
        return text in row.search_text
    
    def _sort_apps(self, row1, row2):
        name1 = row1.app_info.get_display_name() or ""
        name2 = row2.app_info.get_display_name() or ""
        return name1.lower() > name2.lower()
    
    def _on_search_changed(self, entry):
        self.list_box.invalidate_filter()
    
    def _launch_app(self, row):
        if row and row.app_info:
            try:
                app_info = row.app_info
                if isinstance(app_info, Gio.DesktopAppInfo):
                    app_info.launch()
                else:
                    subprocess.Popen(['flatpak', 'run', app_info.get_id()])
                self.close()
            except Exception as e:
                logger.error(f"Failed to launch application: {e}")
    
    def _on_row_activated(self, list_box, row):
        self._launch_app(row)

class MAGILauncherApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.system.magi.launcher')

    def do_activate(self):
        win = MAGILauncher(self)
        win.present()

def main():
    app = MAGILauncherApplication()
    return app.run(sys.argv)

if __name__ == '__main__':
    sys.exit(main())
