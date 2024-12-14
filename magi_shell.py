#!/usr/bin/env python3
"""The MAGI Shell: Where Pixels Meet Philosophy"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib, Gio, Graphene
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
from collections import deque
from weakref import WeakKeyDictionary
from ThemeManager import ThemeManager

# Tell GTK to embrace the power of silicon
os.environ['GTK_CSD'] = '0'
os.environ['GDK_SCALE'] = '1'

# The sacred numbers of optimization
UPDATE_INTERVAL = 1000      # Time between cosmic updates
BATCH_SIZE = 10            # Size of our magical batches
WIDGET_POOL_SIZE = 20      # Maximum widgets in the ethereal pool
CACHE_TIMEOUT = 5000       # How long memories persist

def load_config():
    """Summon the sacred configuration from the depths of ~/.config"""
    config_path = os.path.expanduser("~/.config/magi/config.json")
    try:
        with open(config_path) as scroll_of_settings:
            return json.load(scroll_of_settings)
    except Exception as mystical_mishap:
        print(f"Warning: The configuration scroll resists us ({mystical_mishap}), falling back to ancient defaults")
        default_config = {
            "panel_height": 28,
            "workspace_count": 4,
            "enable_effects": True,
            "enable_ai": True,
            "terminal": "mate-terminal",
            "launcher": "mate-panel --run-dialog",
            "background": "/usr/share/magi/backgrounds/default.png",
            "ollama_model": "mistral",
            "whisper_endpoint": "http://localhost:5000/transcribe",
            "sample_rate": 16000,
            "magi_theme": "Plain"
        }
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as new_scroll:
                json.dump(default_config, new_scroll, indent=4)
        except Exception as scroll_creation_mishap:
            print(f"Warning: Could not inscribe new configuration scroll: {scroll_creation_mishap}")
        return default_config

class UpdateManager:
    """The grand conductor of the update orchestra"""
    def __init__(self):
        self._updates = {}
        self._pending = set()
        self._last_update = {}
        self._batch_id = None
        
    def schedule(self, name, callback, interval, priority=GLib.PRIORITY_DEFAULT):
        """Schedule an update in the cosmic dance of the interface"""
        current_time = time.monotonic() * 1000
        last_time = self._last_update.get(name, 0)
        
        if current_time - last_time < interval:
            return
        
        self._pending.add(name)
        self._updates[name] = (callback, interval)
        
        if not self._batch_id:
            self._batch_id = GLib.timeout_add(
                UPDATE_INTERVAL // BATCH_SIZE,
                self._process_updates
            )
    
    def _process_updates(self):
        """Process the gathered updates in a harmonious batch"""
        current_time = time.monotonic() * 1000
        processed = set()
        
        for name in list(self._pending):
            if name in self._updates:
                callback, interval = self._updates[name]
                last_time = self._last_update.get(name, 0)
                
                if current_time - last_time >= interval:
                    try:
                        callback()
                        self._last_update[name] = current_time
                        processed.add(name)
                    except Exception as update_mishap:
                        print(f"The update ritual failed ({name}): {update_mishap}")
        
        self._pending -= processed
        self._batch_id = None
        return False

class WidgetPool:
    """A mystical pool where widgets rest between incarnations"""
    def __init__(self, widget_class, size=WIDGET_POOL_SIZE):
        self._class = widget_class
        self._pool = deque(maxlen=size)
        self._active = WeakKeyDictionary()
        
        # Pre-summon the widget spirits
        for _ in range(size):
            self._pool.append(self._create_widget())
    
    def _create_widget(self):
        """Breathe life into a new widget"""
        return self._class()
    
    def acquire(self):
        """Summon a widget from the pool"""
        if self._pool:
            widget = self._pool.pop()
        else:
            widget = self._create_widget()
        self._active[widget] = True
        return widget
    
    def release(self, widget):
        """Return a widget to its slumber"""
        if widget in self._active:
            del self._active[widget]
            if len(self._pool) < self._pool.maxlen:
                self._pool.append(widget)

class Cache:
    """The temporary memory palace of our digital dreams"""
    def __init__(self, timeout=CACHE_TIMEOUT):
        self._cache = {}
        self._timestamps = {}
        self._timeout = timeout
    
    def get(self, key):
        """Recall a memory if it hasn't faded"""
        if key in self._cache:
            timestamp = self._timestamps[key]
            if time.monotonic() * 1000 - timestamp < self._timeout:
                return self._cache[key]
            del self._cache[key]
            del self._timestamps[key]
        return None
    
    def set(self, key, value):
        """Inscribe a new memory"""
        self._cache[key] = value
        self._timestamps[key] = time.monotonic() * 1000

