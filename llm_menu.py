#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib, Gio
import os
import sys
import json
import requests
import threading
import sounddevice as sd
import numpy as np
import time
import subprocess
from ThemeManager import ThemeManager

class MessageBox(Gtk.Box):
    def __init__(self, text, is_user=True, parent_window=None, is_code=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.parent_window = parent_window
        self.is_user = is_user
        self.is_code = is_code
        
        # Message container
        msg_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.append(msg_container)
        
        # Content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        msg_container.append(content_box)
        
        # Text label
        self.label = Gtk.Label(label=text)
        self.label.set_wrap(not is_code)
        self.label.set_max_width_chars(80 if is_code else 60)
        self.label.set_xalign(0)
        self.label.set_yalign(0)
        self.label.set_selectable(True)
        
        if is_code:
            self.label.set_markup("<tt>" + GLib.markup_escape_text(text) + "</tt>")
        
        # Apply style classes
        if is_code:
            self.label.add_css_class('code-block')
        else:
            self.label.add_css_class('user-message' if is_user else 'assistant-message')
        
        content_box.append(self.label)
        
        # Button container
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        button_box.set_halign(Gtk.Align.END if is_user else Gtk.Align.START)
        content_box.append(button_box)
        
        # Add buttons based on message type
        if is_code:
            # Copy button for code
            copy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
            copy_btn.connect('clicked', self.on_copy_clicked)
            button_box.append(copy_btn)
            
            # Run button for commands
            if not text.strip().startswith(('import ', 'def ', 'class ')):
                run_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
                run_btn.connect('clicked', self.on_run_clicked)
                button_box.append(run_btn)
        
        elif is_user:
            # Edit button for user messages
            edit_btn = Gtk.Button.new_from_icon_name("document-edit-symbolic")
            edit_btn.connect('clicked', self.on_edit_clicked)
            button_box.append(edit_btn)
        
        else:
            # Read button for assistant messages
            read_btn = Gtk.Button.new_from_icon_name("audio-speakers-symbolic")
            read_btn.connect('clicked', self.on_read_clicked)
            button_box.append(read_btn)
            
            # Copy button for assistant messages
            copy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
            copy_btn.connect('clicked', self.on_copy_clicked)
            button_box.append(copy_btn)
        
        # Delete button for non-code messages
        if not is_code:
            delete_btn = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
            delete_btn.connect('clicked', self.on_delete_clicked)
            button_box.append(delete_btn)
        
        # Update button styling
        for button in button_box:
            button.add_css_class('message-button')
            button.set_has_frame(False)
    
    def on_edit_clicked(self, button):
        text = self.label.get_text()
        self.parent_window.entry.set_text(text)
        self.parent_window.entry.grab_focus()
    
    def on_read_clicked(self, button):
        text = self.label.get_text()
        threading.Thread(target=lambda: os.system(f'espeak "{text}"')).start()
    
    def on_copy_clicked(self, button):
        text = self.label.get_text()
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set_text(text)
    
    def on_delete_clicked(self, button):
        parent = self.get_parent()
        if parent:
            parent.remove(self)
            if isinstance(self.parent_window, MainWindow):
                self.parent_window.save_history()
    
    def on_run_clicked(self, button):
        command = self.label.get_text().strip()
        try:
            threading.Thread(target=lambda: os.system(command)).start()
        except Exception as e:
            dialog = Adw.MessageDialog.new(
                self.parent_window,
                "Error running command",
                str(e)
            )
            dialog.add_response("ok", "OK")
            dialog.present()

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
                
        # Register with theme manager
        ThemeManager().register_window(self)
        
        # Recording state
        self.recording_stream = None
        self.audio_data = []
        self.record_start_time = 0
        self.is_transcribing = False
        self.is_recording = False
        
        self.set_opacity(0.0)
        self.setup_window()
    
    def setup_window(self):
        self.set_title("MAGI Assistant")
        self.set_default_size(800, 600)
        
        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        
        # Chat history area
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        
        self.messages_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroll.set_child(self.messages_box)
        
        # Input area
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.entry = Gtk.Entry()
        self.entry.set_hexpand(True)
        
        # Button box for voice and send buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        # Voice button
        self.record_button = Gtk.Button()
        self.mic_icon = Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic")
        self.record_icon = Gtk.Image.new_from_icon_name("media-record-symbolic")
        self.record_button.set_child(self.mic_icon)
        self.record_button.set_sensitive(True)
        
        # Click gesture for recording
        click = Gtk.GestureClick.new()
        click.set_button(1)
        click.connect('begin', self.start_recording)
        click.connect('end', self.stop_recording)
        self.record_button.add_controller(click)
        
        button_box.append(self.record_button)
        
        # Send button
        self.send_button = Gtk.Button(label="Send")
        self.send_button.add_css_class('suggested-action')
        button_box.append(self.send_button)
        
        # Pack everything
        input_box.append(self.entry)
        input_box.append(button_box)
        main_box.append(scroll)
        main_box.append(input_box)
        
        self.set_content(main_box)
        
        # Connect signals
        self.connect_signals()
        
        # Load history
        self.load_history()
        
        # Schedule window positioning
        GLib.timeout_add(50, self.setup_position)

    def connect_signals(self):
        # Focus handling
        focus_controller = Gtk.EventControllerFocus.new()
        focus_controller.connect('leave', self.on_focus_lost)
        self.add_controller(focus_controller)
        
        # Input handling
        self.entry.connect('activate', self.on_send)
        self.send_button.connect('clicked', self.on_send)
        
        # Keyboard shortcuts
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect('key-pressed', self.on_key_pressed)
        self.add_controller(key_controller)
    
    def setup_position(self):
        """Position window at the bottom center of the screen"""
        display = self.get_display()
        monitor = display.get_monitors()[0]  # Primary monitor
        geometry = monitor.get_geometry()
        window_width, window_height = self.get_default_size()
        x = geometry.x + (geometry.width - window_width) // 2
        y = geometry.y + geometry.height - window_height
        self.set_default_size(window_width, window_height)
        self.present()
        GLib.idle_add(self.move_and_show_window, x, y)
        return False
    
    def move_and_show_window(self, x, y):
        """Move the window using wmctrl and fade it in"""
        try:
            # Get window ID
            out = subprocess.check_output(['xdotool', 'search', '--name', '^MAGI Assistant$']).decode().strip()
            if out:
                window_id = out.split('\n')[0]
                # Move window
                subprocess.run(['wmctrl', '-i', '-r', window_id, '-e', f'0,{x},{y},-1,-1'], check=True)
        except Exception as e:
            print(f"Failed to position window: {e}")
        
        # Start fade in
        GLib.timeout_add(50, self.fade_in_window)
        return False

    def fade_in_window(self):
        """Fade in the window smoothly"""
        current_opacity = self.get_opacity()
        if current_opacity < 1.0:
            self.set_opacity(min(current_opacity + 0.2, 1.0))
            return True  # Continue fading
        return False  # Stop fading

    def on_focus_lost(self, controller):
        """Close window when focus is lost, unless recording or transcribing"""
        if not (self.is_recording or self.is_transcribing):
            self.close()
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle keyboard shortcuts"""
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def scroll_to_bottom(self):
        def _scroll():
            parent = self.messages_box.get_parent()
            if isinstance(parent, Gtk.ScrolledWindow):
                adj = parent.get_vadjustment()
                adj.set_value(adj.get_upper() - adj.get_page_size())
        GLib.idle_add(_scroll)
    
    def add_message(self, text, is_user=True):
        msg_box = MessageBox(text, is_user, self)
        self.messages_box.append(msg_box)
        self.scroll_to_bottom()
        if is_user:
            self.save_history()
    
    def on_send(self, widget):
        text = self.entry.get_text().strip()
        if text:
            self.add_message(text, True)
            self.entry.set_text("")
            threading.Thread(target=self.send_to_ollama, args=(text,)).start()
    
    def send_to_ollama(self, prompt):
        try:
            # Create initial message box for live output
            live_box = MessageBox("...", False, self)
            self.messages_box.append(live_box)
            self.scroll_to_bottom()
            
            full_response = ""
            
            response = requests.post('http://localhost:11434/api/generate',
                                   json={'model': 'mistral',
                                        'prompt': prompt},
                                   stream=True)
            
            if response.ok:
                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            if 'response' in chunk:
                                text = chunk['response']
                                full_response += text
                                
                                def update():
                                    live_box.label.set_text(full_response)
                                    self.scroll_to_bottom()
                                GLib.idle_add(update)
                                        
                        except json.JSONDecodeError:
                            continue
                
                # Split response into parts
                def split_and_create_boxes():
                    self.messages_box.remove(live_box)
                    
                    is_code = False
                    parts = full_response.split('```')
                    
                    for part in parts:
                        if part.strip():
                            msg_box = MessageBox(part.strip(), False, self, is_code)
                            self.messages_box.append(msg_box)
                            is_code = not is_code
                    
                    self.scroll_to_bottom()
                    self.save_history()
                
                GLib.idle_add(split_and_create_boxes)
            
            else:
                GLib.idle_add(lambda: self.add_message(f"Error: HTTP {response.status_code}", False))
                
        except Exception as e:
            GLib.idle_add(lambda: self.add_message(f"Error: {str(e)}", False))

    def start_recording(self, gesture, sequence):
        """Start recording when button is pressed"""
        if self.is_transcribing:
            return
            
        print("Starting recording...")
        self.is_recording = True
        if self.recording_stream:
            try:
                self.recording_stream.stop()
                self.recording_stream.close()
            except:
                pass
            self.recording_stream = None
            
        self.audio_data = []
        self.record_start_time = time.time()
        
        # Swap to record icon
        self.record_button.set_child(self.record_icon)
        
        def audio_callback(indata, *args):
            if hasattr(self, 'audio_data'):
                self.audio_data.append(indata.copy())
        
        try:
            self.recording_stream = sd.InputStream(
                callback=audio_callback,
                channels=1,
                samplerate=16000,
                blocksize=1024,
                dtype=np.float32
            )
            self.recording_stream.start()
            self.record_button.add_css_class('recording')
            print("Recording stream started successfully")
        except Exception as e:
            print(f"Recording Error: {e}")
            self.recording_stream = None
    
    def stop_recording(self, gesture, sequence):
        """Stop recording when button is released"""
        if self.is_transcribing:
            return
            
        print("Stopping recording...")
        self.is_recording = False
        recording_duration = time.time() - self.record_start_time
        
        # Stop recording first
        if self.recording_stream:
            try:
                self.recording_stream.stop()
                self.recording_stream.close()
                self.recording_stream = None
            except Exception as e:
                print(f"Error stopping recording: {e}")
        
        # Reset button state
        self.record_button.set_child(self.mic_icon)
        self.record_button.remove_css_class('recording')
        
        # Handle short recordings
        if recording_duration < 0.5:
            print("Recording too short")
            GLib.idle_add(lambda: subprocess.run(['espeak', "Press and hold to record audio"]))
            return
        
        # Process audio
        if self.audio_data:
            try:
                print("Processing audio...")
                self.is_transcribing = True
                self.record_button.set_sensitive(False)
                
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
                            self.record_button.set_sensitive(True)
                            
                            if response.ok:
                                text = response.json().get('transcription', '')
                                if text:
                                    self.entry.set_text(text)
                                    self.entry.grab_focus()
                            else:
                                print(f"Transcription error: {response.status_code}")
                        
                        GLib.idle_add(handle_response)
                    
                    except Exception as e:
                        print(f"Transcription error: {e}")
                        GLib.idle_add(lambda: setattr(self, 'is_transcribing', False))
                        GLib.idle_add(lambda: self.record_button.set_sensitive(True))
                
                # Start transcription in background
                threading.Thread(target=transcribe, daemon=True).start()
                
            except Exception as e:
                print(f"Audio processing error: {e}")
                self.is_transcribing = False
                self.record_button.set_sensitive(True)
        
        else:
            print("No audio data collected")
            self.record_button.set_sensitive(True)

    def cleanup_recording(self):
        """Clean up recording resources"""
        if self.recording_stream:
            try:
                self.recording_stream.stop()
                self.recording_stream.close()
                self.recording_stream = None
            except Exception as e:
                print(f"Error cleaning up recording stream: {e}")
        
        self.audio_data = []
        self.record_button.remove_css_class('recording')
    
    def load_history(self):
        try:
            with open('/tmp/MAGI/chat_history.json', 'r') as f:
                history = json.load(f)
                for msg in history:
                    msg_box = MessageBox(
                        msg['text'],
                        msg['is_user'],
                        self,
                        msg.get('is_code', False)
                    )
                    self.messages_box.append(msg_box)
                self.scroll_to_bottom()
        except FileNotFoundError:
            pass
    
    def save_history(self):
        history = []
        for child in self.messages_box:
            if isinstance(child, MessageBox):
                history.append({
                    'text': child.label.get_text(),
                    'is_user': child.is_user,
                    'is_code': child.is_code
                })
        
        os.makedirs('/tmp/MAGI', exist_ok=True)
        with open('/tmp/MAGI/chat_history.json', 'w') as f:
            json.dump(history, f)

class MAGIApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.system.magi.llm')
    
    def do_activate(self):
        win = MainWindow(self)
        win.present()

def main():
    app = MAGIApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
