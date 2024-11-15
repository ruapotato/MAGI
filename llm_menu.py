#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import os
import json
import requests
import threading
import subprocess
import sounddevice as sd
import numpy as np
import time

class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("MAGI Assistant")
        self.set_size_request(800, 600)
        self.set_keep_above(True)
        self.set_decorated(False)
        self.set_accept_focus(True)
        
        # Monitor focus and key events
        self.connect('focus-out-event', lambda w, e: GLib.idle_add(w.close))
        self.connect('key-press-event', self.on_key_press)
        
        # Create main layout
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.NONE)
        self.add(frame)
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        frame.add(main_box)
        
        # Chat history area
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_size_request(-1, 500)
        
        self.messages_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        viewport = Gtk.Viewport()
        viewport.add(self.messages_box)
        scroll.add(viewport)
        
        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_bottom(8)
        
        # Clear button
        clear_button = Gtk.Button(label="Clear Chat")
        clear_button.connect('clicked', self.clear_history)
        clear_button.get_style_context().add_class('toolbar-button')
        toolbar.pack_start(clear_button, False, False, 0)
        
        # Voice input button
        record_button = Gtk.Button()
        self.mic_icon = Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
        self.record_icon = Gtk.Image.new_from_icon_name("media-record-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
        record_button.add(self.mic_icon)
        record_button.connect('pressed', self.start_recording)
        record_button.connect('released', self.stop_recording)
        record_button.get_style_context().add_class('toolbar-button')
        toolbar.pack_end(record_button, False, False, 0)
        
        # Store record button reference and add recording state variables
        self.record_button = record_button
        self.recording_stream = None
        self.audio_data = []
        self.record_start_time = 0
        
        # Store record button reference
        self.record_button = record_button
        
        # Recording state
        self.recording_stream = None
        self.audio_data = []
        
        # Input area
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.entry = Gtk.Entry()
        self.entry.set_size_request(650, 44)
        
        send_button = Gtk.Button(label="Send")
        send_button.set_size_request(100, 44)
        
        input_box.pack_start(self.entry, True, True, 0)
        input_box.pack_start(send_button, False, False, 0)
        
        main_box.pack_start(toolbar, False, False, 0)
        main_box.pack_start(scroll, True, True, 0)
        main_box.pack_start(input_box, False, False, 0)
        
        # Store record button reference
        self.record_button = record_button
        
        # Connect signals
        self.entry.connect('activate', self.on_send)
        send_button.connect('clicked', self.on_send)
    
    def scroll_to_bottom(self):
        """Ensure chat window is scrolled to the bottom"""
        def _scroll():
            scroll = self.messages_box.get_parent().get_parent()
            adj = scroll.get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())
        GLib.idle_add(_scroll)

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            widget.close()
            return True
        return False
    
    def add_message(self, text, is_user=True):
        msg_box = MessageBox(text, is_user, self)
        self.messages_box.pack_start(msg_box, False, False, 0)
        self.scroll_to_bottom()
        # Only save history for user messages
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
            # Load current context and chat history
            context = self.load_context()
            
            # Build conversation history string
            history = []
            for child in self.messages_box.get_children():
                if isinstance(child, MessageBox):
                    role = "user" if child.is_user else "assistant"
                    history.append(f"{role}: {child.label.get_text()}")
            
            # Combine context and history
            conversation = ""
            if context:
                conversation += f"{context}\n\n"
            if history:
                conversation += "Previous conversation:\n" + "\n".join(history) + "\n\n"
            conversation += f"user: {prompt}"
            
            # Create initial message box for live output
            live_box = MessageBox("...", False, self)
            self.messages_box.pack_start(live_box, False, False, 0)
            self.scroll_to_bottom()
            
            full_response = ""
            
            response = requests.post('http://localhost:11434/api/generate',
                                   json={'model': 'mistral',
                                        'prompt': conversation},
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
                
                # Now that we have the full response, remove the live box and split into parts
                def split_and_create_boxes():
                    # Remove the live box
                    self.messages_box.remove(live_box)
                    
                    # Split on code blocks and create new boxes
                    is_code = False
                    parts = full_response.split('```')
                    
                    for part in parts:
                        if part.strip():  # Only create boxes for non-empty parts
                            msg_box = MessageBox(part.strip(), False, self, is_code)
                            self.messages_box.pack_start(msg_box, False, False, 0)
                            is_code = not is_code
                    
                    self.scroll_to_bottom()
                    # Save history after all boxes are created
                    self.save_history()
                
                GLib.idle_add(split_and_create_boxes)
            
            else:
                GLib.idle_add(lambda: self.add_message(f"Error: HTTP {response.status_code}", False))
                
        except Exception as e:
            GLib.idle_add(lambda: self.add_message(f"Error: {str(e)}", False))
    
    def load_context(self):
        try:
            with open('/tmp/MAGI/current_context.txt', 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""
    
    def load_history(self):
        try:
            with open('/tmp/MAGI/chat_history.json', 'r') as f:
                history = json.load(f)
                for msg in history:
                    msg_box = MessageBox(
                        msg['text'],
                        msg['is_user'],
                        self,
                        msg.get('is_code', False)  # Default to False for backwards compatibility
                    )
                    self.messages_box.pack_start(msg_box, False, False, 0)
                
                self.scroll_to_bottom()
        except FileNotFoundError:
            pass
    
    def save_history(self):
        history = []
        for child in self.messages_box.get_children():
            if isinstance(child, MessageBox):
                history.append({
                    'text': child.label.get_text(),
                    'is_user': child.is_user,
                    'is_code': child.is_code
                })
        
        os.makedirs('/tmp/MAGI', exist_ok=True)
        with open('/tmp/MAGI/chat_history.json', 'w') as f:
            json.dump(history, f)
    
    def clear_history(self, widget=None):
        for child in self.messages_box.get_children():
            child.destroy()
        self.save_history()
        try:
            os.remove('/tmp/MAGI/chat_history.json')
        except FileNotFoundError:
            pass
    
    def toggle_recording(self, button):
        if button.get_active():
            self.start_recording()
        else:
            self.stop_recording()
    
    # Voice recording functionality
    recording_stream = None
    audio_data = []
    
    def start_recording(self, button):
        """Start recording when button is pressed"""
        self.audio_data = []
        self.record_start_time = time.time()
        
        # Swap to record icon
        button.remove(button.get_child())
        button.add(self.record_icon)
        button.show_all()
        
        def audio_callback(indata, frames, time, status):
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
            self.record_button.get_style_context().add_class('recording')
            print("DEBUG: Recording started")
        except Exception as e:
            print(f"Recording Error: {e}")
    
    def stop_recording(self, button):
        """Stop recording when button is released and process audio"""
        recording_duration = time.time() - self.record_start_time
        
        # Swap back to mic icon
        button.remove(button.get_child())
        button.add(self.mic_icon)
        button.show_all()
        
        if self.recording_stream:
            self.recording_stream.stop()
            self.recording_stream.close()
            self.recording_stream = None
            self.record_button.get_style_context().remove_class('recording')
            print("DEBUG: Recording stopped")
            
            # Check if the recording was too short (less than 0.5 seconds)
            if recording_duration < 0.5:
                print("DEBUG: Recording too short, playing help message")
                subprocess.Popen(['espeak', "Press and hold to record audio"])
                return
            
            if self.audio_data:
                audio = np.concatenate(self.audio_data)
                
                def transcribe():
                    try:
                        print("DEBUG: Starting transcription")
                        files = {'audio': ('audio.wav', audio.tobytes())}
                        response = requests.post('http://localhost:5000/transcribe', files=files)
                        
                        if response.ok:
                            text = response.json().get('transcription', '')
                            print(f"DEBUG: Got transcription: {text}")
                            GLib.idle_add(self.entry.set_text, text)
                            GLib.idle_add(self.entry.grab_focus)
                        else:
                            print(f"Transcription server error: {response.status_code}")
                    except Exception as e:
                        print(f"Transcription Error: {e}")
                
                threading.Thread(target=transcribe, daemon=True).start()
            else:
                print("DEBUG: No audio data collected")

class MessageBox(Gtk.Box):
    def __init__(self, text, is_user=True, parent_window=None, is_code=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.parent_window = parent_window
        self.is_user = is_user
        self.is_code = is_code
        
        # Message container
        msg_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.pack_start(msg_container, True, True, 0)
        
        # Message content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        msg_container.pack_start(content_box, True, True, 0)
        
        # Text label
        self.label = Gtk.Label(label=text)
        self.label.set_line_wrap(False if is_code else True)  # Don't wrap code
        self.label.set_max_width_chars(80 if is_code else 60)  # Wider for code
        self.label.set_xalign(0)
        self.label.set_yalign(0)
        self.label.set_selectable(True)  # Make text selectable
        
        if is_code:
            self.label.set_justify(Gtk.Justification.LEFT)
            # Preserve indentation and line breaks
            self.label.set_markup("<tt>" + GLib.markup_escape_text(text) + "</tt>")
        
        # Apply appropriate style class
        if is_code:
            self.label.get_style_context().add_class('code-block')
        else:
            self.label.get_style_context().add_class('user-message' if is_user else 'assistant-message')
        
        content_box.pack_start(self.label, True, True, 0)
        
        # Button container
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        if is_user:
            button_box.set_halign(Gtk.Align.END)
        else:
            button_box.set_halign(Gtk.Align.START)
        content_box.pack_start(button_box, False, False, 0)
        
        # Add buttons based on message type
        if is_code:
            # Copy button for code blocks
            copy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
            copy_btn.get_style_context().add_class('message-button')
            copy_btn.connect('clicked', self.on_copy_clicked)
            button_box.pack_start(copy_btn, False, False, 0)
            
            # Run button for code blocks (if it looks like a command)
            if not text.strip().startswith(('import ', 'def ', 'class ')):
                run_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
                run_btn.get_style_context().add_class('message-button')
                run_btn.connect('clicked', self.on_run_clicked)
                button_box.pack_start(run_btn, False, False, 0)
        elif is_user:
            edit_btn = Gtk.Button.new_from_icon_name("document-edit-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
            edit_btn.get_style_context().add_class('message-button')
            edit_btn.connect('clicked', self.on_edit_clicked)
            button_box.pack_start(edit_btn, False, False, 0)
        else:
            # Read button for regular assistant messages
            read_btn = Gtk.Button.new_from_icon_name("audio-speakers-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
            read_btn.get_style_context().add_class('message-button')
            read_btn.connect('clicked', self.on_read_clicked)
            button_box.pack_start(read_btn, False, False, 0)
            
            # Copy button for assistant messages
            copy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
            copy_btn.get_style_context().add_class('message-button')
            copy_btn.connect('clicked', self.on_copy_clicked)
            button_box.pack_start(copy_btn, False, False, 0)
        
        # Delete button for all types
        if not is_code:  # Don't show delete button on code blocks
            delete_btn = Gtk.Button.new_from_icon_name("edit-delete-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
            delete_btn.get_style_context().add_class('message-button')
            delete_btn.connect('clicked', self.on_delete_clicked)
            button_box.pack_start(delete_btn, False, False, 0)
        
        self.show_all()
    
    def on_edit_clicked(self, button):
        """Edit the message text"""
        text = self.label.get_text()
        self.parent_window.entry.set_text(text)
        self.parent_window.entry.grab_focus()
    
    def on_read_clicked(self, button):
        """Read the message text using espeak"""
        text = self.label.get_text()
        subprocess.Popen(['espeak', text])
    
    def on_copy_clicked(self, button):
        """Copy message text to clipboard"""
        text = self.label.get_text()
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(text, -1)
    
    def on_delete_clicked(self, button):
        """Delete this message"""
        self.get_parent().remove(self)
        self.parent_window.save_history()
    
    def on_run_clicked(self, button):
        """Execute the code block as a shell command"""
        command = self.label.get_text().strip()
        try:
            subprocess.Popen(command, shell=True)
        except Exception as e:
            dialog = Gtk.MessageDialog(
                transient_for=self.get_toplevel(),
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Error running command"
            )
            dialog.format_secondary_text(str(e))
            dialog.run()
            dialog.destroy()

def setup_css():
    css = b"""
    entry {
        border-radius: 4px;
        padding: 8px;
        margin: 2px;
    }
    
    button {
        padding: 4px 8px;
        border-radius: 4px;
    }
    
    .message-button {
        padding: 4px;
        min-width: 24px;
        min-height: 24px;
    }
    
    .code-block {
        font-family: monospace;
        padding: 8px;
        margin: 4px 0px 4px 200px;
    }
    
    .user-message {
        padding: 8px;
        margin: 4px 200px 4px 0px;
    }
    
    .assistant-message {
        padding: 8px;
        margin: 4px 0px 4px 200px;
    }
    """
    style_provider = Gtk.CssProvider()
    style_provider.load_from_data(css)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        style_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

def parse_message_with_code(text):
    """Split a message into regular text and code blocks"""
    parts = []
    current_text = []
    code_block = False
    code_language = None
    
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('```'):
            if code_block:  # End of code block
                if current_text:
                    parts.append(('code', '\n'.join(current_text)))
                    current_text = []
                code_block = False
                code_language = None
            else:  # Start of code block
                if current_text:
                    parts.append(('text', '\n'.join(current_text)))
                    current_text = []
                code_block = True
                # Check for language specification
                code_language = line[3:].strip()
            i += 1
        else:
            current_text.append(line)
            i += 1
    
    # Add any remaining text
    if current_text:
        parts.append(('code' if code_block else 'text', '\n'.join(current_text)))
    
    # Clean up the parts
    cleaned_parts = []
    for part_type, content in parts:
        # Remove any leading/trailing empty lines
        content = content.strip('\n')
        if content:  # Only add if there's actual content
            cleaned_parts.append((part_type, content))
    
    return cleaned_parts


def position_window(window):
    """Position window at the bottom of the primary monitor"""
    display = Gdk.Display.get_default()
    monitor = display.get_primary_monitor()
    geometry = monitor.get_geometry()
    
    window_width, window_height = window.get_size()
    x = geometry.x + (geometry.width - window_width) // 2
    y = geometry.y + geometry.height - window_height - 100
    
    window.move(x, y)

def main():
    # Create /tmp/MAGI if it doesn't exist
    os.makedirs('/tmp/MAGI', exist_ok=True)
    
    # Set up the UI
    setup_css()
    window = MainWindow()
    
    # Position the window
    position_window(window)
    
    # Load existing chat history
    window.load_history()
    
    # Show and run
    window.connect('destroy', Gtk.main_quit)
    window.show_all()
    window.entry.grab_focus()
    Gtk.main()

if __name__ == "__main__":
    main()
