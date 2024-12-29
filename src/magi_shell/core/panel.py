#!/usr/bin/env python3
# src/magi_shell/core/panel.py
"""
Core panel implementation for MAGI Shell.

Provides the main panel window class that forms the foundation of
both the top and bottom panels in the MAGI Shell interface.
"""

print("Loading panel.py")

print("Importing gi...")
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GLib, Adw
print("Imported gi successfully")

print("Importing standard libraries...")
import os
import subprocess
import sys
import time
print("Imported standard libraries successfully")

print("Importing MAGI utils...")
try:
    from magi_shell.utils.cache import Cache
    print("Imported Cache")
    from magi_shell.utils.update import UpdateManager
    print("Imported UpdateManager")
    from magi_shell.utils.config import load_config
    print("Imported load_config")
except Exception as e:
    print(f"Error importing utils: {e}")
    raise

print("Importing MAGI widgets...")
try:
    from magi_shell.widgets.workspace import WorkspaceSwitcher
    from magi_shell.widgets.window import WindowList
    from magi_shell.widgets.system import SystemMonitor
    from magi_shell.widgets.voice import WhisperingEarButton, VoiceInputButton
    print("Imported widgets successfully")
except Exception as e:
    print(f"Error importing widgets: {e}")
    raise

print("Importing theme manager...")
try:
    from .theme import ThemeManager
    print("Imported ThemeManager")
except Exception as e:
    print(f"Error importing ThemeManager: {e}")
    raise

print("Starting MAGIPanel class definition...")

