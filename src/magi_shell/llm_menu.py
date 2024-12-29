#!/usr/bin/env python3
"""
MAGI Shell LLM Menu Component

Provides a GTK4-based interface for interacting with the MAGI Shell's
LLM capabilities, including context-aware queries and voice input.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib, Gio
import os
import sys
import json
import requests
import threading
import numpy as np
import time
import subprocess
from pathlib import Path

from magi_shell.core.theme import ThemeManager
from magi_shell.utils.config import load_config
from magi_shell.widgets.voice import WhisperingEarButton
from magi_shell.utils.cache import Cache

class MessageBox(Gtk.Box):
    """A message box for displaying chat messages with actions."""
    
    def __init__(self, text, is_user=True, parent_window=None, is_code=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.parent_window = parent_window
        self.is_user = is_user
        self.is_code = is_code
        
        msg_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.append(msg_container)
        
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        msg_container.append(content_box)
        
        self.label = Gtk.Label(label=text)
        self.label.set_wrap(not is_code)
        self.label.set_max_width_chars(80 if is_code else 60)
        self.label.set_xalign(0)
        self.label.set_yalign(0)
        self.label.set_selectable(True)
        
        if is_code:
            self.label.set_markup("<tt>" + GLib.markup_escape_text(text) + "</tt>")
        
        if is_code:
            self.label.add_css_class('code-block')
        else:
            self.label.add_css_class('user-message' if is_user else 'assistant-message')
        
        content_box.append(self.label)
        
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        button_box.set_halign(Gtk.Align.END if is_user else Gtk.Align.START)
        content_box.append(button_box)
        
        if is_code:
            copy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
            copy_btn.connect('clicked', self.on_copy_clicked)
            button_box.append(copy_btn)
            
            if not text.strip().startswith(('import ', 'def ', 'class ')):
                run_btn = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
                run_btn.connect('clicked', self.on_run_clicked)
                button_box.append(run_btn)
        
        elif is_user:
            edit_btn = Gtk.Button.new_from_icon_name("document-edit-symbolic")
            edit_btn.connect('clicked', self.on_edit_clicked)
            button_box.append(edit_btn)
        
        else:
            read_btn = Gtk.Button.new_from_icon_name("audio-speakers-symbolic")
            read_btn.connect('clicked', self.on_read_clicked)
            button_box.append(read_btn)
            
            copy_btn = Gtk.Button.new_from_icon_name("edit-copy-symbolic")
            copy_btn.connect('clicked', self.on_copy_clicked)
            button_box.append(copy_btn)
        
        if not is_code:
            delete_btn = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
            delete_btn.connect('clicked', self.on_delete_clicked)
            button_box.append(delete_btn)
        
        for button in button_box:
            button.add_css_class('message-button')
            button.set_has_frame(False)
    
    def on_edit_clicked(self, button):
        text = self.label.get_text()
        self.parent_window.entry.set_text(text)
        self.parent_window.entry.grab_focus()
    
    def on_read_clicked(self, button):
        text = self.label.get_text()
        threading.Thread(target=lambda: os.system(f'magi_espeak "{text}"')).start()
    
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
    """Main window for the LLM Menu interface."""
    
    def __init__(self, app):
        super().__init__(application=app)
        
        ThemeManager().register_window(self)
        
        
        self.set_opacity(0.0)
        self.setup_window()
    
    def setup_window(self):
        """Initialize the window layout."""
        self.set_title("MAGI Assistant")
        self.set_default_size(800, 600)
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_bottom(8)
        
        clear_button = Gtk.Button(label="Clear Chat")
        clear_button.connect('clicked', self.clear_history)
        toolbar.append(clear_button)
        
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        
        self.messages_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroll.set_child(self.messages_box)
        
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.entry = Gtk.Entry()
        self.entry.set_hexpand(True)
        
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        
        self.send_button = Gtk.Button(label="Send")
        self.send_button.add_css_class('suggested-action')
        button_box.append(self.send_button)
        
        input_box.append(self.entry)
        input_box.append(button_box)
        main_box.append(toolbar)
        main_box.append(scroll)
        main_box.append(input_box)
        
        self.set_content(main_box)
        
        self.connect_signals()
        self.load_history()
        
        GLib.timeout_add(50, self.setup_position)

    def connect_signals(self):
        """Connect signal handlers."""
        focus_controller = Gtk.EventControllerFocus.new()
        focus_controller.connect('leave', self.on_focus_lost)
        self.add_controller(focus_controller)
        
        self.entry.connect('activate', self.on_send)
        self.send_button.connect('clicked', self.on_send)
        
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect('key-pressed', self.on_key_pressed)
        self.add_controller(key_controller)
    
    def setup_position(self):
        """Position window on screen."""
        display = self.get_display()
        monitor = display.get_monitors()[0]
        geometry = monitor.get_geometry()
        window_width, window_height = self.get_default_size()
        x = geometry.x + (geometry.width - window_width) // 2
        y = geometry.y + geometry.height - window_height
        self.set_default_size(window_width, window_height)
        self.present()
        GLib.idle_add(self.move_and_show_window, x, y)
        return False
    
    def move_and_show_window(self, x, y):
        """Move window to position and fade in."""
        try:
            out = subprocess.check_output(['xdotool', 'search', '--name', '^MAGI Assistant$']).decode().strip()
            if out:
                window_id = out.split('\n')[0]
                subprocess.run(['wmctrl', '-i', '-r', window_id, '-e', f'0,{x},{y},-1,-1'], check=True)
        except Exception as e:
            print(f"Failed to position window: {e}")
        
        GLib.timeout_add(50, self.fade_in_window)
        return False

    def fade_in_window(self):
        """Fade in window opacity."""
        current_opacity = self.get_opacity()
        if current_opacity < 1.0:
            self.set_opacity(min(current_opacity + 0.2, 1.0))
            return True
        return False

    def on_focus_lost(self, controller):
        """Handle window losing focus."""
        self.close()
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events."""
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def scroll_to_bottom(self):
        """Scroll messages to bottom."""
        def _scroll():
            adj = self.messages_box.get_parent().get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())
            return False
        GLib.timeout_add(100, _scroll)
    
    def add_message(self, text, is_user=True):
        """Add a new message to the chat."""
        msg_box = MessageBox(text, is_user, self)
        self.messages_box.append(msg_box)
        self.scroll_to_bottom()
        if is_user:
            self.save_history()
    
    def on_send(self, widget):
        """Handle send button click or Enter key."""
        text = self.entry.get_text().strip()
        if text:
            self.add_message(text, True)
            self.entry.set_text("")
            threading.Thread(target=self.send_to_ollama, args=(text,)).start()

    def send_to_ollama(self, prompt):
        """Send message to Ollama and handle streaming response."""
        try:
            context = self.load_context()
            
            history = []
            for child in self.messages_box:
                if isinstance(child, MessageBox):
                    role = "user" if child.is_user else "assistant"
                    history.append(f"{role}: {child.label.get_text()}")
            
            conversation = ""
            if context:
                conversation += f"{context}\n\n"
            if history:
                conversation += "Previous conversation:\n" + "\n".join(history) + "\n\n"
            conversation += f"user: {prompt}"
            
            live_box = MessageBox("...", False, self)
            self.messages_box.append(live_box)
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
                error_msg = f"Error: HTTP {response.status_code}"
                GLib.idle_add(lambda: self.add_message(error_msg, False))
                
        except Exception as error:
            error_msg = f"Error: {str(error)}"
            GLib.idle_add(lambda: self.add_message(error_msg, False))

    def load_context(self):
        """Load current context from file."""
        try:
            with open('/tmp/MAGI/current_context.txt', 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""
            
    def clear_history(self, widget=None):
        """Clear chat history."""
        while (child := self.messages_box.get_first_child()):
            self.messages_box.remove(child)
        self.save_history()
        try:
            os.remove('/tmp/MAGI/chat_history.json')
        except FileNotFoundError:
            pass

    def load_history(self):
        """Load chat history from file."""
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
        """Save chat history to file."""
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
    """Main application class for LLM Menu."""
    
    def __init__(self):
        super().__init__(application_id='com.system.magi.llm')
    
    def do_activate(self):
        """Handle application activation."""
        win = MainWindow(self)
        win.present()

def main():
    """Application entry point."""
    app = MAGIApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
