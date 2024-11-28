#!/usr/bin/env python3

import sys
import json
import os
import requests
import logging
import subprocess
from typing import Optional

class DesktopAssistant:
    def __init__(self, debug: bool = False):
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO,
            format='[%(levelname)s] %(asctime)s %(message)s',
            stream=sys.stderr
        )
        self.log = logging.getLogger('desktop_assistant')
        
        # System prompt that enforces single command responses
        self.system_prompt = """You are a desktop command assistant that outputs ONLY a single bash command.
Rules:
- Return exactly ONE bash command per response
- Use espeak with proper quoting for all speech
- Never combine multiple commands
- No explanations or comments

Examples:
User: "Tell me a joke"
Assistant: espeak "Why did the programmer quit? Because he didn't get arrays"

User: "What's in this folder?"
Assistant: ls -la

User: "Open firefox"
Assistant: firefox

Important: Only output the raw command - nothing else!"""
        
        self.history = []

    def execute_command(self, cmd: str) -> Optional[str]:
        """Execute a single bash command"""
        try:
            # Don't process empty commands
            if not cmd.strip():
                return None
                
            # Log the command being executed
            self.log.debug(f"Executing: {cmd}")
            
            # Run the command
            result = subprocess.run(
                cmd,
                shell=True,
                text=True,
                capture_output=True,
                executable='/bin/bash',
                env=os.environ
            )
            
            # Handle errors
            if result.returncode != 0 and result.stderr:
                error_msg = result.stderr.strip()
                self.log.error(f"Command failed: {error_msg}")
                return f"espeak 'Command failed: {error_msg}'"
            
            return result.stdout.strip() if result.stdout else None
            
        except Exception as e:
            self.log.error(f"Execution error: {e}")
            return None

    def get_ai_response(self, user_input: str) -> str:
        """Get single command from Ollama"""
        try:
            # Add recent history for context
            history_context = "\n".join(f"Previous: {h}" for h in self.history[-3:])
            prompt = f"{self.system_prompt}\n\n{history_context}\n\nUser: {user_input}"
            
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
                # Only take first line to ensure single command
                command = command.split('\n')[0].strip()
                self.log.debug(f"AI command: {command}")
                return command
                
            return f"espeak 'API error: {response.status_code}'"
            
        except Exception as e:
            self.log.error(f"AI error: {e}")
            return f"espeak 'Error getting AI response: {str(e)}'"

    def process_input(self, user_input: str):
        """Process a single user input"""
        try:
            if not user_input.strip():
                return
                
            self.log.debug(f"User input: {user_input}")
            
            # Add to history
            self.history.append(user_input)
            if len(self.history) > 10:
                self.history.pop(0)
            
            # Get single command
            command = self.get_ai_response(user_input)
            if not command:
                return
            
            # Execute command and handle output
            output = self.execute_command(command)
            if output:
                self.log.debug(f"Command output: {output}")
                
                # Only process non-espeak command outputs
                if not command.startswith('espeak'):
                    self.process_input(output)
                    
        except Exception as e:
            self.log.error(f"Processing error: {e}")
            self.execute_command(f"espeak 'Processing error: {str(e)}'")

    def run(self):
        """Main loop"""
        self.log.info("Assistant started")
        self.execute_command('espeak "Desktop assistant ready"')
        
        try:
            for line in sys.stdin:
                line = line.strip()
                if line:
                    self.process_input(line)
        except KeyboardInterrupt:
            self.log.info("Assistant stopped")
        except Exception as e:
            self.log.error(f"Fatal error: {e}")
            sys.exit(1)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true')
    args = parser.parse_args()
    
    assistant = DesktopAssistant(debug=args.debug)
    assistant.run()

if __name__ == "__main__":
    main()
