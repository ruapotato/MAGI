#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import os
import json
import requests
import threading

def create_ui():
    window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
    window.set_title("MAGI Assistant")
    window.set_size_request(600, 400)
    window.set_keep_above(True)
    window.set_decorated(False)
    window.set_accept_focus(True)
    
    # Monitor focus and key events
    window.connect('focus-out-event', lambda w, e: GLib.idle_add(w.close))
    window.connect('key-press-event', on_key_press)
    
    # Create main layout
    frame = Gtk.Frame()
    frame.set_shadow_type(Gtk.ShadowType.OUT)
    window.add(frame)
    
    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    main_box.set_margin_start(12)
    main_box.set_margin_end(12)
    main_box.set_margin_top(12)
    main_box.set_margin_bottom(12)
    frame.add(main_box)
    
    # Chat history area
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_size_request(-1, 300)
    
    messages_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    viewport = Gtk.Viewport()
    viewport.add(messages_box)
    scroll.add(viewport)
    
    # Input area
    input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    entry = Gtk.Entry()
    entry.set_size_request(500, 36)
    
    send_button = Gtk.Button.new_with_label("Send")
    send_button.set_size_request(80, 36)
    
    input_box.pack_start(entry, True, True, 0)
    input_box.pack_start(send_button, False, False, 0)
    
    main_box.pack_start(scroll, True, True, 0)
    main_box.pack_start(input_box, False, False, 0)
    
    # Store widgets we need to access later
    window.messages_box = messages_box
    window.entry = entry
    
    # Connect signals
    entry.connect('activate', lambda w: on_send(window))
    send_button.connect('clicked', lambda w: on_send(window))
    
    return window

def setup_css():
    css = b"""
    window {
        background-color: #2d2d2d;
    }
    .user-message {
        background-color: #0084ff;
        color: white;
        padding: 12px 16px;
        border-radius: 20px;
        margin: 4px 0;
    }
    .assistant-message {
        background-color: #f0f0f0;
        color: black;
        padding: 12px 16px;
        border-radius: 20px;
        margin: 4px 0;
    }
    entry {
        background: #3d3d3d;
        color: white;
        border: 1px solid #4d4d4d;
        border-radius: 6px;
        padding: 8px;
    }
    button {
        background: #4d4d4d;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px;
    }
    button:hover {
        background: #5d5d5d;
    }
    """
    style_provider = Gtk.CssProvider()
    style_provider.load_from_data(css)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        style_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

def position_window(window):
    """Position window at the bottom of the primary monitor"""
    display = Gdk.Display.get_default()
    monitor = display.get_primary_monitor()
    geometry = monitor.get_geometry()
    
    # Position window at the bottom
    window.move(geometry.x,  # Center horizontally
               geometry.y + geometry.height - 400 - 50)    # Bottom with 50px margin

def add_message(window, text, is_user=True):
    msg_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    msg_box.set_margin_start(8)
    msg_box.set_margin_end(8)
    
    if is_user:
        msg_box.set_halign(Gtk.Align.END)
        style_class = 'user-message'
    else:
        msg_box.set_halign(Gtk.Align.START)
        style_class = 'assistant-message'
    
    label = Gtk.Label(text)
    label.set_line_wrap(True)
    label.set_max_width_chars(60)
    label.set_xalign(0)
    label.get_style_context().add_class(style_class)
    
    msg_box.pack_start(label, False, False, 0)
    window.messages_box.pack_start(msg_box, False, False, 0)
    msg_box.show_all()
    
    # Save history after each message
    save_history(window)

def send_to_ollama(window, prompt):
    try:
        # Load current context
        context = load_context()
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        response = requests.post('http://localhost:11434/api/generate',
                               json={'model': 'mistral',
                                    'prompt': full_prompt},
                               stream=True)
        
        if response.ok:
            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if 'response' in chunk:
                            full_response += chunk['response']
                    except json.JSONDecodeError:
                        continue
            
            # Final update with complete response
            if full_response:
                GLib.idle_add(add_message, window, full_response, False)
    except Exception as e:
        GLib.idle_add(add_message, window, f"Error: {str(e)}", False)

def on_send(window):
    text = window.entry.get_text().strip()
    if text:
        add_message(window, text, True)
        window.entry.set_text("")
        threading.Thread(target=send_to_ollama, args=(window, text)).start()

def on_key_press(widget, event):
    if event.keyval == Gdk.KEY_Escape:
        widget.close()
        return True
    return False

def load_context():
    try:
        with open('/tmp/MAGI/current_context.txt', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def load_history(window):
    try:
        with open('/tmp/MAGI/chat_history.json', 'r') as f:
            history = json.load(f)
            for msg in history:
                add_message(window, msg['text'], msg['is_user'])
    except FileNotFoundError:
        pass

def save_history(window):
    history = []
    for child in window.messages_box.get_children():
        label = child.get_children()[0]
        is_user = 'user-message' in label.get_style_context().list_classes()
        history.append({
            'text': label.get_text(),
            'is_user': is_user
        })
    
    os.makedirs('/tmp/MAGI', exist_ok=True)
    with open('/tmp/MAGI/chat_history.json', 'w') as f:
        json.dump(history, f)

def main():
    # Create /tmp/MAGI if it doesn't exist
    os.makedirs('/tmp/MAGI', exist_ok=True)
    
    # Set up the UI
    setup_css()
    window = create_ui()
    
    # Position the window
    position_window(window)
    
    # Load existing chat history
    load_history(window)
    
    # Show and run
    window.connect('destroy', Gtk.main_quit)
    window.show_all()
    window.entry.grab_focus()
    Gtk.main()

if __name__ == "__main__":
    main()
