# src/magi_shell/models/ollama.py
"""
Ollama model management for MAGI Shell.
"""

import requests
import threading
import time
from gi.repository import GLib

class OllamaManager:
    """Manager for Ollama LLM service"""
    def __init__(self, config):
        self.config = config
    
    def check_status(self, status_callback=None):
        """Check Ollama service status"""
        try:
            response = requests.get('http://localhost:11434/api/version', timeout=30)
            if response.ok:
                threading.Thread(target=self._verify_model, args=(status_callback,), 
                              daemon=True).start()
                if status_callback:
                    status_callback("Starting", 20, "Oracle is preparing...")
            else:
                if status_callback:
                    status_callback("Error", 0, 
                                 "Oracle confused. Start with: systemctl start ollama")
        except requests.exceptions.ConnectionError:
            if status_callback:
                status_callback("Error", 0, 
                             "Oracle absent - summon with: systemctl start ollama")
        except requests.exceptions.Timeout:
            if status_callback:
                status_callback("Starting", 15, "Oracle is fashionably late...")
            self._monitor_startup(status_callback)
    
    def _verify_model(self, status_callback=None):
        """Verify model is loaded and responding"""
        model_name = self.config.get('ollama_model', 'mistral')
        try:
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    'model': model_name,
                    'prompt': 'Are you ready?',
                    'options': {
                        'num_predict': 10,
                        'temperature': 0
                    }
                },
                timeout=30
            )
            if response.ok and len(response.text) > 0:
                if status_callback:
                    status_callback("Running", 100, "Oracle is prophesying")
                return True
        except:
            pass
        if status_callback:
            status_callback("Loading", 70, "Oracle is meditating...")
        return False
    
    def _monitor_startup(self, status_callback=None):
        """Monitor Ollama service startup"""
        def monitor():
            attempts = 0
            while attempts < 30:  # 15 minutes max
                try:
                    response = requests.get('http://localhost:11434/api/version', 
                                         timeout=30)
                    if response.ok:
                        self._verify_model(status_callback)
                        return
                except:
                    attempts += 1
                    progress = min(60, 15 + (attempts * 2))
                    if status_callback:
                        status_callback("Starting", progress, 
                                     "Awaiting Oracle's arrival...")
                time.sleep(30)
            
            if status_callback:
                status_callback("Error", 0, "Oracle got lost - check the pathways")
        
        threading.Thread(target=monitor, daemon=True).start()
