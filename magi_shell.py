#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Adw, Gdk, GLib, Gio
import json
import os
import subprocess
import time
import sys
import psutil
import threading
import requests
import numpy as np
import sounddevice as sd
from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo, nvmlDeviceGetUtilizationRates

# Enable GPU acceleration
os.environ['GDK_BACKEND'] = 'gl'

# Global state
windows = {}
ai_predictions = {}
panels = {}
config = None

# Performance optimizations
MONITOR_CHECK_INTERVAL = 5000  # Reduce monitor polling to 5 seconds
SYSTEM_STATS_INTERVAL = 3000   # Reduce system stats updates to 3 seconds
CLOCK_UPDATE_INTERVAL = 1000   # Keep clock at 1 second for accuracy


class WorkspaceSwitcher(Gtk.Box):
    """Workspace switcher widget for GTK4"""
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        
        self.workspace_buttons = []
        self.current_workspace = 0
        
        # Create workspace buttons
        for i in range(config['workspace_count']):
            button = Gtk.Button(label=str(i + 1))
            button.connect('clicked', self.switch_workspace, i)
            self.append(button)
            self.workspace_buttons.append(button)
        
        # Monitor workspace changes using wmctrl
        GLib.timeout_add(500, self.update_current_workspace)
        self.update_current_workspace()
    
    def switch_workspace(self, button, workspace_num):
        """Switch to specified workspace using wmctrl"""
        try:
            subprocess.run(['wmctrl', '-s', str(workspace_num)])
        except Exception as e:
            print(f"Error switching workspace: {e}")
    
    def update_current_workspace(self):
        """Update current workspace indicator"""
        try:
            output = subprocess.check_output(['wmctrl', '-d']).decode()
            for line in output.splitlines():
                if '*' in line:
                    workspace = int(line.split()[0])
                    if workspace != self.current_workspace:
                        self.current_workspace = workspace
                        self._update_buttons()
                    break
        except Exception as e:
            print(f"Error updating workspace: {e}")
        return True
    
    def _update_buttons(self):
        """Update button styles based on current workspace"""
        for i, button in enumerate(self.workspace_buttons):
            if i == self.current_workspace:
                button.add_css_class('active-workspace')
            else:
                button.remove_css_class('active-workspace')

class WindowList(Gtk.Box):
    """Window list widget for GTK4"""
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        self.set_hexpand(True)
        
        self.window_buttons = {}
        self.current_workspace = 0
        
        # Start window monitoring
        GLib.timeout_add(500, self.update_window_list)
    
    def update_window_list(self):
        """Update window list using wmctrl"""
        try:
            # Get current workspace
            workspace_output = subprocess.check_output(['wmctrl', '-d']).decode()
            for line in workspace_output.splitlines():
                if '*' in line:
                    self.current_workspace = int(line.split()[0])
                    break
            
            # Get window list
            window_output = subprocess.check_output(['wmctrl', '-l']).decode()
            current_windows = set()
            
            for line in window_output.splitlines():
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    window_id = parts[0]
                    workspace = int(parts[1])
                    title = parts[3]
                    
                    # Skip panels and other system windows
                    if "MAGI" in title or "Desktop" in title:
                        continue
                    
                    # Only show windows from current workspace
                    if workspace == self.current_workspace or workspace == -1:  # -1 means sticky
                        current_windows.add(window_id)
                        if window_id not in self.window_buttons:
                            button = Gtk.Button(label=title[:30])
                            button.connect('clicked', self.activate_window, window_id)
                            self.append(button)
                            self.window_buttons[window_id] = button
                        else:
                            self.window_buttons[window_id].set_label(title[:30])
            
            # Remove buttons for closed windows
            for window_id in list(self.window_buttons.keys()):
                if window_id not in current_windows:
                    self.remove(self.window_buttons[window_id])
                    del self.window_buttons[window_id]
            
        except Exception as e:
            print(f"Error updating window list: {e}")
        
        return True
    
    def activate_window(self, button, window_id):
        """Activate clicked window"""
        try:
            subprocess.run(['wmctrl', '-ia', window_id])
        except Exception as e:
            print(f"Error activating window: {e}")

