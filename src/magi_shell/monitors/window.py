# src/magi_shell/monitors/window.py
"""
Model manager main window implementation.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GLib, Adw
import os
import json
import threading
import subprocess
import time

from ..models.whisper import WhisperManager, update_whisper_script
from ..models.ollama import OllamaManager
from ..models.voice import BaritoneWrangler
from ..monitors.status import ServiceStatusDisplay
from ..monitors.gpu import GPUMonitor
from ..utils.paths import get_config_path
from ..core.theme import ThemeManager

class ModelManager(Gtk.ApplicationWindow):
    """Main window for model management interface."""
    
    def __init__(self, app):
        super().__init__(application=app)
        
        self.set_decorated(False)
        self.connect('realize', self._on_realize)
        
        # Load configuration
        self._load_config()
        
        # Initialize managers
        self.theme_manager = ThemeManager()
        self.theme_manager.register_window(self)
        
        self.whisper_manager = WhisperManager()
        self.ollama_manager = OllamaManager(self.config)
        self.voice_manager = BaritoneWrangler()
        self.gpu_monitor = GPUMonitor()
        
        # Set up UI
        self._setup_window()
        
        # Initialize status
        self.verification_in_progress = False
        
        # Start monitoring
        GLib.timeout_add(3000, self._update_gpu_status)
        
        # Start services
        try:
            update_whisper_script()
            self._start_whisper()
            self._check_ollama()
            self._start_voice()
        except Exception as e:
            print(f"Service startup error: {e}")
        
        # Schedule initial check
        GLib.timeout_add(5000, self._initial_status_check)
    
    def _load_config(self):
        """Load configuration from file."""
        config_file = get_config_path() / "config.json"
        try:
            with open(config_file) as f:
                self.config = json.load(f)
        except Exception:
            self.config = {'ollama_model': 'mistral'}
    
    def _setup_window(self):
        """Set up the main window layout."""
        self.set_title("MAGI Model Status")
        self.set_default_size(400, 200)
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        
        # Check button
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_halign(Gtk.Align.END)
        self.check_button = Gtk.Button(label="Check Status")
        self.check_button.connect('clicked', lambda _: self._check_status())
        button_box.append(self.check_button)
        main_box.append(button_box)
        
        # Service status displays
        self.whisper_display = ServiceStatusDisplay("THE WHISPER")
        main_box.append(self.whisper_display.box)
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        self.ollama_display = ServiceStatusDisplay(
            f"THE ORACLE ({self.config.get('ollama_model', 'mistral').upper()})"
        )
        main_box.append(self.ollama_display.box)
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        self.voice_display = ServiceStatusDisplay("THE BARITONE")
        main_box.append(self.voice_display.box)
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        # GPU status
        self.gpu_label = Gtk.Label()
        self.gpu_label.set_xalign(0)
        main_box.append(self.gpu_label)
        
        # Last check time
        self.last_check_label = Gtk.Label()
        self.last_check_label.set_xalign(1)
        main_box.append(self.last_check_label)
        
        self.set_child(main_box)
    
    def _on_realize(self, widget):
        """Handle window realization."""
        def setup():
            try:
                window_id = subprocess.check_output(
                    ['xdotool', 'search', '--name', '^MAGI Model Status$']
                ).decode().strip()
                
                if window_id:
                    stage_num = window_id.split('\n')[0]
                    subprocess.run(['wmctrl', '-i', '-r', stage_num, '-b', 'add,below,sticky'])
                    subprocess.run(['wmctrl', '-i', '-r', stage_num, '-t', '-1'])
            except Exception as e:
                print(f"Window setup error: {e}")
                GLib.timeout_add(100, setup)
            return False
        
        GLib.timeout_add(100, setup)
    
    def _start_whisper(self):
        """Start Whisper service."""
        self.whisper_manager.start(
            lambda status, progress, message: 
            GLib.idle_add(self.whisper_display.update_status, status, progress, message)
        )
    
    def _check_ollama(self):
        """Check Ollama service status."""
        self.ollama_manager.check_status(
            lambda status, progress, message:
            GLib.idle_add(self.ollama_display.update_status, status, progress, message)
        )
    
    def _start_voice(self):
        """Start voice service."""
        success, message = self.voice_manager.summon_the_bass_section()
        if success:
            self.voice_display.update_status("Running", 100, "Voice ready!")
        else:
            self.voice_display.update_status("Error", 0, message)
    
    def _check_status(self):
        """Check status of all services."""
        if self.verification_in_progress:
            return
        
        self.verification_in_progress = True
        self.check_button.set_sensitive(False)
        
        def check():
            # Check Whisper
            self.whisper_manager.check_status(
                lambda status, progress, message:
                GLib.idle_add(self.whisper_display.update_status, status, progress, message)
            )
            
            # Check Ollama
            self.ollama_manager.check_status(
                lambda status, progress, message:
                GLib.idle_add(self.ollama_display.update_status, status, progress, message)
            )
            
            # Check Voice
            if self.voice_manager.still_breathing():
                GLib.idle_add(self.voice_display.update_status, "Running", 100, 
                            "Voice projection optimal!")
            else:
                success, message = self.voice_manager.summon_the_bass_section()
                if success:
                    GLib.idle_add(self.voice_display.update_status, "Running", 100,
                                "Voice ready to rumble!")
                else:
                    GLib.idle_add(self.voice_display.update_status, "Error", 0, message)
            
            # Update check time
            check_time = time.strftime("%H:%M:%S")
            GLib.idle_add(self.last_check_label.set_text, 
                         f"Last check: {check_time}")
            
            # Reset button
            GLib.idle_add(self._reset_check_button)
        
        threading.Thread(target=check, daemon=True).start()
    
    def _reset_check_button(self):
        """Reset check button state."""
        self.verification_in_progress = False
        self.check_button.set_sensitive(True)
    
    def _update_gpu_status(self):
        """Update GPU status display."""
        self.gpu_label.set_text(self.gpu_monitor.get_status())
        return True
    
    def _initial_status_check(self):
        """Perform initial status check."""
        self._check_status()
        return False
    
    def cleanup(self):
        """Clean up resources."""
        self.whisper_manager.cleanup()
        self.voice_manager.clear_the_stage()