class MAGIPanel(Gtk.ApplicationWindow):
    """
    Main panel window implementation.
    
    Creates either a top or bottom panel with appropriate widgets and
    maintains its position and properties. Handles window management,
    workspace switching, system monitoring, and voice input.
    
    Attributes:
        position (str): Panel position ('top' or 'bottom')
        _update_manager: UpdateManager instance
        _cache: Cache instance for panel state
        panel_width (int): Panel width in pixels
        panel_height (int): Panel height in pixels
    """
    
    def __init__(self, app, position='top'):
        print("Initializing MAGIPanel...")
        super().__init__(application=app)
        
        from magi_shell.utils.config import load_config  # Import inside the method
        print("Loading config...")
        self.config = load_config()  # Load config in init
        print(f"Config loaded: {self.config}")

        ThemeManager().register_window(self)
        
        self.position = position
        self.set_title(f"MAGI Panel ({position})")
        self.set_decorated(False)
        self.set_resizable(False)
        
        self._update_manager = UpdateManager()
        self._cache = Cache()
        
        print("Setting up window...")
        self._setup_window()
        print("Setting up widgets...")
        self._setup_widgets()
        
        self.connect('realize', self._on_realize)
        
        self._update_manager.schedule(
            'geometry',
            self._update_geometry,
            1000
        )
        print("MAGIPanel initialization complete")
    
    def create_llm_interface_button(self):
        """Create the AI interface button with context awareness."""
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
                    
                output = subprocess.check_output(
                    ['xdotool', 'getactivewindow', 'getwindowname']
                ).decode().strip()
                
                if output and output != "MAGI Assistant":
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
                                f.write(
                                    f"Context: Selected text in {context['window_name']}:"
                                    f"\n{selection}"
                                )
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
    
    def _setup_widgets(self):
        """Set up panel widgets based on position."""
        if self.position == 'top':
            self._setup_top_panel()
        else:
            self._setup_bottom_panel()
    def _setup_launcher(self):
        """Initialize application launcher."""
        from .launcher import MAGILauncher  # Import at top of file
        self._launcher = MAGILauncher(self)
    
    def _setup_top_panel(self):
        """Set up top panel widgets."""
        launcher = Gtk.Button(label=" MAGI ")
        launcher.add_css_class('launcher-button')
        launcher.connect('clicked', lambda w: subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), 'launcher.py')]))
        
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
        """Set up bottom panel widgets with centered buttons."""
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
                os.path.join(os.path.dirname(__file__), '../../settings.py')]))
        
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

    def _launch_command(self, command):
        """Launch command with proper display environment."""
        try:
            display = self.get_display()
            display_name = display.get_name()
            
            env = os.environ.copy()
            env['DISPLAY'] = display_name
            
            if isinstance(command, str):
                command = command.split()
            
            subprocess.Popen(command, env=env)
        except Exception as e:
            print(f"Launch error: {e}")

    def create_llm_interface_button(self):
        """Create the AI interface button with context awareness."""
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
                    
                output = subprocess.check_output(
                    ['xdotool', 'getactivewindow', 'getwindowname']
                ).decode().strip()
                
                if output and output != "MAGI Assistant":
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
                                f.write(
                                    f"Context: Selected text in {context['window_name']}:"
                                    f"\n{selection}"
                                )
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
                os.path.join(os.path.dirname(__file__), '../../magi_shell/llm_menu.py')]))
        
        return button

    def _speak_selection(self, button):
        """Handle TTS button click."""
        try:
            clipboard = self.get_display().get_primary_clipboard()
            clipboard.read_text_async(None, self._handle_clipboard_text)
        except Exception as e:
            print(f"TTS Error: {e}")
    
    def _handle_clipboard_text(self, clipboard, result):
        """Handle clipboard text for TTS."""
        try:
            text = clipboard.read_text_finish(result)
            if text:
                subprocess.Popen(['magi_espeak', text])
        except Exception as e:
            print(f"TTS Error: {e}")

    def _launch_voice_assistant(self, button):
        """Launch the voice assistant pipeline."""
        try:
            # Get the magi_shell directory path
            magi_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Start ASR process
            asr_path = os.path.join(magi_dir, '../../utils/asr.py')
            asr_process = subprocess.Popen(
                [sys.executable, asr_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Start desktop assistant process
            assistant_path = os.path.join(magi_dir, '../desktop_assistant.py')
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


    def _check_monitor_changes(self):
        """Periodically check for monitor changes."""
        display = self.get_display()
        current_monitor = display.get_primary_monitor()
        
        # Check if monitor geometry has changed
        if hasattr(self, '_last_monitor_geometry'):
            current_geometry = current_monitor.get_geometry()
            if (current_geometry.width != self._last_monitor_geometry.width or
                current_geometry.height != self._last_monitor_geometry.height or
                current_geometry.x != self._last_monitor_geometry.x or
                current_geometry.y != self._last_monitor_geometry.y):
                self._update_geometry()
        
        # Store current geometry for next comparison
        self._last_monitor_geometry = current_monitor.get_geometry()
        
        return True  # Keep the timeout active

    def _on_realize(self, widget):
        """Handle window realization."""
        self._update_geometry()
        self._setup_window_properties()
        
        # Set up monitor change handling through display object
        display = self.get_display()
        
        # Instead of trying to connect to signals, we'll use a periodic check
        # This is a more reliable fallback approach
        GLib.timeout_add(2000, self._check_monitor_changes)
    
    def _setup_window(self):
        """Set up the panel window geometry and basic container."""
        display = self.get_display()
        primary_monitor = display.get_primary_monitor()  # GTK4's method for getting primary monitor
        
        geometry = primary_monitor.get_geometry()
        scale = primary_monitor.get_scale_factor()
        
        self.panel_width = geometry.width
        
        # Use the config loaded in __init__
        base_height = self.config['panel_height'] * scale
        self.panel_height = base_height + (8 if self.position == 'bottom' else 4)
        
        self.set_size_request(self.panel_width, self.panel_height)
        self.set_default_size(self.panel_width, self.panel_height)
        
        # Store monitor info for later use
        self._monitor = primary_monitor
        
        # Create main container box
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.box.set_margin_start(2)
        self.box.set_margin_end(2)
        self.set_child(self.box)
    
    
    def _setup_window_properties(self):
        """Set up window properties after realization."""
        try:
            window_id = self._get_window_id()
            if window_id:
                # Set window type first
                subprocess.run([
                    'xprop', '-id', window_id,
                    '-f', '_NET_WM_WINDOW_TYPE', '32a',
                    '-set', '_NET_WM_WINDOW_TYPE', '_NET_WM_WINDOW_TYPE_DOCK'
                ], check=True)
                
                # Update geometry for the new monitor
                self._update_geometry()
                    
                # Set window properties after geometry
                subprocess.run(['wmctrl', '-i', '-r', window_id, '-b', 'add,sticky,above'], check=True)
                subprocess.run(['wmctrl', '-i', '-r', window_id, '-T', f'MAGI Panel ({self.position})'], check=True)
                
                # Force window manager to acknowledge changes
                subprocess.run(['wmctrl', '-i', '-a', window_id], check=True)
        except Exception as e:
            print(f"Window property setup error: {e}")
    
    def _update_geometry(self):
        """Update panel geometry based on primary monitor."""
        if not self.get_realized():
            return
        
        try:
            display = self.get_display()
            primary_monitor = display.get_primary_monitor()
            
            # Only update if primary monitor has changed
            if (not hasattr(self, '_monitor') or 
                primary_monitor.get_geometry() != self._monitor.get_geometry()):
                
                self._monitor = primary_monitor
                geometry = primary_monitor.get_geometry()
                scale = primary_monitor.get_scale_factor()
                
                window_id = self._get_window_id()
                if window_id:
                    # Update panel dimensions
                    self.panel_width = geometry.width
                    base_height = self.config['panel_height'] * scale
                    self.panel_height = base_height + (8 if self.position == 'bottom' else 4)
                    
                    # Set new position and size
                    x = geometry.x
                    y = geometry.y if self.position == 'top' else geometry.y + geometry.height - self.panel_height
                    
                    subprocess.run(['xdotool', 'windowmove', window_id, str(x), str(y)])
                    subprocess.run(['xdotool', 'windowsize', window_id, str(self.panel_width), str(self.panel_height)])
                    
                    # Update struts
                    if self.position == 'top':
                        struts = f'0, 0, {self.panel_height}, 0, 0, 0, 0, 0, {x}, {x + self.panel_width}, 0, 0'
                    else:
                        struts = f'0, 0, 0, {self.panel_height}, 0, 0, 0, 0, 0, 0, {x}, {x + self.panel_width}'
                    
                    subprocess.run([
                        'xprop', '-id', window_id,
                        '-f', '_NET_WM_STRUT_PARTIAL', '32c',
                        '-set', '_NET_WM_STRUT_PARTIAL', struts
                    ])
        except Exception as e:
            print(f"Geometry update error: {e}")
    
    
    def do_monitors_changed(self, display):
        """Handle monitor changes."""
        GLib.idle_add(self._update_geometry)
    
    def _get_window_id(self):
        """Get window ID using multiple methods."""
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
