#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib, Gio
import json
import os
import subprocess
import sounddevice as sd
import numpy as np
import threading
import requests
import time
import sys
from collections import deque

# Theme definitions
MAGI_THEMES = {
    "Plain": {
        "panel_bg": "#ffffff",
        "panel_fg": "#000000",
        "button_bg": "#f0f0f0",
        "button_hover": "#e0e0e0",
        "button_active": "#d0d0d0",
        "launcher_bg": "#2c71cc",
        "accent": "#2c71cc",
        "entry_bg": "#ffffff",
        "entry_fg": "#000000",
        "entry_border": "#cccccc",
        "entry_focus": "#2c71cc",
        "selection_bg": "#2c71cc",
        "selection_fg": "#ffffff",
        "link": "#0066cc",
        "error": "#cc0000"
    },
    "Tokyo Night": {
        "panel_bg": "#1a1b26",
        "panel_fg": "#a9b1d6",
        "button_bg": "#24283b",
        "button_hover": "#414868",
        "button_active": "#565f89",
        "launcher_bg": "#bb9af7",
        "accent": "#7aa2f7",
        "entry_bg": "#1f2335",
        "entry_fg": "#c0caf5",
        "entry_border": "#414868",
        "entry_focus": "#7aa2f7",
        "selection_bg": "#7aa2f7",
        "selection_fg": "#1a1b26",
        "link": "#73daca",
        "error": "#f7768e"
    },
    "Forest": {
        "panel_bg": "#2b3328",
        "panel_fg": "#d3c6aa",
        "button_bg": "#3a4637",
        "button_hover": "#4f6146",
        "button_active": "#546c4d",
        "launcher_bg": "#a7c080",
        "accent": "#83c092",
        "entry_bg": "#323d2f",
        "entry_fg": "#d3c6aa",
        "entry_border": "#4f6146",
        "entry_focus": "#a7c080",
        "selection_bg": "#a7c080",
        "selection_fg": "#2b3328",
        "link": "#83c092",
        "error": "#e67e80"
    }
}


