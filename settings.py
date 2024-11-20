#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib, Gdk
import json
import os
import sounddevice as sd
import subprocess
import numpy as np

class MAGISettings(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.system.magi.settings')
        self.connect('activate', self.on_activate)
        self.connect('shutdown', self.on_shutdown)
        
        # Load config
        self.config_dir = os.path.expanduser("~/.config/magi")
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.config = self.load_config()
    
    def on_shutdown(self, app):
        """Clean up when the application closes"""
        self.stop_audio_monitor()
    
    def on_activate(self, app):
        # Create window
        self.win = Adw.ApplicationWindow(application=app)
        self.win.set_default_size(800, 600)
        self.win.set_title("MAGI Settings")
        
        # Create main box that expands to fill window
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.set_hexpand(True)
        main_box.set_vexpand(True)
        self.win.set_content(main_box)
        
        # Create leaflet that expands to fill box
        leaflet = Adw.Leaflet()
        leaflet.set_can_unfold(True)
        leaflet.set_hexpand(True)
        leaflet.set_vexpand(True)
        main_box.append(leaflet)
        
        # Create sidebar box
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.set_size_request(200, -1)
        
        # Sidebar header
        header = Adw.HeaderBar()
        sidebar_box.append(header)
        
        # Sidebar list
        sidebar = Gtk.ListBox(css_classes=['navigation-sidebar'])
        sidebar.set_selection_mode(Gtk.SelectionMode.SINGLE)
        sidebar.connect('row-selected', self.on_sidebar_select)
        sidebar_box.append(sidebar)
        
        # Content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Content header
        content_header = Adw.HeaderBar()
        content_box.append(content_header)
        
        # Content stack
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        content_box.append(self.stack)
        
        # Add pages
        self.add_page("General", self.create_general_page(), "preferences-desktop-symbolic", sidebar)
        self.add_page("Audio", self.create_audio_page(), "audio-card-symbolic", sidebar)
        self.add_page("AI", self.create_ai_page(), "preferences-system-symbolic", sidebar)
        self.add_page("Appearance", self.create_appearance_page(), "preferences-desktop-theme-symbolic", sidebar)
        
        # Add boxes to leaflet
        leaflet.append(sidebar_box)
        leaflet.append(content_box)
        
        # Set folded properties
        sidebar_box.set_hexpand(False)
        content_box.set_hexpand(True)
        
        # Select first item
        sidebar.select_row(sidebar.get_row_at_index(0))
        
        self.win.present()
    
    def on_sidebar_select(self, listbox, row):
        """Handle sidebar selection"""
        if row:
            page_name = row.get_child().get_last_child().get_text().lower()
            self.stack.set_visible_child_name(page_name)
    
    def add_page(self, title, content, icon_name, sidebar):
        """Add a page to the stack and an item to the sidebar"""
        # Create sidebar item with proper layout
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        row.set_child(box)
        
        # Create icon using new GTK4 method
        icon = Gtk.Image()
        icon.set_from_icon_name(icon_name)
        icon.set_icon_size(Gtk.IconSize.NORMAL)
        
        label = Gtk.Label(label=title)
        label.set_xalign(0)
        
        box.append(icon)
        box.append(label)
        
        sidebar.append(row)
        
        # Add page to stack with proper margins
        self.stack.add_named(content, title.lower())
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
    
    def create_general_page(self):
        """Create general settings page"""
        page = Adw.PreferencesPage()
        
        # Panel settings group
        panel_group = Adw.PreferencesGroup(title="Panel Settings")
        page.add(panel_group)
        
        # Panel height
        height_row = Adw.ActionRow(
            title="Panel Height",
            subtitle="Height of the top and bottom panels in pixels"
        )
        height_spin = Gtk.SpinButton.new_with_range(24, 48, 2)
        height_spin.set_value(self.config.get('panel_height', 28))
        height_spin.connect('value-changed', self.on_panel_height_changed)
        height_row.add_suffix(height_spin)
        panel_group.add(height_row)
        
        # Workspace settings group
        workspace_group = Adw.PreferencesGroup(title="Workspace Settings")
        page.add(workspace_group)
        
        # Workspace count
        workspace_row = Adw.ActionRow(
            title="Workspace Count",
            subtitle="Number of virtual desktops"
        )
        workspace_spin = Gtk.SpinButton.new_with_range(1, 10, 1)
        workspace_spin.set_value(self.config.get('workspace_count', 4))
        workspace_spin.connect('value-changed', self.on_workspace_count_changed)
        workspace_row.add_suffix(workspace_spin)
        workspace_group.add(workspace_row)
        
        # Terminal settings group
        terminal_group = Adw.PreferencesGroup(title="Terminal Settings")
        page.add(terminal_group)
        
        # Terminal command
        terminal_row = Adw.ActionRow(
            title="Terminal Command",
            subtitle="Command used to launch the terminal"
        )
        terminal_entry = Gtk.Entry()
        terminal_entry.set_text(self.config.get('terminal', 'mate-terminal'))
        terminal_entry.connect('changed', self.on_terminal_changed)
        terminal_row.add_suffix(terminal_entry)
        terminal_group.add(terminal_row)
        
        return page
    
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
        """Create appearance settings page"""
        page = Adw.PreferencesPage()
        page.set_hexpand(True)  # Make page expand horizontally
        
        # Theme settings group
        theme_group = Adw.PreferencesGroup(title="Theme Settings")
        page.add(theme_group)
        
        # Theme selection
        theme_row = Adw.ComboRow(
            title="Application Theme",
            subtitle="Select the GTK theme to use"
        )
        
        # Get available themes
        theme_store = Gtk.StringList()
        themes = self.get_available_themes()
        current_theme = self.config.get('gtk_theme', 'Default')
        
        theme_store.append("Default (System)")
        selected_idx = 0
        
        for i, theme in enumerate(themes, 1):
            theme_store.append(theme)
            if theme == current_theme:
                selected_idx = i
        
        theme_row.set_model(theme_store)
        theme_row.set_selected(selected_idx)
        
        theme_row.connect('notify::selected', 
                         lambda r,p: self.on_theme_changed(r, ['Default'] + themes))
        theme_group.add(theme_row)
        
        return page
    
    def get_available_themes(self):
        """Get list of installed GTK themes"""
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
                        # Check for any GTK theme files
                        if any(os.path.exists(os.path.join(theme_dir, f'gtk-{ver}'))
                              for ver in ['2.0', '3.0', '4.0']):
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
    
    def on_theme_changed(self, row, themes):
        theme = themes[row.get_selected()]
        self.config['gtk_theme'] = theme
        self.save_config()
        
        # Apply theme
        if theme == 'Default':
            Gtk.Settings.get_default().set_property(
                'gtk-theme-name', 
                Adw.StyleManager.get_default().get_system_supports_color_schemes()
            )
        else:
            Gtk.Settings.get_default().set_property('gtk-theme-name', theme)
    
    def save_config(self, config=None):
        """Save configuration to file"""
        if config is None:
            config = self.config
        os.makedirs(self.config_dir, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=4)
    
    def load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                # Ensure sample rate has a valid value
                if 'sample_rate' not in config:
                    config['sample_rate'] = 16000
                return config
        except FileNotFoundError:
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
                'gtk_theme': 'Default'
            }
            self.save_config(default_config)
            return default_config

def main():
    app = MAGISettings()
    return app.run(None)

if __name__ == "__main__":
    main()
