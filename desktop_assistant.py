#!/usr/bin/env python3

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Vte', '3.91')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Vte, Gdk, GLib, Adw, Gio, Pango
import sys
import json
import os
import requests
import logging
import subprocess
from pathlib import Path
from typing import Optional

class TerminalWindow(Adw.ApplicationWindow):
    def __init__(self, assistant, app):
        super().__init__(application=app)
        self.assistant = assistant
        
        # Setup window
        self.set_title("MAGI Terminal")
        self.set_default_size(800, 600)
        
        # Use dark theme
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        
        # Create layout
        self.setup_ui()
        
        # Start bash session
        self.spawn_terminal()

    def setup_ui(self):
        """Setup the terminal interface"""
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        header = Adw.HeaderBar()
        main_box.append(header)
        
        self.terminal = Vte.Terminal()
        self.terminal.set_size_request(-1, 400)
        self.terminal.set_font(Pango.FontDescription("Monospace 11"))
        self.terminal.set_scrollback_lines(10000)
        self.terminal.set_mouse_autohide(True)
        
        # Handle terminal output
        self.terminal.connect('contents-changed', self.on_terminal_output)
        
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(self.terminal)
        scroll.set_vexpand(True)
        main_box.append(scroll)
        
        self.set_content(main_box)

    def spawn_terminal(self):
        """Start a new bash session"""
        self.terminal.spawn_async(
            Vte.PtyFlags.DEFAULT,
            os.environ['HOME'],
            ['/bin/bash'],
            [],
            GLib.SpawnFlags.DO_NOT_REAP_CHILD,
            None,
            None,
            -1,
            None,
            None,
        )

    def write_comment(self, text: str):
        """Write a comment to terminal without extra spacing"""
        self.terminal.feed_child(f"# {text}\n".encode())

    def send_command(self, command: str):
        """Send command to terminal without extra spacing"""
        self.terminal.feed_child(f"{command}\n".encode())

    def get_terminal_content(self) -> str:
        """Get current terminal content"""
        return self.terminal.get_text()[0].strip()

    def on_terminal_output(self, terminal):
        """Handle terminal output changes"""
        content = self.get_terminal_content()
        self.assistant.last_terminal_content = content

class DesktopAssistant:
    def __init__(self, model_name: str = "mistral", debug: bool = False):
        # Configure logging
        level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=level,
            format='[%(levelname)s] %(asctime)s %(message)s',
            stream=sys.stderr
        )
        self.log = logging.getLogger('desktop_assistant')
        
        # Initialize GTK app
        self.app = Adw.Application(application_id='com.system.magi.desktop')
        self.app.connect('activate', self.on_activate)
        
        # Setup state
        self.last_terminal_content = ""
        self.command_history = []
        self.window = None
        self.user_name = None
        
        # Setup AI components
        self.system_prompt = """You are a desktop command assistant that outputs ONLY a single bash command.

Rules:
1. Core Response Types:
   - General queries: Use espeak for direct responses
   - File/system commands: Use appropriate bash commands
   - ALWAYS use espeak for jokes, greetings, and conversations

2. User Interaction:
   - Track user's name if provided ("My name is...")
   - Maintain conversation context
   - Use espeak for all conversational responses
   - Don't try to access non-existent files or paths
   
3. Command Usage:
   - File operations: ls, pwd, cat (only for existing files)
   - System info: ps, top, df
   - Navigation: cd (with valid paths)
   - ALWAYS use espeak for jokes and chat

4. Response Guidelines:
   - Keep responses relevant and contextual
   - Don't create fake files or paths
   - Use espeak for ALL conversational responses
   - Stay on current topic
   - Remember user's name if given

Examples:
User: "Hello"
Assistant: espeak "Hello! How can I help you today?"

User: "My name is Bob"
Assistant: espeak "Nice to meet you Bob! How can I assist you?"

User: "Tell me a joke"
Assistant: espeak "Why did the programmer quit his job? He didn't get arrays!"

User: "What's in this folder?"
Assistant: ls -la

Remember: Always use espeak for conversations, jokes, and direct responses!"""

    def on_activate(self, app):
        """Create and show the terminal window"""
        self.window = TerminalWindow(self, app)
        self.window.present()
        
        # Start processing stdin
        GLib.io_add_watch(
            sys.stdin.fileno(),
            GLib.IO_IN | GLib.IO_HUP,
            self.on_stdin_ready
        )

    def get_ai_response(self, user_input: str) -> str:
        """Get command from Ollama"""
        try:
            # Check for name introduction
            if "my name is" in user_input.lower():
                self.user_name = user_input.lower().split("my name is")[-1].strip()
            
            # Add recent history and user info
            history_context = "\n".join(
                f"Previous command: {cmd}" 
                for cmd in self.command_history[-3:]
            )
            user_context = f"\nUser name: {self.user_name}" if self.user_name else ""
            terminal_context = f"\nCurrent terminal state:\n{self.last_terminal_content}\n"
            
            prompt = f"{self.system_prompt}\n\n{history_context}{user_context}\n{terminal_context}\nUser: {user_input}"
            
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    "model": "mistral",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=10
            )
            
            if response.status_code == 200:
                command = response.json()['response'].strip()
                command = command.split('\n')[0].strip()
                return command
                
            return f"espeak 'API error: {response.status_code}'"
            
        except Exception as e:
            self.log.error(f"AI error: {e}")
            return f"espeak 'Error getting AI response: {str(e)}'"

    def on_stdin_ready(self, source, condition):
        """Handle stdin input"""
        if condition & GLib.IO_HUP:
            return False
            
        line = sys.stdin.readline()
        if not line:
            return False
            
        user_input = line.strip()
        if user_input:
            # Show user input as comment
            if self.window:
                self.window.write_comment(user_input)
            
            # Get and execute AI command
            command = self.get_ai_response(user_input)
            if command:
                # Execute command
                if self.window:
                    self.window.send_command(command)
                
                # Update history
                self.command_history.append(command)
                if len(self.command_history) > 10:
                    self.command_history.pop(0)
        
        return True

    def run(self):
        """Start the application"""
        return self.app.run(sys.argv)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true')
    args = parser.parse_args()
    
    assistant = DesktopAssistant(debug=args.debug)
    return assistant.run()

if __name__ == "__main__":
    sys.exit(main())
