#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Wnck', '3.0')
from gi.repository import Gtk, Gdk, Wnck, GLib, GObject
import json
import os
import subprocess
import time
import sys
import cairo
import psutil
import threading
import requests
import numpy as np
import sounddevice as sd
from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo, nvmlDeviceGetUtilizationRates

# Global state
windows = {}
ai_predictions = {}
panels = {}
config = None
recording = False
audio_data = []

def check_x11():
    """Ensure we have a valid X11 connection"""
    display = Gdk.Display.get_default()
    if not display:
        print("Error: Cannot connect to X display")
        sys.exit(1)
    return display

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

def create_system_monitor():
    """Create system monitor widget with fixed-width labels"""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    
    # CPU and RAM labels with monospace font and fixed width
    cpu_label = Gtk.Label()
    ram_label = Gtk.Label()
    gpu_label = Gtk.Label()
    vram_label = Gtk.Label()
    
    # Set monospace font and fixed width for all labels
    for label in [cpu_label, ram_label, gpu_label, vram_label]:
        label.get_style_context().add_class('monitor-label')
    
    box.pack_start(cpu_label, False, False, 2)
    box.pack_start(ram_label, False, False, 2)
    box.pack_start(gpu_label, False, False, 2)
    box.pack_start(vram_label, False, False, 2)
    
    def update_stats():
        # CPU and RAM
        cpu_percent = psutil.cpu_percent()
        ram_percent = psutil.virtual_memory().percent
        
        # GPU stats via NVIDIA
        try:
            handle = nvmlDeviceGetHandleByIndex(0)
            util = nvmlDeviceGetUtilizationRates(handle)
            mem = nvmlDeviceGetMemoryInfo(handle)
            gpu_percent = util.gpu
            vram_percent = (mem.used / mem.total) * 100
        except:
            gpu_percent = 0
            vram_percent = 0
        
        # Format with fixed width
        cpu_label.set_text(f"CPU: {cpu_percent:>5.1f}%")
        ram_label.set_text(f"RAM: {ram_percent:>5.1f}%")
        gpu_label.set_text(f"GPU: {gpu_percent:>5.1f}%")
        vram_label.set_text(f"VRAM: {vram_percent:>5.1f}%")
        return True
    
    # Initialize NVIDIA Management Library
    try:
        nvmlInit()
    except:
        print("Warning: NVIDIA GPU monitoring not available")
    
    update_stats()
    GLib.timeout_add(2000, update_stats)
    return box

def create_network_button():
    """Create network manager button"""
    button = Gtk.Button(label="🌐")
    button.connect('clicked', lambda w: subprocess.Popen(['nm-connection-editor']))
    return button

def create_clock():
    """Create a clock widget with fixed width"""
    label = Gtk.Label()
    label.get_style_context().add_class('clock-label')
    
    def update_clock():
        # Use monospace font and fixed width format
        label.set_text(time.strftime("%Y-%m-%d %H:%M:%S"))
        return True
    
    update_clock()
    GLib.timeout_add(1000, update_clock)
    return label

def create_llm_interface_button():
    """Create context-aware LLM button that launches menu"""
    button = Gtk.Button()
    button.set_relief(Gtk.ReliefStyle.NONE)
    context_label = Gtk.Label("Ask anything...")
    button.add(context_label)
    
    # Keep track of the current window and selection state
    current_state = {
        'window_name': None,
        'has_selection': False,
        'last_selection': None
    }
    
    def handle_window_change(window_name):
        """Handle window context changes"""
        # Ignore the MAGI Assistant window
        if window_name == "MAGI Assistant":
            return
            
        current_state['window_name'] = window_name
        current_state['has_selection'] = False
        current_state['last_selection'] = None
        context_label.set_text(f"Ask anything about {window_name}...")
        
        # Save window context
        os.makedirs('/tmp/MAGI', exist_ok=True)
        with open('/tmp/MAGI/current_context.txt', 'w') as f:
            f.write(f"Context: User is working with {window_name}")
    
    def handle_selection_change(window_name, selected_text):
        """Handle selection changes within the same window"""
        # Ignore the MAGI Assistant window
        if window_name == "MAGI Assistant":
            return
            
        if (window_name == current_state['window_name'] and 
            selected_text and 
            selected_text != current_state['last_selection']):
            current_state['has_selection'] = True
            current_state['last_selection'] = selected_text
            context_label.set_text("Ask anything about your selection...")
            
            # Save selection context
            with open('/tmp/MAGI/current_context.txt', 'w') as f:
                f.write(f"Context: User has selected the following text in {window_name}:\n{selected_text}")
    
    def update_context(*args):
        """Update context and save to file"""
        screen = Wnck.Screen.get_default()
        active_window = screen.get_active_window()
        
        if active_window:
            window_name = active_window.get_name()
            
            # Check if window changed
            if window_name != current_state['window_name']:
                handle_window_change(window_name)
            else:
                # Only check selection if we're in the same window
                clipboard = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
                selected_text = clipboard.wait_for_text()
                handle_selection_change(window_name, selected_text)
        else:
            current_state['window_name'] = None
            current_state['has_selection'] = False
            current_state['last_selection'] = None
            context_label.set_text("Ask anything...")
            
            # Clear context
            with open('/tmp/MAGI/current_context.txt', 'w') as f:
                f.write("")
    
    def on_button_clicked(widget):
        # Launch the menu app without updating context
        subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), 'llm_menu.py')])
    
    button.connect('clicked', on_button_clicked)
    
    # Monitor active window changes
    screen = Wnck.Screen.get_default()
    screen.connect('active-window-changed', update_context)
    
    # Monitor clipboard for selection changes
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
    clipboard.connect('owner-change', update_context)
    
    # Initialize context
    update_context()
    
    return button

