# src/magi_shell/utils/config.py

import os
import json

print("Loading config.py")

def load_config():
    """Load configuration from ~/.config/magi/config.json."""
    print("Executing load_config()")
    config_path = os.path.expanduser("~/.config/magi/config.json")
    try:
        with open(config_path) as f:
            config = json.load(f)
            print(f"Loaded config: {config}")
            return config
    except Exception as e:
        print(f"Warning: Configuration error ({e}), using defaults")
        default_config = {
            "panel_height": 28,
            "workspace_count": 4,
            "enable_effects": True,
            "enable_ai": True,
            "terminal": "mate-terminal",
            "launcher": "mate-panel --run-dialog",
            "background": "/usr/share/magi/backgrounds/default.png",
            "ollama_model": "mistral",
            "whisper_endpoint": "http://localhost:5000/transcribe",
            "sample_rate": 16000,
            "magi_theme": "Plain"
        }
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=4)
            print(f"Saved default config: {default_config}")
        except Exception as e:
            print(f"Warning: Could not save default configuration: {e}")
        return default_config

print("Finished loading config.py")
