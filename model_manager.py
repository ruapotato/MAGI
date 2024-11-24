#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk
import os
import json
import threading
import subprocess
import requests
import time
import numpy as np
import psutil
import socket
from ThemeManager import ThemeManager
from pathlib import Path

# Get script directory for relative paths
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_DIR = SCRIPT_DIR / 'ears_pyenv'
WHISPER_SERVER = SCRIPT_DIR / 'whisper_server.py'

def find_process_by_port(port):
    """Find process using a specific port"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            for conn in proc.connections('tcp'):
                if conn.laddr.port == port:
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def kill_process_on_port(port):
    """Kill any process using the specified port"""
    proc = find_process_by_port(port)
    if proc:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
            return True
        except psutil.NoSuchProcess:
            pass
    return False

def is_port_in_use(port):
    """Check if a port is in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def update_start_script():
    """Update the start_whisper_server.sh script with correct paths"""
    script_content = f"""#!/bin/bash
# Activate virtualenv
source "{VENV_DIR}/bin/activate"
# Set proper Python path
export PYTHONPATH="{VENV_DIR}/lib/python3.11/site-packages"
# Start the server
exec python3 "{WHISPER_SERVER}"
"""
    
    script_path = SCRIPT_DIR / 'start_whisper_server.sh'
    with open(script_path, 'w') as f:
        f.write(script_content)
    os.chmod(script_path, 0o755)

