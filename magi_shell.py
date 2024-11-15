#!/usr/bin/env python3


import struct
import array
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

# Performance optimizations
MONITOR_CHECK_INTERVAL = 5000  # Reduce monitor polling to 5 seconds
SYSTEM_STATS_INTERVAL = 3000   # Reduce system stats updates to 3 seconds
CLOCK_UPDATE_INTERVAL = 1000   # Keep clock at 1 second for accuracy

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
    """Create optimized system monitor widget"""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    
    # Use a single label for all stats to reduce widget count
    stats_label = Gtk.Label()
    stats_label.get_style_context().add_class('monitor-label')
    box.pack_start(stats_label, False, False, 2)
    
    # Initialize NVIDIA monitoring
    nvidia_available = False
    try:
        nvmlInit()
        nvidia_handle = nvmlDeviceGetHandleByIndex(0)
        nvidia_available = True
    except:
        print("Warning: NVIDIA GPU monitoring not available")
    
    # Cached psutil CPU percent
    cpu_percent = psutil.cpu_percent()
    last_cpu_update = time.time()
    
    def update_stats():
        nonlocal cpu_percent, last_cpu_update
        try:
            # Update CPU less frequently
            current_time = time.time()
            if current_time - last_cpu_update >= 1:  # Update CPU every second
                cpu_percent = psutil.cpu_percent()
                last_cpu_update = current_time
            
            ram_percent = psutil.virtual_memory().percent
            
            if nvidia_available:
                try:
                    util = nvmlDeviceGetUtilizationRates(nvidia_handle)
                    mem = nvmlDeviceGetMemoryInfo(nvidia_handle)
                    gpu_percent = util.gpu
                    vram_percent = (mem.used / mem.total) * 100
                except:
                    gpu_percent = vram_percent = 0
            else:
                gpu_percent = vram_percent = 0
            
            # Update all stats in a single label update
            stats_label.set_text(
                f"CPU: {cpu_percent:>5.1f}% | RAM: {ram_percent:>5.1f}% | "
                f"GPU: {gpu_percent:>5.1f}% | VRAM: {vram_percent:>5.1f}%"
            )
            
        except Exception as e:
            print(f"Error updating stats: {e}")
        
        return True
    
    update_stats()
    GLib.timeout_add(SYSTEM_STATS_INTERVAL, update_stats)
    return box

