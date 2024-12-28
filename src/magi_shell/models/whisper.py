# src/magi_shell/models/whisper.py
"""
Whisper ASR model management for MAGI Shell.
"""

import subprocess
import time
import requests
import numpy as np
import os
from pathlib import Path
from ..utils.paths import get_magi_root, get_bin_path, get_utils_path
from ..utils.ports import is_port_in_use, release_port

def update_whisper_script():
    """Update the Whisper's entrance cue"""
    root_dir = get_magi_root()
    utils_dir = get_utils_path()
    script = f"""#!/bin/bash
source "{root_dir}/ears_pyenv/bin/activate"
export PYTHONPATH="{root_dir}/ears_pyenv/lib/python3.11/site-packages:$PYTHONPATH"
exec python3 "{utils_dir}/whisper_server.py"
"""
    
    script_path = get_bin_path() / 'start_whisper_server.sh'
    with open(script_path, 'w') as f:
        f.write(script)
    os.chmod(script_path, 0o755)

class WhisperManager:
    """Manager for the Whisper ASR service"""
    def __init__(self):
        self.whisper_server_process = None
        
    def start(self, status_callback=None):
        """Start the Whisper server"""
        try:
            if is_port_in_use(5000):
                release_port(5000)
                time.sleep(1)
            
            try:
                os.remove('/tmp/MAGI/whisper_progress')
            except FileNotFoundError:
                pass
            
            script_path = get_bin_path() / 'start_whisper_server.sh'
            print(f"Starting whisper server with script: {script_path}")  # Debug print
            self.whisper_server_process = subprocess.Popen([str(script_path)])
            
            if status_callback:
                status_callback("Starting", 10, "Clearing throat...")
            
        except Exception as e:
            print(f"Failed to start whisper server: {e}")  # Debug print
            if status_callback:
                status_callback("Error", 0, f"Failed to start: {e}")
            raise
    
    def check_status(self, status_callback=None):
        """Check Whisper server status"""
        try:
            response = requests.get('http://localhost:5000/status', timeout=5)
            if response.ok:
                data = response.json()
                if data['percentage'] == 100:
                    # Test with silence
                    silence = np.zeros(8000, dtype=np.float32)
                    files = {'audio': ('silence.wav', silence.tobytes())}
                    test = requests.post('http://localhost:5000/transcribe', 
                                      files=files, timeout=10)
                    if test.ok:
                        if status_callback:
                            status_callback("Running", 100, "Ready to whisper")
                        return True
                if status_callback:
                    status_callback("Loading", data['percentage'], data['message'])
            else:
                if status_callback:
                    status_callback("Error", 0, "Lost their voice")
        except requests.exceptions.ConnectionError:
            if status_callback:
                status_callback("Error", 0, "Missed their cue")
        except requests.exceptions.Timeout:
            if status_callback:
                status_callback("Loading", 50, "Still in makeup...")
        return False
    
    def cleanup(self):
        """Clean up Whisper server process"""
        if self.whisper_server_process:
            try:
                self.whisper_server_process.terminate()
                self.whisper_server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.whisper_server_process.kill()
            self.whisper_server_process = None