class SystemMonitor(Gtk.Box):
    """System monitor widget using GTK4"""
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        
        # Use a single label for all stats to reduce widget count
        self.stats_label = Gtk.Label()
        self.stats_label.add_css_class('monitor-label')
        self.append(self.stats_label)
        
        # Initialize NVIDIA monitoring
        self.nvidia_available = False
        try:
            nvmlInit()
            self.nvidia_handle = nvmlDeviceGetHandleByIndex(0)
            self.nvidia_available = True
        except:
            print("Warning: NVIDIA GPU monitoring not available")
        
        # Cached psutil CPU percent
        self.cpu_percent = psutil.cpu_percent(interval=None)
        self.last_cpu_update = time.time()
        
        # Start updates
        self.update_stats()
        GLib.timeout_add(SYSTEM_STATS_INTERVAL, self.update_stats)
    
    def update_stats(self):
        """Update system statistics"""
        try:
            # Update CPU less frequently
            current_time = time.time()
            if current_time - self.last_cpu_update >= 1:
                self.cpu_percent = psutil.cpu_percent(interval=None)
                self.last_cpu_update = current_time
            
            # Get memory usage
            mem = psutil.virtual_memory()
            ram_percent = mem.percent
            
            # Get GPU stats if available
            if self.nvidia_available:
                try:
                    util = nvmlDeviceGetUtilizationRates(self.nvidia_handle)
                    mem = nvmlDeviceGetMemoryInfo(self.nvidia_handle)
                    gpu_percent = util.gpu
                    vram_percent = (mem.used / mem.total) * 100
                except:
                    gpu_percent = vram_percent = 0
            else:
                gpu_percent = vram_percent = 0
            
            # Update all stats in a single label update
            stats_text = f"CPU: {self.cpu_percent:>5.1f}% | RAM: {ram_percent:>5.1f}%"
            if self.nvidia_available:
                stats_text += f" | GPU: {gpu_percent:>5.1f}% | VRAM: {vram_percent:>5.1f}%"
            
            self.stats_label.set_label(stats_text)
            
        except Exception as e:
            print(f"Error updating stats: {e}")
        
        return True  # Continue updating


def load_config():
    """Load configuration from JSON file"""
    global config
    config_path = os.path.expanduser("~/.config/magi/config.json")
    try:
        with open(config_path) as f:
            config = json.load(f)
    except Exception as e:
        print(f"Warning: Could not load config ({e}), using defaults")
        config = {
            "panel_height": 28,
            "workspace_count": 4,
            "enable_effects": True,
            "enable_ai": True,
            "terminal": "mate-terminal",
            "launcher": "mate-panel --run-dialog",
            "background": "/usr/share/magi/backgrounds/default.png",
            "ollama_model": "mistral",
            "whisper_endpoint": "http://localhost:5000/transcribe",
            "sample_rate": 16000
        }
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Warning: Could not save config: {e}")

class VoiceInputButton(Gtk.Button):
    """Voice input button using the same implementation as llm_menu"""
    def __init__(self):
        super().__init__()
        self.stream = None
        self.record_start_time = 0
        self.recording = False
        self.is_transcribing = False
        self.audio_data = []
        
        # Create icons
        self.mic_icon = Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic")
        self.record_icon = Gtk.Image.new_from_icon_name("media-record-symbolic")
        self.set_child(self.mic_icon)
        
        # Setup click gesture
        click = Gtk.GestureClick.new()
        click.connect('begin', self.start_recording)
        click.connect('end', self.stop_recording)
        self.add_controller(click)
    
    def start_recording(self, gesture, sequence):
        if self.is_transcribing:
            return
            
        print("Starting recording...")
        self.recording = True
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except:
                pass
            self.stream = None
            
        self.audio_data = []
        self.record_start_time = time.time()
        
        # Swap to record icon
        self.set_child(self.record_icon)
        
        def audio_callback(indata, *args):
            if self.recording:
                self.audio_data.append(indata.copy())
        
        try:
            self.stream = sd.InputStream(
                callback=audio_callback,
                channels=1,
                samplerate=16000,
                blocksize=1024,
                dtype=np.float32
            )
            self.stream.start()
            print("Recording stream started successfully")
            self.add_css_class('recording')
        except Exception as e:
            print(f"Recording Error: {e}")
            self.recording = False
            self.set_child(self.mic_icon)
    
    def stop_recording(self, gesture, sequence):
        if self.is_transcribing:
            return
            
        print("Stopping recording...")
        self.recording = False
        recording_duration = time.time() - self.record_start_time
        
        # Stop recording first
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            except Exception as e:
                print(f"Error stopping recording: {e}")
        
        # Reset button state
        self.set_child(self.mic_icon)
        self.remove_css_class('recording')
        
        # Handle short recordings
        if recording_duration < 0.5:
            print("Recording too short")
            subprocess.run(['espeak', "Press and hold to record audio"])
            return
        
        # Process audio
        if self.audio_data:
            try:
                print("Processing audio...")
                self.is_transcribing = True
                self.set_sensitive(False)
                
                # Create a copy of audio data
                audio_data = np.concatenate(self.audio_data.copy())
                self.audio_data = []
                
                def transcribe():
                    try:
                        print("Sending to whisper...")
                        files = {'audio': ('audio.wav', audio_data.tobytes())}
                        response = requests.post('http://localhost:5000/transcribe', files=files)
                        
                        def handle_response():
                            self.is_transcribing = False
                            self.set_sensitive(True)
                            
                            if response.ok:
                                text = response.json().get('transcription', '')
                                if text:
                                    subprocess.run(['xdotool', 'type', text])
                            else:
                                print(f"Transcription error: {response.status_code}")
                        
                        GLib.idle_add(handle_response)
                    
                    except Exception as e:
                        print(f"Transcription error: {e}")
                        GLib.idle_add(lambda: setattr(self, 'is_transcribing', False))
                        GLib.idle_add(lambda: self.set_sensitive(True))
                
                # Start transcription in background
                threading.Thread(target=transcribe, daemon=True).start()
                
            except Exception as e:
                print(f"Audio processing error: {e}")
                self.is_transcribing = False
                self.set_sensitive(True)