def create_network_button():
    """Create network manager button"""
    button = Gtk.Button()
    button.set_relief(Gtk.ReliefStyle.NONE)
    icon = Gtk.Image.new_from_icon_name("network-wireless-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
    button.add(icon)
    button.connect('clicked', lambda w: subprocess.Popen(['nm-connection-editor']))
    return button

def create_clock():
    """Create optimized clock widget"""
    label = Gtk.Label()
    label.get_style_context().add_class('clock-label')
    
    # Pre-calculate format string
    format_str = "%Y-%m-%d %H:%M:%S"
    
    def update_clock():
        try:
            label.set_text(time.strftime(format_str))
            return True
        except:
            return False
    
    update_clock()
    GLib.timeout_add(CLOCK_UPDATE_INTERVAL, update_clock)
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
    button.set_relief(Gtk.ReliefStyle.NONE)
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
    button.set_relief(Gtk.ReliefStyle.NONE)
    stream = None
    record_start_time = 0
    recording = False
    
    # Create icons
    mic_icon = Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
    record_icon = Gtk.Image.new_from_icon_name("media-record-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
    button.add(mic_icon)
    
    def start_recording(*args):
        nonlocal stream, record_start_time, recording
        audio_data.clear()
        record_start_time = time.time()
        recording = True
        
        # Swap to record icon
        button.remove(button.get_child())
        button.add(record_icon)
        button.show_all()
        
        def audio_callback(indata, frames, time, status):
            nonlocal recording
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
        nonlocal stream, record_start_time, recording
        print("DEBUG: Stopping recording")
        recording = False
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
    """Create optimized workspace switcher"""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
    screen = Wnck.Screen.get_default()
    screen.force_update()
    
    # Cache for workspace state
    workspace_cache = {'count': 0, 'active': None}
    
    def update_workspaces(*args):
        try:
            active_space = screen.get_active_workspace()
            workspace_count = screen.get_workspace_count()
            
            # Check if anything changed
            if (workspace_count == workspace_cache['count'] and 
                active_space == workspace_cache['active']):
                return
            
            workspace_cache['count'] = workspace_count
            workspace_cache['active'] = active_space
            
            for child in box.get_children():
                box.remove(child)
            
            for i in range(workspace_count):
                workspace = screen.get_workspace(i)
                button = Gtk.Button(label=str(i + 1))
                if workspace and workspace == active_space:
                    button.get_style_context().add_class('active-workspace')
                button.connect('clicked', lambda w, num=i: switch_to_workspace(num))
                box.pack_start(button, False, False, 0)
            
            box.show_all()
            
        except Exception as e:
            print(f"Error updating workspaces: {e}")
    
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
    """Create optimized window list"""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
    screen = Wnck.Screen.get_default()
    screen.force_update()
    
    # Cache for window titles
    title_cache = {}
    
    def update_window_list(*args):
        # Only update if the box is visible
        if not box.get_visible():
            return
        
        try:
            current_workspace = screen.get_active_workspace()
            
            # Get windows efficiently
            windows = [
                win for win in screen.get_windows() 
                if not win.is_skip_tasklist() and 
                (win.get_workspace() == current_workspace or win.is_pinned())
            ]
            
            # Calculate max width once
            max_chars = max(10, min(30, int(80 / max(1, len(windows)))))
            
            # Remove old buttons
            for child in box.get_children():
                box.remove(child)
            
            # Update window buttons
            for window in windows:
                window_id = window.get_xid()
                
                # Check title cache
                current_title = window.get_name()
                if window_id not in title_cache or title_cache[window_id] != current_title:
                    title_cache[window_id] = current_title
                    if len(current_title) > max_chars:
                        title_cache[window_id] = current_title[:max_chars-3] + "..."
                
                button = Gtk.Button(label=title_cache[window_id])
                
                if window.is_active():
                    button.get_style_context().add_class('active-window')
                
                button.connect('clicked', lambda w, win=window: win.activate(GLib.get_current_time()))
                box.pack_start(button, False, False, 0)
            
            box.show_all()
            
        except Exception as e:
            print(f"Error updating window list: {e}")
    
    # Optimize event connections
    screen.connect('window-opened', update_window_list)
    screen.connect('window-closed', update_window_list)
    screen.connect('active-window-changed', update_window_list)
    screen.connect('active-workspace-changed', update_window_list)
    
    # Initial update
    GLib.idle_add(update_window_list)
    return box

def create_panel(position='top'):
    """Create GPU-accelerated panel with proper multi-monitor positioning"""
    window = Gtk.Window.new(Gtk.WindowType.TOPLEVEL)
    window.set_type_hint(Gdk.WindowTypeHint.DOCK)
    window.set_visual(window.get_screen().get_rgba_visual())
    os.environ['GDK_BACKEND'] = 'gl'
    
    window.set_decorated(False)
    window.set_app_paintable(True)
    window.set_accept_focus(False)
    window.set_resizable(False)
    window.stick()
    window.set_keep_above(True)
    
    last_draw_time = 0
    UPDATE_INTERVAL = 1.0  # 1 FPS
    
    def on_draw(widget, ctx):
        nonlocal last_draw_time
        current_time = time.time()
        
        if current_time - last_draw_time < UPDATE_INTERVAL:
            return False
            
        last_draw_time = current_time
        
        # GPU-optimized drawing
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.push_group()
        ctx.set_source_rgba(0.10, 0.11, 0.15, 0.95)
        ctx.paint()
        ctx.pop_group_to_source()
        ctx.paint()
        return False
    
    def force_redraw(*args):
        nonlocal last_draw_time
        last_draw_time = 0
        window.queue_draw()
    
    def update_geometry(*args):
        if hasattr(window, '_geometry_update_pending'):
            return False
            
        window._geometry_update_pending = True
        
        def do_update():
            try:
                display = Gdk.Display.get_default()
                primary = display.get_primary_monitor()
                geometry = primary.get_geometry()
                scale = primary.get_scale_factor()
                
                width = geometry.width // scale
                height = config['panel_height']
                x = geometry.x // scale
                
                if position == 'top':
                    y = geometry.y // scale
                else:
                    y = (geometry.y + geometry.height) // scale - height
                    
                # Block redrawing during updates
                window.set_opacity(0)
                window.move(x, y)
                window.set_size_request(width, height)
                window.resize(width, height)
                window.set_opacity(1)
                
                if window.get_window():
                    xid = window.get_window().get_xid()
                    if position == 'top':
                        subprocess.run(['xprop', '-id', str(xid),
                                      '-f', '_NET_WM_STRUT_PARTIAL', '32c',
                                      '-set', '_NET_WM_STRUT_PARTIAL',
                                      f'0, 0, {height}, 0, 0, 0, 0, 0, {x}, {x + width}, 0, 0'])
                    else:
                        subprocess.run(['xprop', '-id', str(xid),
                                      '-f', '_NET_WM_STRUT_PARTIAL', '32c',
                                      '-set', '_NET_WM_STRUT_PARTIAL',
                                      f'0, 0, 0, {height}, 0, 0, 0, 0, 0, 0, {x}, {x + width}'])
            finally:
                window._geometry_update_pending = False
            return False
            
        GLib.idle_add(do_update)
        return False
    
    window.connect('draw', on_draw)
    window.connect('button-press-event', force_redraw)
    window.connect('button-release-event', force_redraw)
    
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
    window.add(box)
    
    GLib.timeout_add(1000, update_geometry)
    display = Gdk.Display.get_default()
    display.connect('monitor-added', update_geometry)
    display.connect('monitor-removed', update_geometry)
    
    return window, box

def setup_panels():
    """Initialize panel layout with performance optimizations"""
    global panels
    
    if panels:
        print("Warning: Panels already initialized")
        return panels
    
    # Initialize NVIDIA for GPU monitoring
    try:
        nvmlInit()
        nvidia_handle = nvmlDeviceGetHandleByIndex(0)
    except Exception as e:
        print(f"NVIDIA init error: {e}")
        nvidia_handle = None
    
    # Create panels
    top_panel, top_box = create_panel('top')
    bottom_panel, bottom_box = create_panel('bottom')
    
    # Create and pack top panel components
    components = {
        'launcher': create_launcher_button(),
        'workspace': create_workspace_switcher(),
        'windows': create_window_list(),
        'monitor': create_system_monitor(),
        'network': create_network_button(),
        'clock': create_clock()
    }
    
    # Block redraws during component addition
    top_panel.set_opacity(0)
    top_box.pack_start(components['launcher'], False, False, 0)
    top_box.pack_start(components['workspace'], False, False, 2)
    top_box.pack_start(components['windows'], True, True, 0)
    top_box.pack_end(components['monitor'], False, False, 2)
    top_box.pack_end(components['network'], False, False, 2)
    top_box.pack_end(components['clock'], False, False, 5)
    top_panel.set_opacity(1)
    
    # Create and pack bottom panel components
    center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    llm_button = create_llm_interface_button()
    tts_button = create_tts_button()
    voice_button = create_voice_input()
    
    bottom_panel.set_opacity(0)
    bottom_box.pack_start(center_box, True, True, 0)
    center_box.set_center_widget(llm_button)
    bottom_box.pack_end(tts_button, False, False, 2)
    bottom_box.pack_end(voice_button, False, False, 2)
    bottom_panel.set_opacity(1)
    
    top_panel.show_all()
    bottom_panel.show_all()
    
    panels = {'top': top_panel, 'bottom': bottom_panel}
    return panels

def draw_panel_background(widget, ctx):
    """Draw panel background with Tokyo Night colors"""
    ctx.set_source_rgba(0.10, 0.11, 0.15, 0.95)  # #1a1b26 with 0.95 alpha
    ctx.set_operator(cairo.OPERATOR_SOURCE)
    ctx.paint()
    return False


def setup_styles():
    css = b"""
    button {
        background: none;
        color: #7aa2f7;
        border: 1px solid #7aa2f7;
        border-radius: 12px;
        padding: 8px 20px;
        font-size: 15px
    }

    button:hover {
        border-color: #88b0ff;
        color: #88b0ff
    }

    button:active {
        border-color: #6992e3;
        color: #6992e3
    }

    button image {
        color: #7aa2f7
    }

    button:hover image {
        color: #88b0ff
    }

    button:active image {
        color: #6992e3
    }

    .monitor-label {
        font-family: monospace;
        padding: 0 4px;
        min-width: 100px;
        color: #c0caf5;
        font-weight: 500;
        text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.3);
    }

    .clock-label {
    font-family: monospace;
    padding: 0 4px;
    min-width: 180px;
    color: #c0caf5;  /* Tokyo Night foreground color - a light blue-white */
    font-weight: 500;  /* Medium weight for better visibility */
    text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.3);  /* Optional: adds a subtle shadow for better readability */
    }

    .recording {
        border: 2px solid #f7768e;
        background: none
    }

    .recording image {
        color: #f7768e
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
