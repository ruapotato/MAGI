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
            "whisper_endpoint": "http://localhost:9000/asr",
            "sample_rate": 16000
        }
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Warning: Could not save config: {e}")

def create_system_monitor():
    """Create system monitor widget"""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    
    # CPU and RAM labels
    cpu_label = Gtk.Label()
    ram_label = Gtk.Label()
    gpu_label = Gtk.Label()
    vram_label = Gtk.Label()
    
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
        
        cpu_label.set_text(f"CPU: {cpu_percent:.1f}%")
        ram_label.set_text(f"RAM: {ram_percent:.1f}%")
        gpu_label.set_text(f"GPU: {gpu_percent:.1f}%")
        vram_label.set_text(f"VRAM: {vram_percent:.1f}%")
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
    """Create a clock widget"""
    label = Gtk.Label()
    
    def update_clock():
        label.set_text(time.strftime("%Y-%m-%d %H:%M:%S"))
        return True
    
    update_clock()
    GLib.timeout_add(1000, update_clock)
    return label

def create_llm_interface():
    """Create LLM interface using Ollama"""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    
    entry = Gtk.Entry()
    entry.set_placeholder_text("Ask anything...")
    entry.set_size_request(300, -1)
    
    response_label = Gtk.Label()
    response_label.set_line_wrap(True)
    response_label.set_size_request(400, -1)
    
    def send_to_ollama(prompt):
        try:
            response = requests.post('http://localhost:11434/api/generate',
                                   json={'model': config['ollama_model'],
                                        'prompt': prompt})
            if response.ok:
                GLib.idle_add(response_label.set_text, response.json().get('response', 'No response'))
        except Exception as e:
            GLib.idle_add(response_label.set_text, f"Error: {str(e)}")
    
    def on_enter(widget, event):
        if event.keyval == Gdk.KEY_Return:
            prompt = entry.get_text()
            threading.Thread(target=send_to_ollama, args=(prompt,)).start()
            entry.set_text("")
    
    entry.connect('key-press-event', on_enter)
    
    box.pack_start(entry, False, False, 2)
    box.pack_start(response_label, True, True, 2)
    return box

def create_tts_button():
    """Create text-to-speech button"""
    button = Gtk.Button(label="🔊")
    
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
    """Create voice input button"""
    button = Gtk.Button(label="🎤")
    
    def on_press(*args):
        global recording, audio_data
        recording = True
        audio_data = []
        
        def audio_callback(indata, frames, time, status):
            if recording:
                audio_data.append(indata.copy())
        
        # Start recording
        stream = sd.InputStream(callback=audio_callback,
                              channels=1,
                              samplerate=config['sample_rate'])
        stream.start()
    
    def on_release(*args):
        global recording
        recording = False
        
        if audio_data:
            # Combine audio chunks
            audio = np.concatenate(audio_data)
            
            # Send to whisper service
            try:
                files = {'audio': ('audio.wav', audio.tobytes())}
                response = requests.post(config['whisper_endpoint'], files=files)
                if response.ok:
                    print(f"Transcribed: {response.json().get('text', '')}")
            except Exception as e:
                print(f"Whisper Error: {e}")
    
    button.connect('pressed', on_press)
    button.connect('released', on_release)
    return button

def create_panel(position='top'):
    """Create a basic panel window"""
    window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    window.set_type_hint(Gdk.WindowTypeHint.DOCK)
    
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
    
    # Add LLM interface
    llm_interface = create_llm_interface()
    bottom_box.pack_start(llm_interface, True, True, 2)
    
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
        for child in box.get_children():
            box.remove(child)
        
        for window in screen.get_windows():
            if not window.is_skip_tasklist():
                button = Gtk.Button(label=window.get_name()[:30])
                button.connect('clicked', lambda w, win=window: win.activate(GLib.get_current_time()))
                box.pack_start(button, False, False, 0)
        box.show_all()
    
    screen.connect('window-opened', update_window_list)
    screen.connect('window-closed', update_window_list)
    screen.connect('window-stacking-changed', update_window_list)
    
    GLib.idle_add(update_window_list)
    return box

def draw_panel_background(widget, ctx):
    """Draw semi-transparent panel background"""
    ctx.set_source_rgba(0.2, 0.2, 0.2, 0.85)
    ctx.set_operator(cairo.OPERATOR_SOURCE)
    ctx.paint()
    return False

def setup_styles():
    """Set up CSS styles"""
    css = b"""
    .launcher-button {
        background-color: #215d9c;
        color: white;
        padding: 0 10px;
    }
    .launcher-button:hover {
        background-color: #2c7bd3;
    }
    .active-workspace {
        background-color: #215d9c;
        color: white;
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