def create_tts_button():
    """Create text-to-speech button"""
    button = Gtk.Button()
    icon = Gtk.Image.new_from_icon_name("audio-speakers-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
    button.add(icon)
    
    def speak_selection(*args):
        try:
            # Get clipboard contents
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
            text = clipboard.wait_for_text()
            if text:
                subprocess.Popen(['espeak', text])
        except Exception as e:
            print(f"TTS Error: {e}")
    
    button.connect('clicked', speak_selection)
    return button

def create_voice_input():
    """Create voice input button that sends to Whisper server"""
    button = Gtk.Button()
    stream = None
    record_start_time = 0
    recording = False  # Add this line to define the recording variable
    
    # Create icons
    mic_icon = Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
    record_icon = Gtk.Image.new_from_icon_name("media-record-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
    button.add(mic_icon)
    
    def start_recording(*args):
        nonlocal stream, record_start_time, recording  # Add 'recording' here
        audio_data.clear()
        record_start_time = time.time()
        recording = True  # Set recording to True when starting
        
        # Swap to record icon
        button.remove(button.get_child())
        button.add(record_icon)
        button.show_all()
        
        def audio_callback(indata, frames, time, status):
            nonlocal recording  # Add this line to access the 'recording' variable
            if recording:
                audio_data.append(indata.copy())
        
        try:
            stream = sd.InputStream(
                callback=audio_callback,
                channels=1,
                samplerate=16000,
                blocksize=1024,
                dtype=np.float32
            )
            stream.start()
            GLib.idle_add(lambda: button.get_style_context().add_class('recording'))
            print("DEBUG: Recording stream started")
        except Exception as e:
            print(f"Recording Error: {e}")
            recording = False
            GLib.idle_add(lambda: button.get_style_context().remove_class('recording'))
            # Swap back to mic icon
            button.remove(button.get_child())
            button.add(mic_icon)
            button.show_all()
    
    def stop_recording(*args):
        nonlocal stream, record_start_time, recording  # Add 'recording' here
        print("DEBUG: Stopping recording")
        recording = False  # Set recording to False when stopping
        recording_duration = time.time() - record_start_time
        
        # Swap back to mic icon
        button.remove(button.get_child())
        button.add(mic_icon)
        button.show_all()
        
        try:
            if stream:
                stream.stop()
                stream.close()
                stream = None
            GLib.idle_add(lambda: button.get_style_context().remove_class('recording'))
            
            # Check if the recording was too short
            if recording_duration < 0.5:
                print("DEBUG: Recording too short, playing help message")
                subprocess.Popen(['espeak', "Press and hold to record audio"])
                return
            
            if audio_data:
                print(f"DEBUG: Got {len(audio_data)} chunks of audio data")
                audio = np.concatenate(audio_data)
                print(f"DEBUG: Concatenated audio shape: {audio.shape}")
                
                def transcribe():
                    try:
                        print("DEBUG: Starting transcription request")
                        files = {'audio': ('audio.wav', audio.tobytes())}
                        response = requests.post('http://localhost:5000/transcribe', files=files)
                        print(f"DEBUG: Got response status {response.status_code}")
                        
                        if response.ok:
                            text = response.json().get('transcription', '')
                            print(f"DEBUG: Got transcription: {text}")
                            subprocess.run(['xdotool', 'type', text], check=True)
                            print("DEBUG: Typed transcription")
                        else:
                            print(f"Server Error: {response.status_code}")
                    except Exception as e:
                        print(f"Transcription Error: {e}")
                        import traceback
                        traceback.print_exc()
                
                threading.Thread(target=transcribe, daemon=True).start()
            else:
                print("DEBUG: No audio data collected")
                
        except Exception as e:
            print(f"Audio Processing Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            GLib.idle_add(lambda: button.get_style_context().remove_class('recording'))
    
    button.connect('pressed', start_recording)
    button.connect('released', stop_recording)
    
    return button

def create_launcher_button():
    """Create the main menu button"""
    button = Gtk.Button(label=" MAGI ")
    button.connect('clicked', lambda w: launch_menu())
    button.get_style_context().add_class('launcher-button')
    return button

def launch_menu():
    """Launch the application menu"""
    try:
        subprocess.Popen(config['launcher'].split())
    except Exception as e:
        print(f"Error launching menu: {e}")

def create_workspace_switcher():
    """Create the workspace switcher"""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
    screen = Wnck.Screen.get_default()
    screen.force_update()
    
    def update_workspaces(*args):
        for child in box.get_children():
            box.remove(child)
        
        active_space = screen.get_active_workspace()
        for i in range(screen.get_workspace_count()):
            workspace = screen.get_workspace(i)
            button = Gtk.Button(label=str(i + 1))
            if workspace and workspace == active_space:
                button.get_style_context().add_class('active-workspace')
            button.connect('clicked', lambda w, num=i: switch_to_workspace(num))
            box.pack_start(button, False, False, 0)
        box.show_all()
    
    screen.connect('workspace-created', update_workspaces)
    screen.connect('workspace-destroyed', update_workspaces)
    screen.connect('active-workspace-changed', update_workspaces)
    
    update_workspaces()
    return box

def switch_to_workspace(num):
    """Switch to a specific workspace"""
    screen = Wnck.Screen.get_default()
    workspace = screen.get_workspace(num)
    if workspace:
        workspace.activate(GLib.get_current_time())

def create_window_list():
    """Create the window list for the panel"""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
    screen = Wnck.Screen.get_default()
    screen.force_update()
    
    def update_window_list(*args):
        # Clear existing buttons
        for child in box.get_children():
            box.remove(child)
        
        # Get current workspace
        current_workspace = screen.get_active_workspace()
        
        # Get all windows on current workspace
        windows = [win for win in screen.get_windows() 
                  if not win.is_skip_tasklist() and 
                  (win.get_workspace() == current_workspace or win.is_pinned())]
        
        # Calculate max width based on number of windows
        max_chars = max(10, min(30, int(80 / max(1, len(windows)))))
        
        for window in windows:
            # Truncate window title
            title = window.get_name()
            if len(title) > max_chars:
                title = title[:max_chars-3] + "..."
            
            button = Gtk.Button(label=title)
            
            # Add active class if window is active
            if window.is_active():
                button.get_style_context().add_class('active-window')
            
            button.connect('clicked', lambda w, win=window: win.activate(GLib.get_current_time()))
            box.pack_start(button, False, False, 0)
        
        box.show_all()
    
    screen.connect('window-opened', update_window_list)
    screen.connect('window-closed', update_window_list)
    screen.connect('window-stacking-changed', update_window_list)
    screen.connect('active-window-changed', update_window_list)
    screen.connect('active-workspace-changed', update_window_list)
    
    GLib.idle_add(update_window_list)
    return box

def create_panel(position='top'):
    """Create a basic panel window"""
    window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    window.set_type_hint(Gdk.WindowTypeHint.DOCK)
    window.set_accept_focus(False)  # Don't accept focus by default
    
    def update_panel_geometry(*args):
        screen = window.get_screen()
        primary_monitor = screen.get_primary_monitor()
        geometry = screen.get_monitor_geometry(primary_monitor)
        
        width = geometry.width
        height = config['panel_height']
        x_offset = geometry.x
        y_offset = geometry.y
        
        if position == 'top':
            window.move(x_offset, y_offset)
        else:
            window.move(x_offset, y_offset + geometry.height - height)
        
        window.set_size_request(width, height)
    
    update_panel_geometry()
    window.set_decorated(False)
    window.stick()
    window.set_keep_above(True)
    
    screen = window.get_screen()
    visual = screen.get_rgba_visual()
    if visual and screen.is_composited():
        window.set_visual(visual)
        window.set_app_paintable(True)
    
    window.connect('draw', draw_panel_background)
    screen.connect('monitors-changed', update_panel_geometry)
    screen.connect('size-changed', update_panel_geometry)
    
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
    window.add(box)
    
    return window, box

def draw_panel_background(widget, ctx):
    """Draw panel background with Tokyo Night colors"""
    ctx.set_source_rgba(0.10, 0.11, 0.15, 0.95)  # #1a1b26 with 0.95 alpha
    ctx.set_operator(cairo.OPERATOR_SOURCE)
    ctx.paint()
    return False

def setup_panels():
    """Initialize panel layout"""
    global panels
    
    # Create top panel
    top_panel, top_box = create_panel('top')
    
    # Add launcher button
    launcher = create_launcher_button()
    top_box.pack_start(launcher, False, False, 0)
    
    # Add workspace switcher to top
    workspace_switcher = create_workspace_switcher()
    top_box.pack_start(workspace_switcher, False, False, 2)
    
    # Add window list
    window_list = create_window_list()
    top_box.pack_start(window_list, True, True, 0)
    
    # Add system monitor
    sys_monitor = create_system_monitor()
    top_box.pack_end(sys_monitor, False, False, 2)
    
    # Add network button
    network_btn = create_network_button()
    top_box.pack_end(network_btn, False, False, 2)
    
    # Add clock
    clock = create_clock()
    top_box.pack_end(clock, False, False, 5)
    
    # Create bottom panel
    bottom_panel, bottom_box = create_panel('bottom')
    
    # Create a container for centered content
    center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    bottom_box.pack_start(center_box, True, True, 0)
    
    # Add LLM interface button centered
    llm_button = create_llm_interface_button()
    center_box.set_center_widget(llm_button)
    
    # Add TTS button
    tts_button = create_tts_button()
    bottom_box.pack_end(tts_button, False, False, 2)
    
    # Add voice input button
    voice_button = create_voice_input()
    bottom_box.pack_end(voice_button, False, False, 2)
    
    # Show panels
    top_panel.show_all()
    bottom_panel.show_all()
    
    panels = {'top': top_panel, 'bottom': bottom_panel}
    return panels

def setup_styles():
    css = b"""
    .launcher-button {
        background: linear-gradient(135deg, #7aa2f7, #2ac3de);
        color: #1a1b26;
        border: none;
        border-radius: 12px;
        padding: 0 10px;
        font-weight: 600;
    }
    
    .launcher-button:hover {
        background: linear-gradient(135deg, #88b0ff, #33d1ed);
    }
    
    .launcher-button:active {
        background: linear-gradient(135deg, #6992e3, #29b2cc);
    }
    
    .active-workspace {
        background: linear-gradient(135deg, #7aa2f7, #2ac3de);
        color: #1a1b26;
        border: none;
        border-radius: 8px;
    }
    
    .active-window {
        background: linear-gradient(135deg, #7aa2f7, #2ac3de);
        color: #1a1b26;
        border: none;
    }
    
    button {
    background: #292e42;
    color: #7aa2f7;  /* Change the color to blue */
    border: 1px solid #3b4261;
    border-radius: 8px;
    padding: 2px 8px;
    }

    button:hover {
        background: #343b58;
        border-color: #7aa2f7;
        color: #a9c0ff;  /* Lighter blue on hover */
    }

    button:active {
        background: #1a1b26;
        color: #6b8ee6;  /* Darker blue when active */
    }
        
    label {
        color: #c0caf5;
    }
    
    .monitor-label {
        font-family: monospace;
        padding: 0 4px;
        min-width: 100px;
    }
    
    .clock-label {
        font-family: monospace;
        padding: 0 4px;
        min-width: 180px;
    }
    
    .recording {
        background-color: #f7768e;
        border: 2px solid #ff99a3;
        color: white;  /* White icon when recording */
    }
    """
    style_provider = Gtk.CssProvider()
    style_provider.load_from_data(css)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        style_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

def main():
    # Check X11 first
    display = check_x11()
    
    # Load configuration
    load_config()
    
    # Initialize Wnck with retry
    screen = None
    for _ in range(5):  # Try 5 times
        try:
            screen = Wnck.Screen.get_default()
            screen.force_update()
            break
        except Exception:
            time.sleep(1)
    
    if not screen:
        print("Error: Could not initialize window manager connection")
        sys.exit(1)
    
    # Set up CSS styles
    setup_styles()
    
    # Set up panels
    global panels
    panels = setup_panels()
    
    # Start GTK main loop
    try:
        Gtk.main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