class MAGIPanel(Gtk.ApplicationWindow):
    """Main panel window using GTK4"""
    def __init__(self, app, position='top', **kwargs):
        super().__init__(**kwargs)
        
        # Set application
        self.set_application(app)
        
        self.position = position
        self.set_title(f"MAGI Panel ({position})")
        
        # Set window properties for panel behavior
        self.set_decorated(False)
        self.set_resizable(False)
        
        # Main box
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.set_child(self.box)
        
        if position == 'top':
            self.setup_top_panel()
        else:
            self.setup_bottom_panel()
        
        # Initial geometry setup
        self.initial_geometry_setup()
        
        # Connect map signal instead of realize
        self.connect('map', self.on_map)
        
        # Monitor geometry changes less frequently
        GLib.timeout_add(2000, self.update_geometry)
        
    def initial_geometry_setup(self):
        """Set initial geometry before window is realized"""
        display = self.get_display()
        monitor = display.get_monitors()[0]  # Get first monitor initially
        
        geometry = monitor.get_geometry()
        scale = monitor.get_scale_factor()
        
        # Calculate panel dimensions
        width = geometry.width
        height = config['panel_height'] * scale
        
        # Set initial size
        self.set_size_request(width, height)
        self.set_default_size(width, height)
        
    def on_map(self, widget):
        """Handle window mapping"""
        # Give the window a moment to be fully mapped
        GLib.timeout_add(100, self.delayed_window_setup)
    
    
    def delayed_window_setup(self):
        """Set up window properties after it's mapped"""
        try:
            # First try getting window by PID
            pid = os.getpid()
            window_id = None
            
            try:
                output = subprocess.check_output(['xdotool', 'search', '--pid', str(pid), '--class', 'Gtk4Window']).decode().strip()
                if output:
                    window_ids = output.split('\n')
                    # Try to match by geometry to find our panel
                    for wid in window_ids:
                        try:
                            info = subprocess.check_output(['xwininfo', '-id', wid]).decode()
                            if f"MAGI Panel ({self.position})" in info:
                                window_id = wid
                                break
                        except:
                            continue
            except Exception as e:
                print(f"Error finding window by PID: {e}")
            
            # Fallback to title search if PID method failed
            if not window_id:
                try:
                    output = subprocess.check_output(['wmctrl', '-l']).decode()
                    for line in output.splitlines():
                        if f"MAGI Panel ({self.position})" in line:
                            window_id = line.split()[0]
                            break
                except Exception as e:
                    print(f"Error finding window by title: {e}")
            
            if window_id:
                # Set window type and properties
                subprocess.run(['wmctrl', '-i', '-r', window_id, '-b', 'add,sticky,above'])
                subprocess.run(['wmctrl', '-i', '-r', window_id, '-T', f'MAGI Panel ({self.position})'])
                
                # Position the window
                display = self.get_display()
                monitor = display.get_monitors()[0]
                geometry = monitor.get_geometry()
                scale = monitor.get_scale_factor()
                
                width = geometry.width
                height = config['panel_height'] * scale
                x = geometry.x
                
                if self.position == 'top':
                    y = geometry.y
                    # Set struts for top panel
                    subprocess.run([
                        'xprop', '-id', window_id,
                        '-f', '_NET_WM_STRUT_PARTIAL', '32c',
                        '-set', '_NET_WM_STRUT_PARTIAL',
                        f'0, 0, {height}, 0, 0, 0, 0, 0, {x}, {x + width}, 0, 0'
                    ])
                else:
                    y = geometry.y + geometry.height - height
                    # Set struts for bottom panel
                    subprocess.run([
                        'xprop', '-id', window_id,
                        '-f', '_NET_WM_STRUT_PARTIAL', '32c',
                        '-set', '_NET_WM_STRUT_PARTIAL',
                        f'0, 0, 0, {height}, 0, 0, 0, 0, 0, 0, {x}, {x + width}'
                    ])
                
                # Position window using absolute positioning
                subprocess.run([
                    'xdotool', 'windowmove', window_id, str(x), str(y)
                ])
                
                # Set window size
                subprocess.run([
                    'xdotool', 'windowsize', window_id, str(width), str(height)
                ])
                
                # Ensure window is on top and sticky
                subprocess.run(['wmctrl', '-i', '-r', window_id, '-b', 'add,sticky,above'])
                
                # Set dock type
                subprocess.run([
                    'xprop', '-id', window_id,
                    '-f', '_NET_WM_WINDOW_TYPE', '32a',
                    '-set', '_NET_WM_WINDOW_TYPE',
                    '_NET_WM_WINDOW_TYPE_DOCK'
                ])
        
        except Exception as e:
            print(f"Error in delayed window setup: {e}")
        
        return False
    
    def update_geometry(self):
        """Update panel geometry when monitor changes"""
        if self.get_realized():
            self.delayed_window_setup()
        return True
    
    def setup_top_panel(self):
        """Set up top panel widgets"""
        # Launcher button
        launcher = Gtk.Button(label=" MAGI ")
        launcher.add_css_class('launcher-button')
        launcher.connect('clicked', lambda w: subprocess.Popen(config['launcher'].split()))
        
        # Workspace switcher
        workspace_switcher = WorkspaceSwitcher()
        
        # Window list
        window_list = WindowList()
        
        # System monitor
        monitor = SystemMonitor()
        
        # Network button
        network = Gtk.Button()
        network.set_child(Gtk.Image.new_from_icon_name("network-wireless-symbolic"))
        network.connect('clicked', lambda w: subprocess.Popen(['nm-connection-editor']))
        
        # Clock
        clock = Gtk.Label()
        clock.add_css_class('clock-label')
        def update_clock():
            clock.set_label(time.strftime("%Y-%m-%d %H:%M:%S"))
            return True
        update_clock()
        GLib.timeout_add(CLOCK_UPDATE_INTERVAL, update_clock)
        
        # Pack widgets
        self.box.append(launcher)
        self.box.append(workspace_switcher)
        self.box.append(window_list)
        self.box.append(monitor)
        self.box.append(network)
        self.box.append(clock)
    
    def setup_bottom_panel(self):
        """Set up bottom panel widgets with centered content"""
        # Center box for content
        center_box = Gtk.CenterBox()
        self.box.append(center_box)
        
        # Create a container for the buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        # LLM button
        llm_button = Gtk.Button(label="Ask anything...")
        llm_button.connect('clicked', lambda w: 
            subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), 'llm_menu.py')]))
        
        # TTS button
        tts_button = Gtk.Button()
        tts_button.set_child(Gtk.Image.new_from_icon_name("audio-speakers-symbolic"))
        tts_button.connect('clicked', self.speak_selection)
        
        # Voice input button
        voice_button = VoiceInputButton()
        
        # Pack buttons into button box
        button_box.append(llm_button)
        button_box.append(tts_button)
        button_box.append(voice_button)
        
        # Center the button box
        center_box.set_center_widget(button_box)
    
    def speak_selection(self, button):
        """Handle TTS button click"""
        try:
            clipboard = self.get_display().get_primary_clipboard()
            clipboard.read_text_async(None, self._handle_clipboard_text)
        except Exception as e:
            print(f"TTS Error: {e}")
    
    def _handle_clipboard_text(self, clipboard, result):
        """Handle clipboard text for TTS"""
        try:
            text = clipboard.read_text_finish(result)
            if text:
                subprocess.Popen(['espeak', text])
        except Exception as e:
            print(f"TTS Error: {e}")

class MAGIApplication(Adw.Application):
    """Main application class"""
    def __init__(self):
        # Use a proper reverse-DNS application ID format
        super().__init__(application_id='dev.magi.shell')
    
    def do_activate(self):
        # Load config first
        load_config()
        
        # Create panels
        self.top_panel = MAGIPanel(app=self, position='top')
        self.bottom_panel = MAGIPanel(app=self, position='bottom')
        
        # Show panels
        self.top_panel.present()
        self.bottom_panel.present()

def main():
    app = MAGIApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    try:
        # Enable GPU rendering
        os.environ['GDK_BACKEND'] = 'gl'
        
        # Start application
        app = MAGIApplication()
        
        def cleanup(signum=None, frame=None):
            """Cleanup resources before exit"""
            print("\nCleaning up...")
            for panel in panels.values():
                if hasattr(panel, 'cleanup_recording'):
                    panel.cleanup_recording()
            sys.exit(0)
            
        import signal
        signal.signal(signal.SIGINT, cleanup)
        signal.signal(signal.SIGTERM, cleanup)
        
        exit_code = app.run(sys.argv)
        cleanup()
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