class MAGISettings(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.system.magi.settings')
        self.connect('activate', self.on_activate)
        self.connect('shutdown', self.on_shutdown)
        
        # Load config and theme data
        self.config_dir = os.path.expanduser("~/.config/magi")
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.config = self.load_config()
        
        # Initialize theme system
        self.magi_themes = MAGI_THEMES  # From previous code
        self.current_magi_theme = self.config.get('magi_theme', 'Plain')
        self.apply_magi_theme(self.current_magi_theme)
    
    def on_shutdown(self, app):
        """Clean up when the application closes"""
        self.stop_audio_monitor()
    
    def on_activate(self, app):
        """Initialize the main window with proper layout"""
        # Create window with proper titlebar
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_default_size(1024, 768)
        self.win.maximize()
        
        # Create main layout box
        main_layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_layout.set_hexpand(True)
        main_layout.set_vexpand(True)
        
        # Add header bar
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label="MAGI Settings"))
        main_layout.append(header)
        
        # Main content box
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.set_hexpand(True)
        main_box.set_vexpand(True)
        main_layout.append(main_box)
        
        # Create split view for adaptive layout
        self.split_view = Adw.Leaflet()
        self.split_view.set_can_unfold(True)
        self.split_view.set_hexpand(True)
        self.split_view.set_vexpand(True)
        main_box.append(self.split_view)
        
        # Sidebar
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.set_size_request(200, -1)
        
        # Sidebar list
        self.sidebar = Gtk.ListBox(css_classes=['navigation-sidebar'])
        self.sidebar.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sidebar.connect('row-selected', self.on_sidebar_select)
        sidebar_box.append(self.sidebar)
        
        # Content area with full width
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.set_hexpand(True)
        content_box.set_vexpand(True)
        
        # Stack for content pages
        self.stack = Gtk.Stack()
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        content_box.append(self.stack)
        
        # Add content pages
        self.add_page("General", self.create_general_page(), "preferences-desktop-symbolic")
        self.add_page("Audio", self.create_audio_page(), "audio-card-symbolic")
        self.add_page("AI", self.create_ai_page(), "preferences-system-symbolic")
        self.add_page("Appearance", self.create_appearance_page(), "preferences-desktop-theme-symbolic")
        
        # Add boxes to split view
        self.split_view.append(sidebar_box)
        self.split_view.append(content_box)
        
        # Select first item
        self.sidebar.select_row(self.sidebar.get_row_at_index(0))
        
        # Set the main layout as window content
        self.win.set_content(main_layout)
        self.win.present()
    
    def on_sidebar_select(self, listbox, row):
        """Handle sidebar selection"""
        if row:
            page_name = row.get_child().get_last_child().get_text().lower()
            self.stack.set_visible_child_name(page_name)
    
    def add_page(self, title, content, icon_name):
        """Add a page to the stack and sidebar with proper layout"""
        # Create sidebar item
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        row.set_child(box)
        
        icon = Gtk.Image()
        icon.set_from_icon_name(icon_name)
        label = Gtk.Label(label=title)
        label.set_xalign(0)
        
        box.append(icon)
        box.append(label)
        
        self.sidebar.append(row)
        
        # Create full-width container for the content
        content_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        content_container.set_hexpand(True)
        content_container.set_vexpand(True)
        
        # Center the content with appropriate margins
        margin_start = Gtk.Box()
        margin_start.set_hexpand(True)
        margin_end = Gtk.Box()
        margin_end.set_hexpand(True)
        
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        content.set_hexpand(True)  # Make content expand horizontally
        
        # Pack content with flexible margins
        content_container.append(margin_start)
        content_container.append(content)
        content_container.append(margin_end)
        
        # Add to stack
        self.stack.add_named(content_container, title.lower())
    
    def create_general_page(self):
        """Create general settings page with full width layout"""
        clamp = Adw.Clamp()
        
        page = Adw.PreferencesPage()
        page.set_hexpand(True)
        page.set_vexpand(True)
        
        # Panel settings group
        panel_group = Adw.PreferencesGroup(
            title="Panel Settings",
            description="Configure the appearance and behavior of the panels"
        )
        page.add(panel_group)
        
        # Panel height
        height_row = Adw.ActionRow(
            title="Panel Height",
            subtitle="Height of the top and bottom panels in pixels"
        )
        height_spin = Gtk.SpinButton.new_with_range(24, 48, 2)
        height_spin.set_value(self.config.get('panel_height', 28))
        height_spin.set_valign(Gtk.Align.CENTER)
        height_spin.connect('value-changed', self.on_panel_height_changed)
        height_row.add_suffix(height_spin)
        panel_group.add(height_row)
        
        # Workspace settings group
        workspace_group = Adw.PreferencesGroup(
            title="Workspace Settings",
            description="Configure virtual workspace behavior"
        )
        page.add(workspace_group)
        
        # Workspace count
        workspace_row = Adw.ActionRow(
            title="Workspace Count",
            subtitle="Number of virtual desktops available"
        )
        workspace_spin = Gtk.SpinButton.new_with_range(1, 10, 1)
        workspace_spin.set_value(self.config.get('workspace_count', 4))
        workspace_spin.set_valign(Gtk.Align.CENTER)
        workspace_spin.connect('value-changed', self.on_workspace_count_changed)
        workspace_row.add_suffix(workspace_spin)
        workspace_group.add(workspace_row)
        
        # Application settings group
        app_group = Adw.PreferencesGroup(
            title="Application Settings",
            description="Configure default applications and launchers"
        )
        page.add(app_group)
        
        # Terminal command
        terminal_row = Adw.ActionRow(
            title="Terminal Command",
            subtitle="Command used to launch the terminal application"
        )
        terminal_entry = Gtk.Entry()
        terminal_entry.set_text(self.config.get('terminal', 'mate-terminal'))
        terminal_entry.set_valign(Gtk.Align.CENTER)
        terminal_entry.set_hexpand(True)
        terminal_entry.connect('changed', self.on_terminal_changed)
        terminal_row.add_suffix(terminal_entry)
        app_group.add(terminal_row)
        
        # Launcher command
        launcher_row = Adw.ActionRow(
            title="Launcher Command",
            subtitle="Command used to show the application launcher"
        )
        launcher_entry = Gtk.Entry()
        launcher_entry.set_text(self.config.get('launcher', 'mate-panel --run-dialog'))
        launcher_entry.set_valign(Gtk.Align.CENTER)
        launcher_entry.set_hexpand(True)
        launcher_entry.connect('changed', self.on_launcher_changed)
        launcher_row.add_suffix(launcher_entry)
        app_group.add(launcher_row)
        
        # System settings group
        system_group = Adw.PreferencesGroup(
            title="System Settings",
            description="Configure system-wide behavior"
        )
        page.add(system_group)
        
        # Startup delay
        startup_row = Adw.ActionRow(
            title="Startup Delay",
            subtitle="Delay in seconds before starting background services"
        )
        startup_spin = Gtk.SpinButton.new_with_range(0, 10, 1)
        startup_spin.set_value(self.config.get('startup_delay', 2))
        startup_spin.set_valign(Gtk.Align.CENTER)
        startup_spin.connect('value-changed', self.on_startup_delay_changed)
        startup_row.add_suffix(startup_spin)
        system_group.add(startup_row)
        
        clamp.set_child(page)
        return clamp
    
    def on_terminal_changed(self, entry):
        self.config['terminal'] = entry.get_text()
        self.save_config()
    
    def on_launcher_changed(self, entry):
        self.config['launcher'] = entry.get_text()
        self.save_config()
    
    def on_startup_delay_changed(self, spin):
        self.config['startup_delay'] = spin.get_value_as_int()
        self.save_config()
    
    def on_panel_height_changed(self, spin):
        self.config['panel_height'] = spin.get_value_as_int()
        self.save_config()
    
    def on_workspace_count_changed(self, spin):
        self.config['workspace_count'] = spin.get_value_as_int()
        self.save_config()
    
    def create_audio_page(self):
        """Create audio settings page with proper settings loading"""
        page = Adw.PreferencesPage()
        page.set_hexpand(True)
        
        # Microphone settings group
        mic_group = Adw.PreferencesGroup(title="Microphone Settings")
        page.add(mic_group)
        
        # Microphone selection
        mic_row = Adw.ComboRow(
            title="Default Microphone",
            subtitle="Select the microphone to use for voice input"
        )
        
        # Create microphone model
        mic_store = Gtk.StringList()
        self.mic_devices = []  # Store as instance variable for access in handlers
        current_mic = self.config.get('default_microphone')
        current_idx = 0
        
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                mic_store.append(device['name'])
                self.mic_devices.append(i)
                if i == current_mic:
                    current_idx = len(self.mic_devices) - 1
        
        mic_row.set_model(mic_store)
        if current_mic is not None:
            mic_row.set_selected(current_idx)
        
        mic_row.connect('notify::selected', self.on_microphone_changed)
        mic_group.add(mic_row)
        
        # Live visualizer
        visualizer_row = Adw.ActionRow(
            title="Microphone Level",
            subtitle="Live audio input visualization"
        )
        
        # Create visualizer widget
        visualizer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        visualizer_box.set_margin_top(12)
        visualizer_box.set_margin_bottom(12)
        visualizer_box.set_margin_end(12)
        
        self.level_bar = Gtk.LevelBar()
        self.level_bar.set_min_value(0)
        self.level_bar.set_max_value(1)
        self.level_bar.add_offset_value("low", 0.3)
        self.level_bar.add_offset_value("high", 0.8)
        self.level_bar.set_size_request(200, 20)
        
        self.level_label = Gtk.Label(label="Level: -∞ dB")
        
        visualizer_box.append(self.level_bar)
        visualizer_box.append(self.level_label)
        
        visualizer_row.add_suffix(visualizer_box)
        mic_group.add(visualizer_row)
        
        # Sample rate settings
        rate_group = Adw.PreferencesGroup(title="Sample Rate Settings")
        page.add(rate_group)
        
        rate_row = Adw.ComboRow(
            title="Sample Rate",
            subtitle="Audio recording sample rate in Hz"
        )
        
        # Load sample rate from config
        current_rate = self.config.get('sample_rate', 16000)
        
        rate_store = Gtk.StringList()
        self.sample_rates = [8000, 16000, 22050, 44100, 48000]
        
        selected_idx = 0
        for i, rate in enumerate(self.sample_rates):
            rate_store.append(f"{rate} Hz")
            if rate == current_rate:
                selected_idx = i
        
        rate_row.set_model(rate_store)
        rate_row.set_selected(selected_idx)
        rate_row.connect('notify::selected', self.on_sample_rate_changed)
        rate_group.add(rate_row)
        
        # Start audio monitoring with current settings
        self.start_audio_monitor()
        
        return page
    
    def create_ai_page(self):
        """Create AI settings page with dynamic model selection"""
        page = Adw.PreferencesPage()
        page.set_hexpand(True)
        
        # AI Features group
        ai_group = Adw.PreferencesGroup(title="AI Features")
        page.add(ai_group)
        
        # Enable AI toggle
        enable_row = Adw.ActionRow(
            title="Enable AI Features",
            subtitle="Enable or disable AI-powered features"
        )
        enable_switch = Gtk.Switch()
        enable_switch.set_active(self.config.get('enable_ai', True))
        enable_switch.connect('notify::active', self.on_ai_enabled_changed)
        enable_row.add_suffix(enable_switch)
        ai_group.add(enable_row)
        
        # Model settings group
        model_group = Adw.PreferencesGroup(title="Model Settings")
        page.add(model_group)
        
        # Ollama model selection
        model_row = Adw.ComboRow(
            title="Ollama Model",
            subtitle="Select the AI model to use for text generation"
        )
        
        # Create model store
        model_store = Gtk.StringList()
        models = self.get_ollama_models()
        current_model = self.config.get('ollama_model', 'mistral')
        
        selected_idx = 0
        for i, model in enumerate(models):
            model_store.append(model)
            if model == current_model:
                selected_idx = i
        
        model_row.set_model(model_store)
        model_row.set_selected(selected_idx)
        model_row.connect('notify::selected', 
                         lambda r,p: self.on_model_changed(r, models))
        
        model_group.add(model_row)
        
        # Refresh models button
        refresh_row = Adw.ActionRow(
            title="Available Models",
            subtitle="Refresh the list of available Ollama models"
        )
        refresh_button = Gtk.Button(label="Refresh")
        refresh_button.connect('clicked', self.on_refresh_models_clicked)
        refresh_button.add_css_class("flat")
        refresh_row.add_suffix(refresh_button)
        model_group.add(refresh_row)
        
        return page
    
    def create_appearance_page(self):
        """Replace the existing appearance page with new theme system"""
        return self.create_theme_section()


    def apply_magi_theme(self, theme_name):
        """Apply enhanced MAGI-specific theme"""
        if theme_name not in self.magi_themes:
            return
        
        theme = self.magi_themes[theme_name]
        css = f"""
        /* Window and General Styling */
        window, window.background {{
            background-color: {theme['panel_bg']};
            color: {theme['panel_fg']};
        }}
        
        /* Button Styling */
        button {{
            background-color: {theme['button_bg']};
            color: {theme['panel_fg']};
            padding: 6px 10px;
            border-radius: 6px;
            border: 1px solid alpha(currentColor, 0.1);
            box-shadow: 0 1px 2px alpha(black, 0.1);
        }}
        
        button:hover {{
            background-color: {theme['button_hover']};
            transform: translateY(-1px);
            transition: all 200ms ease;
        }}
        
        button:active {{
            background-color: {theme['button_active']};
            transform: translateY(0px);
        }}
        
        .launcher-button {{
            background-color: {theme['launcher_bg']};
            color: {'#ffffff' if theme_name != "Plain" else '#ffffff'};
            font-weight: bold;
            padding: 0 12px;
            border: none;
        }}
        
        .message-button {{
            background-color: transparent;
            color: {theme['panel_fg']};
            padding: 4px;
            border: none;
            box-shadow: none;
        }}
        
        .message-button:hover {{
            background-color: alpha({theme['button_hover']}, 0.5);
        }}
        
        /* Entry/TextField Styling */
        entry {{
            background-color: {theme['entry_bg']};
            color: {theme['entry_fg']};
            border: 1px solid {theme['entry_border']};
            border-radius: 6px;
            padding: 8px;
            box-shadow: inset 0 1px 2px alpha(black, 0.1);
            caret-color: {theme['entry_fg']};
        }}
        
        entry:focus {{
            border-color: {theme['entry_focus']};
            box-shadow: 0 0 0 2px alpha({theme['entry_focus']}, 0.3);
        }}
        
        /* Selection Styling */
        *:selected {{
            background-color: {theme['selection_bg']};
            color: {theme['selection_fg']};
        }}
        
        /* Message Styling */
        .user-message {{
            background-color: alpha({theme['button_bg']}, 0.8);
            color: {theme['panel_fg']};
            padding: 12px;
            border-radius: 12px;
            border: 1px solid alpha(currentColor, 0.1);
            box-shadow: 0 2px 4px alpha(black, 0.1);
            margin: 4px 8px;
        }}
        
        .assistant-message {{
            background-color: alpha({theme['accent']}, 0.1);
            color: {theme['panel_fg']};
            padding: 12px;
            border-radius: 12px;
            border: 1px solid alpha({theme['accent']}, 0.2);
            box-shadow: 0 2px 4px alpha(black, 0.1);
            margin: 4px 8px;
        }}
        
        .code-block {{
            background-color: {theme['entry_bg']};
            color: {theme['entry_fg']};
            padding: 12px;
            border-radius: 8px;
            font-family: monospace;
            border: 1px solid {theme['entry_border']};
        }}
        
        /* Link Styling */
        link {{
            color: {theme['link']};
        }}
        
        link:hover {{
            text-decoration: underline;
        }}
        
        /* Error and Warning Styling */
        .error {{
            color: {theme['error']};
        }}
        
        /* Scrollbar Styling */
        scrollbar {{
            background-color: transparent;
        }}
        
        scrollbar slider {{
            background-color: alpha({theme['panel_fg']}, 0.2);
            border-radius: 999px;
            min-width: 8px;
            min-height: 8px;
        }}
        
        scrollbar slider:hover {{
            background-color: alpha({theme['panel_fg']}, 0.4);
        }}
        
        scrollbar slider:active {{
            background-color: alpha({theme['panel_fg']}, 0.6);
        }}
        """
        
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    def create_theme_section(self):
        """Create theme selection UI with three sections"""
        page = Adw.PreferencesPage()
        
        # GTK3 themes
        gtk3_group = Adw.PreferencesGroup(
            title="GTK3 Theme",
            description="Theme for legacy applications"
        )
        gtk3_row = Adw.ComboRow(
            title="GTK3 Theme",
            model=Gtk.StringList.new(self.get_gtk3_themes())
        )
        # Set current GTK3 theme
        current_gtk3 = self.config.get('gtk3_theme', 'Default')
        gtk3_themes = self.get_gtk3_themes()
        if current_gtk3 in gtk3_themes:
            gtk3_row.set_selected(gtk3_themes.index(current_gtk3))
        gtk3_row.connect('notify::selected', self.on_gtk3_theme_changed)
        gtk3_group.add(gtk3_row)
        
        # GTK4 color scheme
        gtk4_group = Adw.PreferencesGroup(
            title="GTK4 Style",
            description="Color scheme for modern applications"
        )
        gtk4_row = Adw.ComboRow(
            title="Color Scheme",
            model=Gtk.StringList.new(["System Default", "Prefer Dark", "Prefer Light", "Force Dark"])
        )
        gtk4_row.set_selected(self.config.get('gtk4_scheme', 0))
        gtk4_row.connect('notify::selected', self.on_gtk4_theme_changed)
        gtk4_group.add(gtk4_row)
        
        # MAGI theme
        magi_group = Adw.PreferencesGroup(
            title="MAGI Theme",
            description="Theme for MAGI panels and menus"
        )
        magi_row = Adw.ComboRow(
            title="MAGI Theme",
            model=Gtk.StringList.new(list(self.magi_themes.keys()))
        )
        current_theme_idx = list(self.magi_themes.keys()).index(self.current_magi_theme)
        magi_row.set_selected(current_theme_idx)
        magi_row.connect('notify::selected', self.on_magi_theme_changed)
        magi_group.add(magi_row)
        
        page.add(gtk3_group)
        page.add(gtk4_group)
        page.add(magi_group)
        
        return page
    
    def get_gtk3_themes(self):
        """Get list of installed GTK3 themes"""
        themes = set(["Default"])
        theme_paths = [
            os.path.expanduser('~/.themes'),
            os.path.expanduser('~/.local/share/themes'),
            '/usr/share/themes'
        ]
        
        for path in theme_paths:
            if os.path.exists(path):
                for theme in os.listdir(path):
                    theme_dir = os.path.join(path, theme)
                    if os.path.isdir(theme_dir):
                        # Check for GTK3 theme files
                        if (os.path.exists(os.path.join(theme_dir, 'gtk-3.0', 'gtk.css')) or
                            os.path.exists(os.path.join(theme_dir, 'gtk-3.0', 'gtk-main.css'))):
                            themes.add(theme)
        
        return sorted(list(themes))
    
    def on_gtk3_theme_changed(self, row, _):
        """Handle GTK3 theme changes safely"""
        selected = row.get_selected()
        themes = self.get_gtk3_themes()
        if 0 <= selected < len(themes):
            theme_name = themes[selected]
            
            # Update GTK settings
            settings = Gtk.Settings.get_default()
            settings.set_property('gtk-theme-name', theme_name)
            
            # Update system settings safely
            try:
                # Update MATE interface theme
                subprocess.run(['gsettings', 'set', 'org.mate.interface', 'gtk-theme', theme_name],
                            check=False)
                
                # Update window manager theme
                subprocess.run(['gsettings', 'set', 'org.mate.Marco.general', 'theme', theme_name],
                            check=False)
                
                # Update through dconf for persistence
                subprocess.run(['dconf', 'write', '/org/mate/desktop/interface/gtk-theme',
                            f"'{theme_name}'"], check=False)
                
            except Exception as e:
                print(f"Error updating GTK3 theme: {e}")
            
            self.config['gtk3_theme'] = theme_name
            self.save_config()
            
            # Show notification
            if hasattr(self, 'toast_overlay'):
                toast = Adw.Toast.new(f"GTK3 theme changed to {theme_name}")
                toast.set_timeout(2)
                self.toast_overlay.add_toast(toast)

            # Suggest logout for complete theme application
            dialog = Adw.MessageDialog.new(
                self,
                "Theme Changed",
                "Some applications may need to be restarted or require a logout to fully apply the theme."
            )
            dialog.add_response("ok", "OK")
            dialog.present()
    
    def on_gtk4_theme_changed(self, row, _):
        """Handle GTK4 color scheme changes"""
        schemes = [
            Adw.ColorScheme.DEFAULT,
            Adw.ColorScheme.PREFER_DARK,
            Adw.ColorScheme.PREFER_LIGHT,
            Adw.ColorScheme.FORCE_DARK
        ]
        selected = row.get_selected()
        if 0 <= selected < len(schemes):
            style_manager = Adw.StyleManager.get_default()
            style_manager.set_color_scheme(schemes[selected])
            self.config['gtk4_scheme'] = selected
            self.save_config()
    
    def on_magi_theme_changed(self, row, _):
        """Handle MAGI theme changes"""
        selected = row.get_selected()
        themes = list(self.magi_themes.keys())
        if 0 <= selected < len(themes):
            theme_name = themes[selected]
            self.current_magi_theme = theme_name
            self.config['magi_theme'] = theme_name
            self.save_config()
            self.apply_magi_theme(theme_name)
    
    def _show_window_after_theme_change(self):
        """Helper to show window after brief delay to allow theme to apply"""
        self.win.show()
        return False

    def get_available_themes(self):
        """Get list of installed GTK themes with validation"""
        themes = set()
        theme_paths = [
            os.path.expanduser('~/.themes'),
            os.path.expanduser('~/.local/share/themes'),
            '/usr/share/themes'
        ]
        
        for path in theme_paths:
            if os.path.exists(path):
                for theme in os.listdir(path):
                    theme_dir = os.path.join(path, theme)
                    if os.path.isdir(theme_dir):
                        # Check for theme files in order of preference
                        if (os.path.exists(os.path.join(theme_dir, 'gtk-4.0', 'gtk.css')) or
                            os.path.exists(os.path.join(theme_dir, 'gtk-3.0', 'gtk.css')) or
                            os.path.exists(os.path.join(theme_dir, 'gtk-3.0', 'gtk-main.css')) or
                            os.path.exists(os.path.join(theme_dir, 'gtk-2.0', 'gtkrc'))):
                            themes.add(theme)
        
        return sorted(list(themes))
    
    def start_audio_monitor(self):
        """Start monitoring audio input level"""
        self.stop_audio_monitor()  # Ensure any existing monitor is stopped
        
        device_id = self.config.get('default_microphone')
        sample_rate = self.config.get('sample_rate', 16000)
        
        if device_id is None:
            self.level_label.set_text("No microphone selected")
            return
        
        self.monitor_running = True
        
        def audio_callback(indata, frames, time, status):
            if status:
                print(status)
            if self.monitor_running:
                # Calculate RMS level with proper scaling
                rms = np.sqrt(np.mean(indata**2))
                # Convert to dB with proper range
                db = max(-60, 20 * np.log10(rms + 1e-10))
                # Normalize to 0-1 range for level bar
                normalized = (db + 60) / 60
                
                GLib.idle_add(self.update_level_indicator, normalized, db)
        
        try:
            self.monitor_stream = sd.InputStream(
                device=device_id,
                channels=1,
                callback=audio_callback,
                blocksize=1024,
                samplerate=sample_rate,
                dtype=np.float32
            )
            self.monitor_stream.start()
        except Exception as e:
            print(f"Error starting audio monitor: {e}")
            self.level_label.set_text(f"Error: {str(e)}")
    
    
    def stop_audio_monitor(self):
        """Stop the audio monitor"""
        self.monitor_running = False
        if hasattr(self, 'monitor_stream'):
            try:
                self.monitor_stream.stop()
                self.monitor_stream.close()
                self.monitor_stream = None
            except Exception as e:
                print(f"Error stopping audio monitor: {e}")
    
    def apply_theme(self, theme_name):
        """Apply theme and save to config"""
        settings = Gtk.Settings.get_default()
        if theme_name == 'Default':
            # Reset to system theme
            settings.set_property('gtk-theme-name', None)
        else:
            settings.set_property('gtk-theme-name', theme_name)
        
        self.config['gtk_theme'] = theme_name
        self.save_config()
    
    def update_level_indicator(self, level, db):
        """Update the level bar and label with proper formatting"""
        if hasattr(self, 'level_bar'):
            self.level_bar.set_value(level)
            if db < -60:
                self.level_label.set_text("Level: -60 dB")
            else:
                self.level_label.set_text(f"Level: {db:.1f} dB")
        return False
    
    def stop_audio_monitor(self):
        """Stop the audio monitor"""
        self.monitor_running = False
        if hasattr(self, 'monitor_stream'):
            try:
                self.monitor_stream.stop()
                self.monitor_stream.close()
            except Exception as e:
                print(f"Error stopping audio monitor: {e}")
    
    def get_ollama_models(self):
        """Get list of installed Ollama models"""
        try:
            result = subprocess.run(['ollama', 'list'], 
                                  capture_output=True, 
                                  text=True, 
                                  check=True)
            
            models = []
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # Skip header row
                for line in lines[1:]:
                    # Split on whitespace and get first column (name)
                    parts = line.split()
                    if parts:
                        model_name = parts[0]
                        # Remove :latest if present
                        if model_name.endswith(':latest'):
                            model_name = model_name[:-7]
                        models.append(model_name)
            
            return sorted(models)
        except subprocess.CalledProcessError as e:
            print(f"Error getting Ollama models: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error getting Ollama models: {e}")
            return []
    
    def on_choose_background(self, button):
        """Handle background image selection"""
        dialog = Gtk.FileChooserDialog(
            title="Choose Background Image",
            action=Gtk.FileChooserAction.OPEN,
        )
        
        dialog.add_buttons(
            "_Cancel",
            Gtk.ResponseType.CANCEL,
            "_Open",
            Gtk.ResponseType.ACCEPT,
        )
        
        dialog.set_transient_for(self.win)
        dialog.set_modal(True)
        
        filter_images = Gtk.FileFilter()
        filter_images.set_name("Image files")
        filter_images.add_mime_type("image/jpeg")
        filter_images.add_mime_type("image/png")
        dialog.add_filter(filter_images)
        
        dialog.connect('response', self.on_background_dialog_response)
        dialog.show()
    
    def on_background_dialog_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                path = file.get_path()
                self.config['background'] = path
                self.save_config()
                # Update background
                try:
                    subprocess.run(['feh', '--bg-fill', path])
                except Exception as e:
                    print(f"Error setting background: {e}")
        
        dialog.destroy()
    
    def on_panel_height_changed(self, spin):
        self.config['panel_height'] = spin.get_value_as_int()
        self.save_config()
    
    def on_workspace_count_changed(self, spin):
        self.config['workspace_count'] = spin.get_value_as_int()
        self.save_config()
    
    def on_terminal_changed(self, entry):
        self.config['terminal'] = entry.get_text()
        self.save_config()
    
    def on_microphone_changed(self, row, _):
        """Handle microphone selection change"""
        selected = row.get_selected()
        if 0 <= selected < len(self.mic_devices):
            device_id = self.mic_devices[selected]
            self.config['default_microphone'] = device_id
            self.save_config()
            
            # Restart audio monitoring with new device
            self.stop_audio_monitor()
            self.start_audio_monitor()
    
    def on_test_microphone(self, button):
        """Test selected microphone with improved error handling and feedback"""
        device_id = self.config.get('default_microphone')
        if device_id is None:
            dialog = Adw.MessageDialog.new(
                self.win,
                "No microphone selected",
                "Please select a microphone first."
            )
            dialog.add_response("ok", "OK")
            dialog.present()
            return
        
        # Get device info first to check capabilities
        try:
            device_info = sd.query_devices(device_id)
            if device_info['max_input_channels'] < 1:
                raise ValueError("Selected device has no input channels")
            
            # Get supported sample rates
            supported_rates = []
            test_rates = [8000, 16000, 22050, 44100, 48000]
            for rate in test_rates:
                try:
                    sd.check_input_settings(
                        device=device_id,
                        channels=1,
                        dtype=np.float32,
                        samplerate=rate
                    )
                    supported_rates.append(rate)
                except Exception:
                    continue
            
            if not supported_rates:
                raise ValueError("No supported sample rates found for this device")
            
            # Use the closest supported rate to our configured rate
            configured_rate = self.config.get('sample_rate', 16000)
            sample_rate = min(supported_rates, key=lambda x: abs(x - configured_rate))
            
            # Create recording progress dialog
            progress_dialog = Adw.MessageDialog.new(
                self.win,
                "Testing Microphone",
                "Recording in progress..."
            )
            progress_dialog.add_response("cancel", "Cancel")
            
            # Add progress bar
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            content.set_margin_top(12)
            content.set_margin_bottom(12)
            content.set_margin_start(12)
            content.set_margin_end(12)
            
            progress_bar = Gtk.ProgressBar()
            progress_bar.set_fraction(0.0)
            content.append(progress_bar)
            
            level_label = Gtk.Label(label="Level: 0 dB")
            content.append(level_label)
            
            progress_dialog.set_extra_child(content)
            
            # Variables for recording
            duration = 3  # seconds
            recording_data = []
            start_time = None
            is_recording = True
            
            def audio_callback(indata, frames, time, status):
                if status:
                    print(status)
                if is_recording:
                    recording_data.append(indata.copy())
                    # Update level meter
                    level = 20 * np.log10(np.max(np.abs(indata)) + 1e-10)
                    GLib.idle_add(level_label.set_text, f"Level: {level:.1f} dB")
            
            def update_progress():
                if not is_recording:
                    return False
                
                nonlocal start_time
                if start_time is None:
                    start_time = time.time()
                
                elapsed = time.time() - start_time
                if elapsed >= duration:
                    stream.stop()
                    progress_dialog.close()
                    return False
                
                progress_bar.set_fraction(elapsed / duration)
                return True
            
            # Start recording
            try:
                stream = sd.InputStream(
                    device=device_id,
                    channels=1,
                    samplerate=sample_rate,
                    callback=audio_callback,
                    dtype=np.float32
                )
                
                stream.start()
                GLib.timeout_add(100, update_progress)
                progress_dialog.present()
                
                def on_dialog_response(dialog, response):
                    nonlocal is_recording
                    is_recording = False
                    stream.stop()
                    stream.close()
                
                progress_dialog.connect('response', on_dialog_response)
                
                # When recording is done, play it back
                def on_recording_complete():
                    if not recording_data:
                        return
                    
                    # Combine all recorded chunks
                    recorded_audio = np.concatenate(recording_data)
                    
                    # Play the recording back
                    playback_dialog = Adw.MessageDialog.new(
                        self.win,
                        "Playback",
                        "Playing back recorded audio..."
                    )
                    playback_dialog.present()
                    
                    try:
                        sd.play(recorded_audio, sample_rate)
                        sd.wait()
                    except Exception as e:
                        print(f"Playback error: {e}")
                    finally:
                        playback_dialog.close()
                
                GLib.timeout_add_seconds(duration, on_recording_complete)
                
            except Exception as e:
                error_msg = str(e)
                if "Invalid sample rate" in error_msg:
                    error_msg = f"Sample rate {sample_rate}Hz not supported by device. Supported rates: {supported_rates}"
                elif "Invalid number of channels" in error_msg:
                    error_msg = "Device does not support mono recording"
                
                error_dialog = Adw.MessageDialog.new(
                    self.win,
                    "Recording Failed",
                    error_msg
                )
                error_dialog.add_response("ok", "OK")
                error_dialog.present()
                return
            
        except Exception as e:
            error_msg = str(e)
            if "Invalid device" in error_msg:
                error_msg = "Selected device is no longer available"
            
            error_dialog = Adw.MessageDialog.new(
                self.win,
                "Device Error",
                error_msg
            )
            error_dialog.add_response("ok", "OK")
            error_dialog.present()
    
    def on_sample_rate_changed(self, row, _):
        """Handle sample rate selection change"""
        selected = row.get_selected()
        if 0 <= selected < len(self.sample_rates):
            rate = self.sample_rates[selected]
            self.config['sample_rate'] = rate
            self.save_config()
            
            # Restart audio monitoring with new sample rate
            self.stop_audio_monitor()
            self.start_audio_monitor()
    
    def on_refresh_models_clicked(self, button):
        """Refresh the Ollama models list"""
        models = self.get_ollama_models()
        model_row = self.find_model_row()
        if model_row:
            # Update model store
            model_store = Gtk.StringList()
            current_model = self.config.get('ollama_model', 'mistral')
            
            selected_idx = 0
            for i, model in enumerate(models):
                model_store.append(model)
                if model == current_model:
                    selected_idx = i
            
            model_row.set_model(model_store)
            model_row.set_selected(selected_idx)
    
    def find_model_row(self):
        """Find the Ollama model ComboRow in the UI"""
        stack = self.stack
        ai_page = stack.get_child_by_name('ai')
        if ai_page:
            for group in ai_page:
                if isinstance(group, Adw.PreferencesGroup):
                    for row in group:
                        if isinstance(row, Adw.ComboRow) and row.get_title() == "Ollama Model":
                            return row
        return None
    
    def on_model_changed(self, row, models):
        """Handle Ollama model selection"""
        selected = row.get_selected()
        if 0 <= selected < len(models):
            self.config['ollama_model'] = models[selected]
            self.save_config()
    
    def on_endpoint_changed(self, entry):
        self.config['whisper_endpoint'] = entry.get_text()
        self.save_config()
    
    def on_ai_enabled_changed(self, switch, _):
        self.config['enable_ai'] = switch.get_active()
        self.save_config()
    
    def on_effects_enabled_changed(self, switch, _):
        self.config['enable_effects'] = switch.get_active()
        self.save_config()
    
    def on_theme_changed(self, row, _):
        """Handle theme selection for both GTK3 and GTK4/libadwaita apps"""
        selected = row.get_selected()
        theme_name = "Default"
        
        if selected > 0:
            theme_name = self.themes[selected - 1]
        
        # Detect if dark theme
        is_dark = any(x in theme_name.lower() for x in ['dark', 'noir', 'nacht', 'black'])
        
        # Set GTK4/libadwaita color scheme
        style_manager = Adw.StyleManager.get_default()
        if is_dark:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        
        # Handle GTK3 apps
        settings = Gtk.Settings.get_default()
        if theme_name == "Default":
            settings.reset_property('gtk-theme-name')
            try:
                interface_settings = Gio.Settings.new('org.gnome.desktop.interface')
                interface_settings.reset('gtk-theme')
            except:
                pass
        else:
            settings.set_property('gtk-theme-name', theme_name)
            try:
                interface_settings = Gio.Settings.new('org.gnome.desktop.interface')
                interface_settings.set_string('gtk-theme', theme_name)
            except:
                pass
                
            # Update window manager theme
            try:
                marco_settings = Gio.Settings.new('org.mate.Marco.general')
                marco_settings.set_string('theme', theme_name)
            except:
                pass
        
        # Update dconf
        try:
            subprocess.run(['dconf', 'write', '/org/gnome/desktop/interface/gtk-theme',
                        f"'{theme_name}'"], check=False)
            subprocess.run(['dconf', 'write', '/org/gnome/desktop/interface/color-scheme',
                        "'prefer-dark'" if is_dark else "'default'"], check=False)
        except Exception as e:
            print(f"Warning: Could not update dconf settings: {e}")
        
        # Save to config
        self.config['gtk_theme'] = theme_name
        self.config['prefer_dark'] = is_dark
        self.save_config()
        
        # Force redraw
        def apply_theme():
            self.win.queue_draw()
            scheme = "dark" if is_dark else "light"
            if hasattr(self, 'toast_overlay'):
                toast = Adw.Toast.new(f"Theme changed to {theme_name} ({scheme})")
                toast.set_timeout(2)
                self.toast_overlay.add_toast(toast)
            return False
        
        GLib.timeout_add(100, apply_theme)
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(os.path.join(self.config_dir, "config.json"), 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def load_config(self):
        """Load configuration from file with defaults"""
        config_path = os.path.join(self.config_dir, "config.json")
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                # Ensure all required fields exist
                default_config = {
                    'panel_height': 28,
                    'workspace_count': 4,
                    'enable_effects': True,
                    'enable_ai': True,
                    'terminal': 'mate-terminal',
                    'launcher': 'mate-panel --run-dialog',
                    'background': '/usr/share/magi/backgrounds/default.png',
                    'ollama_model': 'mistral',
                    'whisper_endpoint': 'http://localhost:5000/transcribe',
                    'sample_rate': 16000,
                    'default_microphone': None,
                    'gtk3_theme': 'Default',
                    'gtk4_scheme': 0,
                    'magi_theme': 'Plain'
                }
                
                # Update config with any missing defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                
                return config
                
        except (FileNotFoundError, json.JSONDecodeError):
            # Create default config
            default_config = {
                'panel_height': 28,
                'workspace_count': 4,
                'enable_effects': True,
                'enable_ai': True,
                'terminal': 'mate-terminal',
                'launcher': 'mate-panel --run-dialog',
                'background': '/usr/share/magi/backgrounds/default.png',
                'ollama_model': 'mistral',
                'whisper_endpoint': 'http://localhost:5000/transcribe',
                'sample_rate': 16000,
                'default_microphone': None,
                'gtk3_theme': 'Default',
                'gtk4_scheme': 0,
                'magi_theme': 'Plain'
            }
            
            # Ensure config directory exists
            os.makedirs(self.config_dir, exist_ok=True)
            
            # Save default config
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=4)
            
            return default_config

def main():
    app = MAGISettings()
    return app.run(None)

if __name__ == "__main__":
    main()