class ModelManager(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        
        # Remove window decorations
        self.set_decorated(False)
        
        # Connect realize signal for window properties
        self.connect('realize', self._on_realize)
        
        # First, clean up any running servers
        if is_port_in_use(5000):
            print("Cleaning up old Whisper server...")
            kill_process_on_port(5000)
            time.sleep(1)  # Give time for cleanup
        
        if is_port_in_use(11434):
            print("Cleaning up old Ollama server...")
            kill_process_on_port(11434)
            time.sleep(1)  # Give time for cleanup
        
        # Load config first
        self.load_config()
        
        # Register with theme manager
        self.theme_manager = ThemeManager()
        self.theme_manager.register_window(self)
        
        self.whisper_server_process = None
        self.setup_window()
        
        # Initialize states
        self.whisper_status = "Starting"
        self.whisper_progress = 0
        self.ollama_status = "Starting"
        self.ollama_progress = 0
        
        # Track if verification is in progress
        self.verification_in_progress = False
        
        # Start GPU monitoring
        GLib.timeout_add(3000, self.update_gpu_status)
        
        # Update start script and start models
        try:
            update_start_script()
            self.start_whisper_server()
            self.start_ollama_server()
        except Exception as e:
            print(f"Startup error: {e}")
        
        # Initial status check after startup
        GLib.timeout_add(5000, self.initial_status_check)
    
    def _on_realize(self, widget):
        """Set window properties after window is realized"""
        def set_window_properties():
            try:
                # Get window ID
                output = subprocess.check_output(
                    ['xdotool', 'search', '--name', '^MAGI Model Status$']
                ).decode().strip()
                
                if output:
                    window_id = output.split('\n')[0]
                    # Set window to stay below others and stick to all workspaces
                    subprocess.run(['wmctrl', '-i', '-r', window_id, '-b', 'add,below,sticky'], check=True)
                    # Make window appear on all workspaces
                    subprocess.run(['wmctrl', '-i', '-r', window_id, '-t', '-1'], check=True)
            except Exception as e:
                print(f"Failed to set window properties: {e}")
            return False
        
        # Give window time to be created before setting properties
        GLib.timeout_add(100, set_window_properties)
    
    def initial_status_check(self):
        """Perform initial status check after startup"""
        self.check_model_status()
        return False  # Don't repeat
    
    def setup_window(self):
        """Set up the window with minimal layout"""
        self.set_title("MAGI Model Status")
        self.set_default_size(400, 200)
        
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        
        # Status check button at top
        check_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        check_box.set_halign(Gtk.Align.END)
        self.check_button = Gtk.Button(label="Check Models Now")
        self.check_button.connect('clicked', lambda _: self.check_model_status())
        check_box.append(self.check_button)
        main_box.append(check_box)
        
        # Whisper section
        whisper_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        # Header with status
        whisper_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.whisper_indicator = Gtk.Label(label="●")
        whisper_header.append(self.whisper_indicator)
        whisper_header.append(Gtk.Label(label="WHISPER"))
        whisper_header.set_hexpand(True)
        
        self.whisper_reload = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        self.whisper_reload.connect('clicked', self.on_whisper_reload)
        whisper_header.append(self.whisper_reload)
        whisper_box.append(whisper_header)
        
        # Progress bar
        self.whisper_progress_bar = Gtk.ProgressBar()
        self.whisper_progress_bar.set_hexpand(True)
        whisper_box.append(self.whisper_progress_bar)
        
        # Status label
        self.whisper_status_label = Gtk.Label()
        self.whisper_status_label.set_xalign(0)
        whisper_box.append(self.whisper_status_label)
        
        main_box.append(whisper_box)
        
        # Separator
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        # Ollama section
        ollama_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        # Header with status
        ollama_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.ollama_indicator = Gtk.Label(label="●")
        ollama_header.append(self.ollama_indicator)
        model_name = self.config.get('ollama_model', 'mistral').upper()
        ollama_header.append(Gtk.Label(label=f"OLLAMA ({model_name})"))
        ollama_header.set_hexpand(True)
        
        self.ollama_reload = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        self.ollama_reload.connect('clicked', self.on_ollama_reload)
        ollama_header.append(self.ollama_reload)
        ollama_box.append(ollama_header)
        
        # Progress bar
        self.ollama_progress_bar = Gtk.ProgressBar()
        self.ollama_progress_bar.set_hexpand(True)
        ollama_box.append(self.ollama_progress_bar)
        
        # Status label
        self.ollama_status_label = Gtk.Label()
        self.ollama_status_label.set_xalign(0)
        ollama_box.append(self.ollama_status_label)
        
        main_box.append(ollama_box)
        
        # Separator
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        # GPU status
        self.gpu_info = Gtk.Label()
        self.gpu_info.set_xalign(0)
        main_box.append(self.gpu_info)
        
        # Last check time
        self.last_check_label = Gtk.Label()
        self.last_check_label.set_xalign(1)
        main_box.append(self.last_check_label)
        
        self.set_child(main_box)
    
    def load_config(self):
        """Load MAGI configuration"""
        config_path = os.path.expanduser("~/.config/magi/config.json")
        try:
            with open(config_path) as f:
                self.config = json.load(f)
        except Exception:
            self.config = {'ollama_model': 'mistral'}
    
    def check_model_status(self):
        """Perform a deep check of both models"""
        if self.verification_in_progress:
            print("Verification already in progress, skipping...")
            return
        
        print("Performing deep status check...")
        self.verification_in_progress = True
        self.check_button.set_sensitive(False)
        
        def verify_models():
            # Check Whisper
            try:
                # Test actual transcription
                audio_data = np.zeros(16000, dtype=np.float32)  # 1 second of silence
                files = {'audio': ('test.wav', audio_data.tobytes())}
                response = requests.post('http://localhost:5000/transcribe', 
                                      files=files, timeout=5)
                if response.ok:
                    GLib.idle_add(self.set_whisper_status, "Running", 100, "Model verified")
                else:
                    GLib.idle_add(self.set_whisper_status, "Error", 0, "Model verification failed")
            except Exception as e:
                print(f"Whisper verification error: {e}")
                GLib.idle_add(self.set_whisper_status, "Error", 0, str(e))
            
            # Check Ollama
            try:
                model_name = self.config.get('ollama_model', 'mistral')
                # Test quick generation
                response = requests.post(
                    'http://localhost:11434/api/generate',
                    json={'model': model_name, 'prompt': 'test', 'raw': True},
                    timeout=5
                )
                if response.ok:
                    GLib.idle_add(self.set_ollama_status, "Running", 100, "Model verified")
                else:
                    GLib.idle_add(self.set_ollama_status, "Error", 0, "Model verification failed")
            except Exception as e:
                print(f"Ollama verification error: {e}")
                GLib.idle_add(self.set_ollama_status, "Error", 0, str(e))
            
            # Update last check time
            check_time = time.strftime("%H:%M:%S")
            GLib.idle_add(self.last_check_label.set_text, f"Last checked: {check_time}")
            
            # Reset verification state
            GLib.idle_add(self._reset_verification_state)
        
        # Run verification in background
        threading.Thread(target=verify_models, daemon=True).start()
    
    def _reset_verification_state(self):
        """Reset verification state and button"""
        self.verification_in_progress = False
        self.check_button.set_sensitive(True)
    
    def start_whisper_server(self):
        """Start the Whisper server"""
        try:
            # Check if port is in use and clean up
            if is_port_in_use(5000):
                print("Cleaning up old Whisper server...")
                kill_process_on_port(5000)
                time.sleep(1)  # Give the port time to be released
            
            # Clean up any existing progress file
            try:
                os.remove('/tmp/MAGI/whisper_progress')
            except FileNotFoundError:
                pass
            
            script_path = str(SCRIPT_DIR / 'start_whisper_server.sh')
            self.whisper_server_process = subprocess.Popen([script_path])
            print(f"Started Whisper server with script: {script_path}")
            self.set_whisper_status("Starting", 0, "Starting server...")
        except Exception as e:
            print(f"Failed to start Whisper server: {e}")
            self.set_whisper_status("Error", 0, f"Failed to start: {e}")
    
    def start_ollama_server(self):
        """Start Ollama server"""
        try:
            # Check if port is in use and clean up
            if is_port_in_use(11434):
                print("Cleaning up old Ollama server...")
                kill_process_on_port(11434)
                time.sleep(1)  # Give the port time to be released
            
            subprocess.Popen(['ollama', 'serve'])
            time.sleep(2)  # Give it time to start
            threading.Thread(target=self.load_ollama_model, daemon=True).start()
            self.set_ollama_status("Starting", 0, "Starting server...")
        except Exception as e:
            print(f"Failed to start Ollama server: {e}")
            self.set_ollama_status("Error", 0, f"Failed to start: {e}")
    
    def load_ollama_model(self):
        """Load Ollama model"""
        try:
            model_name = self.config.get('ollama_model', 'mistral')
            
            # Pull model
            response = requests.post(
                'http://localhost:11434/api/pull',
                json={'name': model_name},
                stream=True
            )
            
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if 'status' in data:
                        GLib.idle_add(
                            self.set_ollama_status,
                            "Loading",
                            int(data.get('completed', 0) * 80 / 100),  # Scale to 80%
                            data['status']
                        )
                    if 'completed' in data:
                        break
            
            GLib.idle_add(
                self.set_ollama_status,
                "Loading",
                90,
                "Testing model..."
            )
            
            # Test model
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={'model': model_name, 'prompt': 'Hello!'}
            )
            
            if response.ok:
                GLib.idle_add(
                    self.set_ollama_status,
                    "Running",
                    100,
                    "Model loaded and ready"
                )
            else:
                GLib.idle_add(
                    self.set_ollama_status,
                    "Error",
                    0,
                    "Model test failed"
                )
            
        except Exception as e:
            print(f"Ollama load error: {e}")
            GLib.idle_add(
                self.set_ollama_status,
                "Error",
                0,
                str(e)
            )
    
    def on_whisper_reload(self, button):
        """Handle Whisper reload button click"""
        if self.verification_in_progress:
            return
            
        button.set_sensitive(False)
        
        # Clean up existing server
        if self.whisper_server_process:
            try:
                self.whisper_server_process.terminate()
                self.whisper_server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.whisper_server_process.kill()
            self.whisper_server_process = None
        
        # Kill any stray processes
        if is_port_in_use(5000):
            kill_process_on_port(5000)
            time.sleep(1)  # Give it time to clean up
        
        # Reset status and start fresh
        self.whisper_status = "Starting"
        self.whisper_progress = 0
        self.update_status_displays()
        self.start_whisper_server()
        button.set_sensitive(True)
    
    def on_ollama_reload(self, button):
        """Handle Ollama reload button click"""
        if self.verification_in_progress:
            return
            
        button.set_sensitive(False)
        
        # Clean up existing server
        if is_port_in_use(11434):
            kill_process_on_port(11434)
            time.sleep(1)
        
        self.ollama_status = "Starting"
        self.ollama_progress = 0
        self.update_status_displays()
        self.start_ollama_server()
        button.set_sensitive(True)
    
    def set_whisper_status(self, status, progress, message=""):
        """Update Whisper status display"""
        self.whisper_status = status
        self.whisper_progress = progress
        self.whisper_progress_bar.set_fraction(progress / 100)
        self.whisper_status_label.set_text(message)
        self.whisper_reload.set_sensitive(status in ["Running", "Error"])
        self.update_status_displays()
    
    def set_ollama_status(self, status, progress=0, message=""):
        """Update Ollama status display"""
        self.ollama_status = status
        self.ollama_progress = progress
        self.ollama_progress_bar.set_fraction(progress / 100)
        self.ollama_status_label.set_text(message)
        self.ollama_reload.set_sensitive(status in ["Running", "Error"])
        self.update_status_displays()
    
    def update_status_displays(self):
        """Update status indicators"""
        def update_indicator(indicator, status):
            indicator.remove_css_class('status-running')
            indicator.remove_css_class('status-error')
            indicator.remove_css_class('status-loading')
            
            if status == "Running":
                indicator.add_css_class('status-running')
            elif status == "Error":
                indicator.add_css_class('status-error')
            else:
                indicator.add_css_class('status-loading')
        
        update_indicator(self.whisper_indicator, self.whisper_status)
        update_indicator(self.ollama_indicator, self.ollama_status)
    
    def update_gpu_status(self):
        """Update GPU status display"""
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            
            # Get memory info
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            mem_used_gb = mem.used / 1024**3
            mem_total_gb = mem.total / 1024**3
            
            # Get temperature
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            
            self.gpu_info.set_text(
                f"GPU Memory: {mem_used_gb:.1f}GB/{mem_total_gb:.1f}GB | Temp: {temp}°C"
            )
        except Exception:
            self.gpu_info.set_text("GPU: Not Available")
        
        return True
    
    def cleanup(self):
        """Clean up resources"""
        if self.whisper_server_process:
            try:
                self.whisper_server_process.terminate()
                self.whisper_server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.whisper_server_process.kill()
            except Exception as e:
                print(f"Error cleaning up Whisper server: {e}")
        
        # Clean up ports
        for port in [5000, 11434]:
            if is_port_in_use(port):
                try:
                    kill_process_on_port(port)
                except Exception as e:
                    print(f"Error cleaning up port {port}: {e}")

class ModelManagerApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.system.magi.models')
    
    def do_activate(self):
        """Create and show the main window"""
        win = ModelManager(self)
        win.present()
        
        # Position at top right of screen
        display = win.get_display()
        monitor = display.get_monitors()[0]
        geometry = monitor.get_geometry()
        
        win_width, win_height = win.get_default_size()
        # Calculate x to align with right edge, leaving a small gap
        x = geometry.x + geometry.width - win_width - 10
        # Calculate y to align with top edge, leaving a small gap
        y = geometry.y + 10
        
        def set_window_properties():
            try:
                # Get window ID
                output = subprocess.check_output(['xdotool', 'search', '--name', '^MAGI Model Status$']).decode().strip()
                if output:
                    window_id = output.split('\n')[0]
                    
                    # Make window visible on all workspaces with -1
                    subprocess.run(['wmctrl', '-i', '-r', window_id, '-t', '-1'], check=True)
                    
                    # Set window to stay below others and make it sticky (appears on all workspaces)
                    subprocess.run(['wmctrl', '-i', '-r', window_id, '-b', 'add,below,sticky'], check=True)
                    
                    # Move window to top right
                    subprocess.run(['wmctrl', '-i', '-r', window_id, '-e', f'0,{x},{y},-1,-1'], check=True)
                    
                    # Additional command to ensure it's on all workspaces
                    subprocess.run(['wmctrl', '-i', '-r', window_id, '-b', 'add,sticky'], check=True)
            except Exception as e:
                print(f"Failed to set window properties: {e}")
                # Retry after a short delay if it fails
                GLib.timeout_add(500, set_window_properties)
                return False
            return False
        
        # Give the window time to appear before setting properties
        GLib.timeout_add(100, set_window_properties)

def main():
    """Main entry point"""
    import signal
    
    app = ModelManagerApplication()
    
    def cleanup(signum=None, frame=None):
        """Clean up resources on exit"""
        print("\nCleaning up...")
        for window in app.get_windows():
            if isinstance(window, ModelManager):
                window.cleanup()
                break
        app.quit()
    
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    try:
        exit_code = app.run(None)
        cleanup()
        return exit_code
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