class WhisperingEarButton(Gtk.Button):
    """The mystical ear that channels voices from the ether"""
    def __init__(self):
        super().__init__()
        self._ethereal_portal = None
        
        # The all-seeing ear icon
        self.set_child(Gtk.Image.new_from_icon_name("audio-card-symbolic"))
        self.add_css_class('whispering-ear-button')
        
        # When clicked, open the portal to wisdom
        self.connect('clicked', self._summon_listening_portal)
    
    def _summon_listening_portal(self, _):
        """Open a terminal window to the realm of voice understanding"""
        if self._ethereal_portal:
            return
            
        try:
            # Find the path to our mystical scrolls
            sacred_scroll_path = os.path.dirname(os.path.abspath(__file__))
            
            # Prepare the incantation
            listening_spell = (
                f"cd {sacred_scroll_path} && "
                f"./asr.py | ./voice_assistant.py"
            )
            
            # Open the portal
            self._ethereal_portal = subprocess.Popen(
                ['mate-terminal', '--title=MAGI Voice Assistant', 
                 '--command', f'bash -c "{listening_spell}"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Monitor the portal's status
            def portal_watcher():
                if self._ethereal_portal:
                    self._ethereal_portal.wait()
                    self._ethereal_portal = None
                return False
            
            GLib.timeout_add(1000, portal_watcher)
            
        except Exception as mystical_mishap:
            print(f"Failed to open the listening portal: {mystical_mishap}")
            if self._ethereal_portal:
                self._ethereal_portal.terminate()
                self._ethereal_portal = None

class WorkspaceSwitcher(Gtk.Box):
    """The master of workspace dimensions"""
    def __init__(self, update_manager):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        
        self._update_manager = update_manager
        self._button_pool = WidgetPool(Gtk.Button)
        self._active_buttons = {}
        self._cache = Cache()
        
        self._setup_workspace_buttons()
        
    def _setup_workspace_buttons(self):
        config = load_config()
        for realm_number in range(config['workspace_count']):
            portal_button = self._button_pool.acquire()
            portal_button.set_label(str(realm_number + 1))
            portal_button.connect('clicked', self._switch_workspace, realm_number)
            self.append(portal_button)
            self._active_buttons[realm_number] = portal_button
        
        self._update_manager.schedule(
            'workspaces',
            self._update_current_workspace,
            UPDATE_INTERVAL
        )
    
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
class WindowList(Gtk.Box):
    """The grand curator of window souls"""
    def __init__(self, update_manager):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        self.set_hexpand(True)
        
        self._update_manager = update_manager
        self._button_pool = WidgetPool(Gtk.Button)
        self._window_buttons = {}
        self._cache = Cache()
        
        # Begin the eternal window watch
        self._update_window_list()
        GLib.timeout_add(1000, self._update_window_list)
    
    def _update_window_list(self):
        """Keep track of all windows in our reality"""
        try:
            window_census = subprocess.check_output(['wmctrl', '-l']).decode()
            surviving_windows = set()
            
            for window_scroll in window_census.splitlines():
                window_parts = window_scroll.split(None, 3)
                if len(window_parts) >= 4:
                    window_id = window_parts[0]
                    window_realm = int(window_parts[1])
                    window_title = window_parts[3]
                    
                    # Ignore our own reflections
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
                        # Update the window's true name
                        self._window_buttons[window_id].set_label(window_title[:30])
            
            # Bid farewell to departed windows
            for departed_id in list(self._window_buttons.keys()):
                if departed_id not in surviving_windows:
                    departed_button = self._window_buttons.pop(departed_id)
                    self.remove(departed_button)
                    self._button_pool.release(departed_button)
            
        except Exception as window_chaos:
            print(f"Window list descended into chaos: {window_chaos}")
        
        return True  # The watch never ends
    
    def summon_window(self, button, window_id):
        """Bring forth a window from the digital void"""
        try:
            subprocess.run(['wmctrl', '-ia', window_id], check=True)
        except Exception as summoning_mishap:
            print(f"Window summoning ritual failed: {summoning_mishap}")

class SystemMonitor(Gtk.Box):
    """The all-seeing eye of system resources"""
    def __init__(self, update_manager):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        
        self._update_manager = update_manager
        self._prophecy_label = Gtk.Label()
        self._prophecy_label.add_css_class('monitor-label')
        self.append(self._prophecy_label)
        
        # Begin the resource divination
        self._setup_monitoring()
        
    def _setup_monitoring(self):
        """Establish connection with the silicon spirits"""
        self._nvidia = None
        try:
            nvmlInit()
            self._nvidia = nvmlDeviceGetHandleByIndex(0)
        except Exception:
            print("NVIDIA crystal ball unavailable")
        
        self._cpu_cache = Cache(timeout=1000)
        self._divine_resource_usage()
        GLib.timeout_add(3000, self._divine_resource_usage)
    
    def _divine_resource_usage(self):
        """Read the digital tea leaves of system resources"""
        try:
            # Consult the CPU oracle
            cpu_load = psutil.cpu_percent(interval=None)
            
            # Peek into the memory realm
            memory_state = psutil.virtual_memory()
            ram_usage = memory_state.percent
            
            # Check the GPU crystal ball if available
            if self._nvidia:
                try:
                    gpu_prophecy = nvmlDeviceGetUtilizationRates(self._nvidia)
                    gpu_memory = nvmlDeviceGetMemoryInfo(self._nvidia)
                    gpu_load = gpu_prophecy.gpu
                    vram_usage = (gpu_memory.used / gpu_memory.total) * 100
                except:
                    gpu_load = vram_usage = 0
                
                self._prophecy_label.set_label(
                    f"CPU: {cpu_load:>5.1f}% | RAM: {ram_usage:>5.1f}% | "
                    f"GPU: {gpu_load:>5.1f}% | VRAM: {vram_usage:>5.1f}%"
                )
            else:
                self._prophecy_label.set_label(
                    f"CPU: {cpu_load:>5.1f}% | RAM: {ram_usage:>5.1f}%"
                )
            
        except Exception as divination_failure:
            print(f"Resource reading went awry: {divination_failure}")
        
        return True  # Continue the eternal watch





























class VoiceInputButton(Gtk.Button):
    """Optimized voice input button using system default audio"""
    def __init__(self):
        super().__init__()
        
        self._recording = False
        self._transcribing = False
        self._stream = None
        self._audio_buffer = []
        self._start_time = 0
        
        self._setup_ui()
        self._setup_gestures()
    
    def _setup_ui(self):
        """Set up button UI"""
        self._mic_icon = Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic")
        self._record_icon = Gtk.Image.new_from_icon_name("media-record-symbolic")
        self.set_child(self._mic_icon)
    
    def _setup_gestures(self):
        """Set up button gestures"""
        click = Gtk.GestureClick.new()
        click.connect('begin', self._start_recording)
        click.connect('end', self._stop_recording)
        self.add_controller(click)
    
    def _start_recording(self, gesture, sequence):
        """Start audio recording with system default device"""
        if self._transcribing:
            return
        
        print("Starting recording...")
        self._recording = True
        self._start_time = time.monotonic()
        self._audio_buffer.clear()
        
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except:
                pass
            self._stream = None
        
        # Use system default audio input
        try:
            config = load_config()
            sample_rate = config.get('sample_rate', 16000)
            
            self._stream = sd.InputStream(
                channels=1,
                callback=self._audio_callback,
                blocksize=1024,
                samplerate=sample_rate,
                dtype=np.float32
            )
            self._stream.start()
            self.set_child(self._record_icon)
            self.add_css_class('recording')
            print(f"Recording started with default device at {sample_rate}Hz")
        except Exception as e:
            print(f"Recording error: {e}")
            self._recording = False
            self.set_child(self._mic_icon)
            dialog = Adw.MessageDialog.new(
                self.get_root(),
                "Recording Error",
                str(e)
            )
            dialog.add_response("ok", "OK")
            dialog.present()
    
    def _audio_callback(self, indata, *args):
        """Handle audio input"""
        if self._recording:
            self._audio_buffer.append(indata.copy())
    
    def _stop_recording(self, gesture, sequence):
        """Stop and process recording"""
        if self._transcribing:
            return
        
        print("Stopping recording...")
        self._recording = False
        duration = time.monotonic() - self._start_time
        
        # Stop recording
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            except Exception as e:
                print(f"Error stopping recording: {e}")
        
        # Reset button state
        self.set_child(self._mic_icon)
        self.remove_css_class('recording')
        
        # Handle short recordings
        if duration < 0.5:
            print("Recording too short")
            if not hasattr(self, '_speaking'):
                self._speaking = True
                subprocess.run(['espeak', "Press and hold to record audio"])
                GLib.timeout_add(2000, self._reset_speaking_state)
            return
        
        # Process audio
        if self._audio_buffer:
            try:
                print("Processing audio...")
                self._transcribing = True
                self.set_sensitive(False)
                
                # Create a copy of audio data
                audio_data = np.concatenate(self._audio_buffer.copy())
                self._audio_buffer.clear()
                
                # Process in background
                threading.Thread(
                    target=self._transcribe_audio,
                    args=(audio_data,),
                    daemon=True
                ).start()
                
            except Exception as e:
                print(f"Audio processing error: {e}")
                self._transcribing = False
                self.set_sensitive(True)
    
    def _reset_speaking_state(self):
        """Reset the speaking state flag"""
        if hasattr(self, '_speaking'):
            delattr(self, '_speaking')
        return False
    
    def _transcribe_audio(self, audio_data):
        """Transcribe audio in background"""
        config = load_config()
        try:
            print("Sending to whisper...")
            endpoint = config.get('whisper_endpoint', 'http://localhost:5000/transcribe')
            files = {'audio': ('audio.wav', audio_data.tobytes())}
            response = requests.post(endpoint, files=files)
            
            GLib.idle_add(self._handle_transcription, response)
            
        except Exception as e:
            print(f"Transcription error: {e}")
            GLib.idle_add(self._reset_state)
    
    def _handle_transcription(self, response):
        """Handle transcription response"""
        try:
            if response.ok:
                text = response.json().get('transcription', '')
                if text:
                    subprocess.run(['xdotool', 'type', text], check=True)
        except Exception as e:
            print(f"Transcription handling error: {e}")
        finally:
            self._reset_state()
        return False
    
    def _reset_state(self):
        """Reset button state"""
        self._transcribing = False
        self.set_sensitive(True)
        return False
    
    def _transcribe_audio(self, audio_data):
        """Transcribe audio in background"""
        config = load_config()
        try:
            print("Sending to whisper...")
            files = {'audio': ('audio.wav', audio_data.tobytes())}
            response = requests.post(config['whisper_endpoint'], files=files)
            
            GLib.idle_add(self._handle_transcription, response)
            
        except Exception as e:
            print(f"Transcription error: {e}")
            GLib.idle_add(self._reset_state)
    
    def _handle_transcription(self, response):
        """Handle transcription response"""
        try:
            if response.ok:
                text = response.json().get('transcription', '')
                if text:
                    subprocess.run(['xdotool', 'type', text], check=True)
        except Exception as e:
            print(f"Transcription handling error: {e}")
        finally:
            self._reset_state()
        return False
    
    def _reset_state(self):
        """Reset button state"""
        self._transcribing = False
        self.set_sensitive(True)
        return False

class MAGIPanel(Gtk.ApplicationWindow):
    """Main panel window with optimizations"""
    def __init__(self, app, position='top'):
        super().__init__(application=app)
        
        # Register with theme manager
        ThemeManager().register_window(self)
        
        self.position = position
        self.set_title(f"MAGI Panel ({position})")
        self.set_decorated(False)
        self.set_resizable(False)
        
        # Initialize managers
        self._update_manager = UpdateManager()
        self._cache = Cache()
        
        # Set up window
        self._setup_window()
        self._setup_widgets()
        
        # Connect signals
        self.connect('realize', self._on_realize)
        
        # Start geometry updates
        self._update_manager.schedule(
            'geometry',
            self._update_geometry,
            UPDATE_INTERVAL
        )
    
    def _setup_window(self):
        display = self.get_display()
        monitor = display.get_monitors()[0]
        geometry = monitor.get_geometry()
        scale = monitor.get_scale_factor()
        
        self.panel_width = geometry.width
        config = load_config()
        
        # Add extra padding for panels
        base_height = config['panel_height'] * scale
        self.panel_height = base_height + (8 if self.position == 'bottom' else 4)
        
        self.set_size_request(self.panel_width, self.panel_height)
        self.set_default_size(self.panel_width, self.panel_height)
        
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.box.set_margin_start(2)
        self.box.set_margin_end(2)
        self.set_child(self.box)
    
    def _setup_widgets(self):
        """Set up panel widgets based on position"""
        if self.position == 'top':
            self._setup_top_panel()
        else:
            self._setup_bottom_panel()
    
    
    def create_llm_interface_button(self):
        """Create context-aware LLM button with persistent selection state"""
        button = Gtk.Button(label="Ask anything...")
        button.add_css_class('llm-button')
        button.set_hexpand(True)
        button.set_halign(Gtk.Align.CENTER)
        
        context = {
            'window_name': None,
            'selection': None,
            'last_update': 0
        }
        
        def update_context():
            try:
                current_time = time.monotonic()
                if current_time - context['last_update'] < 0.1:
                    return True
                    
                output = subprocess.check_output(['xdotool', 'getactivewindow', 'getwindowname']).decode().strip()
                if output and output != "MAGI Assistant":
                    # Window changed
                    if output != context['window_name']:
                        context['window_name'] = output
                        button.set_label(f"Ask about {context['window_name']}...")
                        with open('/tmp/MAGI/current_context.txt', 'w') as f:
                            f.write(f"Context: Working with {context['window_name']}")
                    
                    try:
                        selection = subprocess.check_output(
                            ['xclip', '-o', '-selection', 'primary'],
                            stderr=subprocess.DEVNULL
                        ).decode().strip()
                        if selection and selection != context['selection']:
                            context['selection'] = selection
                            button.set_label("Ask about selection...")
                            os.makedirs('/tmp/MAGI', exist_ok=True)
                            with open('/tmp/MAGI/current_context.txt', 'w') as f:
                                f.write(f"Context: Selected text in {context['window_name']}:\n{selection}")
                    except subprocess.CalledProcessError:
                        context['selection'] = None
                
                context['last_update'] = current_time
                return True
                
            except Exception as e:
                print(f"Context update error: {e}")
                return True
        
        GLib.timeout_add(250, update_context)
        
        button.connect('clicked', lambda w:
            subprocess.Popen([sys.executable, 
                os.path.join(os.path.dirname(__file__), 'llm_menu.py')]))
        
        return button
    
    def _launch_command(self, command):
        """Launch command with proper display environment"""
        try:
            # Get current display
            display = self.get_display()
            display_name = display.get_name()
            
            # Set up environment with correct display
            env = os.environ.copy()
            env['DISPLAY'] = display_name
            
            # Split command if it's a string
            if isinstance(command, str):
                command = command.split()
            
            # Launch process with correct display
            subprocess.Popen(command, env=env)
        except Exception as e:
            print(f"Launch error: {e}")
    
    def _setup_top_panel(self):
        """Set up top panel widgets"""
        config = load_config()
        
        # Create widgets
        launcher = Gtk.Button(label=" MAGI ")
        launcher.add_css_class('launcher-button')
        launcher.connect('clicked', lambda w: self._launch_command(config['launcher']))
        
        workspace_switcher = WorkspaceSwitcher(self._update_manager)
        window_list = WindowList(self._update_manager)
        monitor = SystemMonitor(self._update_manager)
        
        network = Gtk.Button()
        network.set_child(Gtk.Image.new_from_icon_name("network-wireless-symbolic"))
        network.connect('clicked', lambda w: self._launch_command('nm-connection-editor'))
        
        clock = Gtk.Label()
        clock.add_css_class('clock-label')
        
        def update_clock():
            clock.set_label(time.strftime("%Y-%m-%d %H:%M:%S"))
            return True
        
        update_clock()
        GLib.timeout_add(1000, update_clock)
        
        # Pack widgets
        self.box.append(launcher)
        self.box.append(workspace_switcher)
        self.box.append(window_list)
        self.box.append(monitor)
        self.box.append(network)
        self.box.append(clock)
    
    def _setup_bottom_panel(self):
        """Set up bottom panel widgets with centered buttons"""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_hexpand(True)
        
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.CENTER)
        button_box.set_hexpand(True)
        
        # The keeper of settings
        settings_button = Gtk.Button()
        settings_button.set_child(Gtk.Image.new_from_icon_name("preferences-system-symbolic"))  
        settings_button.connect('clicked', lambda w:
            subprocess.Popen([sys.executable, 
                os.path.join(os.path.dirname(__file__), 'settings.py')]))
        
        # The context-aware question asker
        llm_button = self.create_llm_interface_button()
        
        # The text-to-speech sage
        tts_button = Gtk.Button()
        tts_button.set_child(Gtk.Image.new_from_icon_name("audio-speakers-symbolic"))
        tts_button.connect('clicked', self._speak_selection)
        
        # The quick dictation wizard
        voice_button = VoiceInputButton()
        
        # The independent terminal sage
        assistant_button = Gtk.Button()
        assistant_button.set_child(Gtk.Image.new_from_icon_name("terminal-symbolic"))
        assistant_button.connect('clicked', self._launch_voice_assistant)
        
        # The new whispering ear
        whispering_ear = WhisperingEarButton()
        
        # Arrange the mystical buttons in their proper order
        button_box.append(settings_button)
        button_box.append(llm_button)
        button_box.append(tts_button)
        button_box.append(voice_button)
        button_box.append(assistant_button)
        button_box.append(whispering_ear)
        
        box.append(button_box)
        self.box.append(box)
   
   
    def _launch_voice_assistant(self, button):
        """Launch the voice assistant pipeline directly"""
        try:
            # Get the magi_shell directory path
            magi_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Start ASR process
            asr_path = os.path.join(magi_dir, 'asr.py')
            asr_process = subprocess.Popen(
                [sys.executable, asr_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Start desktop assistant process
            assistant_path = os.path.join(magi_dir, 'desktop_assistant.py')
            assistant_process = subprocess.Popen(
                [sys.executable, assistant_path],
                stdin=asr_process.stdout,
                stderr=subprocess.PIPE
            )
            
            # Close ASR stdout in parent process
            asr_process.stdout.close()
            
            # Store process references for cleanup
            if not hasattr(self, '_assistant_processes'):
                self._assistant_processes = []
            self._assistant_processes.append((asr_process, assistant_process))
            
        except Exception as e:
            print(f"Error launching voice assistant: {e}")
   
    
    def _speak_selection(self, button):
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
    
    def _on_realize(self, widget):
        """Handle window realization"""
        self._update_geometry()
        self._setup_window_properties()
    
    def _setup_window_properties(self):
        """Set up window properties after realization"""
        try:
            window_id = self._get_window_id()
            if window_id:
                # Set window type first
                subprocess.run([
                    'xprop', '-id', window_id,
                    '-f', '_NET_WM_WINDOW_TYPE', '32a',
                    '-set', '_NET_WM_WINDOW_TYPE', '_NET_WM_WINDOW_TYPE_DOCK'
                ], check=True)
                
                # Set struts before other properties
                self._set_geometry(window_id)
                
                # Set window properties after struts
                subprocess.run(['wmctrl', '-i', '-r', window_id, '-b', 'add,sticky,above'], check=True)
                subprocess.run(['wmctrl', '-i', '-r', window_id, '-T', f'MAGI Panel ({self.position})'], check=True)
                
                # Force window manager to acknowledge changes
                subprocess.run(['wmctrl', '-i', '-a', window_id], check=True)
        except Exception as e:
            print(f"Window property setup error: {e}")
    
    def _update_geometry(self):
        """Update panel geometry"""
        if not self.get_realized():
            return
        
        try:
            window_id = self._get_window_id()
            if window_id:
                self._set_geometry(window_id)
        except Exception as e:
            print(f"Geometry update error: {e}")
    
    def _set_geometry(self, window_id):
        """Set window geometry and struts based on actual window size"""
        display = self.get_display()
        monitor = display.get_monitors()[0]
        geometry = monitor.get_geometry()
        scale = monitor.get_scale_factor()
        
        # Get actual window size after rendering
        try:
            output = subprocess.check_output(['xwininfo', '-id', window_id]).decode()
            for line in output.splitlines():
                if 'Height:' in line:
                    actual_height = int(line.split()[-1])
                    break
        except:
            actual_height = self.panel_height
        
        width = geometry.width
        x = geometry.x
        y = geometry.y if self.position == 'top' else geometry.y + geometry.height - actual_height
        
        # Set position and size
        subprocess.run(['xdotool', 'windowmove', window_id, str(x), str(y)])
        subprocess.run(['xdotool', 'windowsize', window_id, str(width), str(actual_height)])
        
        # Set struts with actual height
        if self.position == 'top':
            struts = f'0, 0, {actual_height}, 0, 0, 0, 0, 0, {x}, {x + width}, 0, 0'
        else:
            struts = f'0, 0, 0, {actual_height}, 0, 0, 0, 0, 0, 0, {x}, {x + width}'
        
        subprocess.run([
            'xprop', '-id', window_id,
            '-f', '_NET_WM_STRUT_PARTIAL', '32c',
            '-set', '_NET_WM_STRUT_PARTIAL', struts
        ])
    
    def _set_window_type(self, window_id):
        """Set window type to dock"""
        subprocess.run([
            'xprop', '-id', window_id,
            '-f', '_NET_WM_WINDOW_TYPE', '32a',
            '-set', '_NET_WM_WINDOW_TYPE',
            '_NET_WM_WINDOW_TYPE_DOCK'
        ])
    
    def _get_window_id(self):
        """Get window ID using multiple methods"""
        window_id = self._cache.get('window_id')
        if window_id:
            return window_id
        
        try:
            # Try by PID
            pid = os.getpid()
            output = subprocess.check_output(
                ['xdotool', 'search', '--pid', str(pid), '--class', 'Gtk4Window']
            ).decode().strip()
            
            if output:
                for wid in output.split('\n'):
                    try:
                        info = subprocess.check_output(['xwininfo', '-id', wid]).decode()
                        if f"MAGI Panel ({self.position})" in info:
                            self._cache.set('window_id', wid)
                            return wid
                    except:
                        continue
            
            # Try by title
            output = subprocess.check_output(['wmctrl', '-l']).decode()
            for line in output.splitlines():
                if f"MAGI Panel ({self.position})" in line:
                    wid = line.split()[0]
                    self._cache.set('window_id', wid)
                    return wid
                    
        except Exception as e:
            print(f"Window ID lookup error: {e}")
        
        return None

class MAGIApplication(Adw.Application):
    """Main application class"""
    def __init__(self):
        super().__init__(application_id='com.system.magi.shell')
        
    def do_activate(self):
        """Handle application activation"""
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
    """Main entry point"""
    try:
        app = MAGIApplication()
        
        def cleanup(signum=None, frame=None):
            """Clean up resources"""
            print("\nCleaning up...")
            sys.exit(0)
        
        # Set up signal handlers
        import signal
        signal.signal(signal.SIGINT, cleanup)
        signal.signal(signal.SIGTERM, cleanup)
        
        # Run application
        exit_code = app.run(sys.argv)
        cleanup()
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
