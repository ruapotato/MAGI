#!/usr/bin/env python3
"""
MAGI Model Manager
A Comedy in Several Acts
Featuring: Whispers, Oracles, and a Baritone Cast
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk
import os
import json
import threading
import subprocess
import requests
import time
import numpy as np
import psutil
import socket
from dataclasses import dataclass
from typing import Optional, Tuple
from ThemeManager import ThemeManager
from pathlib import Path

# The Stage Directory
BACKSTAGE = Path(__file__).parent.absolute()
COSTUME_CLOSET = BACKSTAGE / 'ears_pyenv'
WHISPER_SCRIPT = BACKSTAGE / 'whisper_server.py'
BARITONE_SCRIPT = BACKSTAGE / 'voice.py'

@dataclass
class BaritoneWrangler:
    """Master of the Deep-Voiced Performers"""
    voice_artist: Optional[subprocess.Popen] = None
    green_room: Path = Path('/tmp/magi_realm/say')
    current_voice: str = "p326"  # Our leading bass
    
    def summon_the_bass_section(self) -> Tuple[bool, str]:
        """Raise the curtain on our deep-voiced performers"""
        try:
            self.green_room.mkdir(parents=True, exist_ok=True)
            self._escort_current_performer_offstage()
            
            self.voice_artist = subprocess.Popen([
                'python3', str(BARITONE_SCRIPT)
            ])
            
            return self._await_dramatic_entrance()
            
        except Exception as stage_fright:
            return False, f"Performance anxiety: {stage_fright}"
    
    def _escort_current_performer_offstage(self):
        """Politely show our current voice actor to the exit"""
        if self.voice_artist:
            try:
                self.voice_artist.terminate()
                self.voice_artist.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.voice_artist.kill()
            self.voice_artist = None
    
    def _await_dramatic_entrance(self) -> Tuple[bool, str]:
        """Wait in the wings for our voice to warm up"""
        test_script = self.green_room / f"sound_check_{time.time()}.txt"
        try:
            test_script.write_text("♪ Do-Re-Mi ♪")
            time.sleep(2)  # Brief pause for dramatic effect
            
            if not test_script.exists():
                return True, "Voice warmed up and ready for the spotlight!"
            else:
                test_script.unlink()
                return False, "Voice caught a case of stage fright"
        except Exception as vocal_strain:
            return False, f"Technical difficulties: {vocal_strain}"
    
    def still_breathing(self) -> bool:
        """Make sure our vocalist hasn't fainted"""
        return self.voice_artist and self.voice_artist.poll() is None
    
    def clear_the_stage(self):
        """Time to go home, everyone"""
        self._escort_current_performer_offstage()

def find_process_monopolizing_port(port):
    """Hunt down the process hogging our stage"""
    for performer in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            for connection in performer.connections('tcp'):
                if connection.laddr.port == port:
                    return performer
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def escort_squatter_from_port(port):
    """Politely remove any process squatting on our port"""
    squatter = find_process_monopolizing_port(port)
    if squatter:
        try:
            squatter.terminate()
            try:
                squatter.wait(timeout=3)
            except psutil.TimeoutExpired:
                squatter.kill()
            return True
        except psutil.NoSuchProcess:
            pass
    return False

def is_stage_door_locked(port):
    """Check if someone's already using our stage door (port)"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as door:
        return door.connect_ex(('localhost', port)) == 0

def update_whisper_script():
    """Update the Whisper's entrance cue"""
    script = f"""#!/bin/bash
source "{COSTUME_CLOSET}/bin/activate"
export PYTHONPATH="{COSTUME_CLOSET}/lib/python3.11/site-packages"
exec python3 "{WHISPER_SCRIPT}"
"""
    
    script_path = BACKSTAGE / 'start_whisper_server.sh'
    with open(script_path, 'w') as f:
        f.write(script)
    os.chmod(script_path, 0o755)

def prepare_voice_monitoring(window):
    """Set up the voice monitoring section of our variety show"""
    # Create the vocalist's personal stage
    voice_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    
    # The marquee featuring our star
    voice_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    window.voice_indicator = Gtk.Label(label="●")
    voice_header.append(window.voice_indicator)
    voice_header.append(Gtk.Label(label="THE BARITONE"))
    voice_box.append(voice_header)
    
    # The critics' corner
    window.voice_status_label = Gtk.Label()
    window.voice_status_label.set_xalign(0)
    voice_box.append(window.voice_status_label)
    
    # Find the main stage (our containing box)
    main_stage = window.get_child()
    
    # Place our act in the show lineup, right after the Oracle
    main_stage.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
    main_stage.append(voice_box)
    
    # Prepare the voice director
    window.voice_manager = BaritoneWrangler()
    window.voice_status = "Starting"
    
    # Update the status board with our new performer
    original_update = window.update_status_displays
    def new_update_status_displays():
        original_update()
        def update_indicator(spotlight, dramatic_state):
            """The Grand Illuminator of Status Indicators"""
            # First, dim all the lights
            spotlight.remove_css_class('status-running')   # The "all is well" green glow
            spotlight.remove_css_class('status-error')     # The "panic mode" red alert
            spotlight.remove_css_class('status-loading')   # The "please hold" amber hue
            
            # Now, for the dramatic lighting reveal...
            match dramatic_state:
                case "Running":
                    spotlight.add_css_class('status-running')    # A triumphant green!
                case "Error":
                    spotlight.add_css_class('status-error')      # A concerning crimson!
                case _:
                    spotlight.add_css_class('status-loading')    # An anticipatory amber!
        update_indicator(window.voice_indicator, window.voice_status)
    window.update_status_displays = new_update_status_displays
    
    # Add voice check to the daily rehearsal
    original_check = window.check_model_status
    def new_check_model_status():
        if window.verification_in_progress:
            return
        
        window.verification_in_progress = True
        window.check_button.set_sensitive(False)
        
        def verify_full_cast():
            # Check if our baritone is still conscious
            if window.voice_manager.still_breathing():
                window.set_voice_status("Running", "Voice projection optimal!")
            else:
                success, message = window.voice_manager.summon_the_bass_section()
                if success:
                    window.set_voice_status("Running", "Voice ready to rumble!")
                else:
                    window.set_voice_status("Error", message)
            
            # Check the rest of the cast
            original_check()
        
        threading.Thread(target=verify_full_cast, daemon=True).start()
    
    window.check_model_status = new_check_model_status
    
    # Add the voice status board updater
    def set_voice_status(status, message=""):
        window.voice_status = status
        window.voice_status_label.set_text(message)
        window.update_status_displays()
    window.set_voice_status = set_voice_status
    
    # Enhance the final curtain call
    original_cleanup = window.cleanup
    def new_cleanup():
        window.voice_manager.clear_the_stage()
        original_cleanup()
    window.cleanup = new_cleanup
    
    # Raise the curtain on our vocal performer
    success, message = window.voice_manager.summon_the_bass_section()
    if success:
        window.set_voice_status("Running", "Voice ready for its solo!")
    else:
        window.set_voice_status("Error", message)

class ModelManager(Gtk.ApplicationWindow):
    """The Grand Theater of AI Models"""
    
    def __init__(self, app):
        super().__init__(application=app)
        
        # No fancy decorations for our stage
        self.set_decorated(False)
        self.connect('realize', self._on_realize)
        
        # Clear any lingering performers
        if is_stage_door_locked(5000):
            print("Escorting the previous Whisper from the premises...")
            escort_squatter_from_port(5000)
            time.sleep(1)
        
        # Load the playbill
        self.load_config()
        
        # Get our costume designer
        self.theme_manager = ThemeManager()
        self.theme_manager.register_window(self)
        
        # Our Whisper starts in the wings
        self.whisper_server_process = None
        self.setup_theater()
        
        # Set the initial mood
        self.whisper_status = "Starting"
        self.whisper_progress = 0
        self.ollama_status = "Starting"
        self.ollama_progress = 0
        
        # Add our voice monitor to the production
        prepare_voice_monitoring(self)
        
        # Are we in rehearsal?
        self.verification_in_progress = False
        
        # Start monitoring the power consumption
        GLib.timeout_add(3000, self.update_gpu_status)
        
        # Places everyone!
        try:
            update_whisper_script()
            self.summon_whisper_oracle()
            self.check_ollama_presence()
        except Exception as opening_night_jitters:
            print(f"First night nerves: {opening_night_jitters}")
        
        # Schedule first review
        GLib.timeout_add(5000, self.initial_status_check)
    def _on_realize(self, widget):
        """Set the stage after the curtain rises"""
        def arrange_scenery():
            try:
                # Find our stage number
                playbill = subprocess.check_output(
                    ['xdotool', 'search', '--name', '^MAGI Model Status$']
                ).decode().strip()
                
                if playbill:
                    stage_number = playbill.split('\n')[0]
                    # Make sure we're visible from all seats
                    subprocess.run(['wmctrl', '-i', '-r', stage_number, '-b', 'add,below,sticky'], check=True)
                    # Perform in all theaters simultaneously
                    subprocess.run(['wmctrl', '-i', '-r', stage_number, '-t', '-1'], check=True)
            except Exception as scenery_collapse:
                print(f"Stage decoration malfunction: {scenery_collapse}")
            return False
        
        # Give the stagehands time to set up
        GLib.timeout_add(100, arrange_scenery)
    
    def initial_status_check(self):
        """Opening night pre-show check"""
        self.check_model_status()
        return False
    
    def setup_theater(self):
        """Prepare our grand theater for the performance"""
        self.set_title("MAGI Model Status")
        self.set_default_size(400, 200)
        
        # The main stage
        stage = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        stage.set_margin_start(16)
        stage.set_margin_end(16)
        stage.set_margin_top(16)
        stage.set_margin_bottom(16)
        
        # The director's button
        directors_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        directors_box.set_halign(Gtk.Align.END)
        self.check_button = Gtk.Button(label="Check The Cast")
        self.check_button.connect('clicked', lambda _: self.check_model_status())
        directors_box.append(self.check_button)
        stage.append(directors_box)
        
        # The Whisper's Corner
        whisper_stage = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        # Whisper's nameplate
        whisper_marquee = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.whisper_indicator = Gtk.Label(label="●")
        whisper_marquee.append(self.whisper_indicator)
        whisper_marquee.append(Gtk.Label(label="THE WHISPER"))
        whisper_stage.append(whisper_marquee)
        
        # Whisper's progress tracker
        self.whisper_progress_bar = Gtk.ProgressBar()
        self.whisper_progress_bar.set_hexpand(True)
        whisper_stage.append(self.whisper_progress_bar)
        
        # Whisper's current state
        self.whisper_status_label = Gtk.Label()
        self.whisper_status_label.set_xalign(0)
        whisper_stage.append(self.whisper_status_label)
        
        stage.append(whisper_stage)
        stage.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        # The Oracle's Domain
        oracle_stage = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        # Oracle's nameplate
        oracle_marquee = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.ollama_indicator = Gtk.Label(label="●")
        oracle_marquee.append(self.ollama_indicator)
        model_name = self.config.get('ollama_model', 'mistral').upper()
        oracle_marquee.append(Gtk.Label(label=f"THE ORACLE ({model_name})"))
        oracle_stage.append(oracle_marquee)
        
        # Oracle's progress tracker
        self.ollama_progress_bar = Gtk.ProgressBar()
        self.ollama_progress_bar.set_hexpand(True)
        oracle_stage.append(self.ollama_progress_bar)
        
        # Oracle's prophecies
        self.ollama_status_label = Gtk.Label()
        self.ollama_status_label.set_xalign(0)
        oracle_stage.append(self.ollama_status_label)
        
        stage.append(oracle_stage)
        stage.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        
        # The Power Meter
        self.gpu_info = Gtk.Label()
        self.gpu_info.set_xalign(0)
        stage.append(self.gpu_info)
        
        # The Time Keeper
        self.last_check_label = Gtk.Label()
        self.last_check_label.set_xalign(1)
        stage.append(self.last_check_label)
        
        self.set_child(stage)
    
    def load_config(self):
        """Read the director's notes"""
        playbill_location = os.path.expanduser("~/.config/magi/config.json")
        try:
            with open(playbill_location) as playbill:
                self.config = json.load(playbill)
        except Exception:
            self.config = {'ollama_model': 'mistral'}
    
    def check_model_status(self):
        """Perform a full cast check"""
        if self.verification_in_progress:
            print("Rehearsal already in progress, please wait...")
            return
        
        print("Checking on all our performers...")
        self.verification_in_progress = True
        self.check_button.set_sensitive(False)
        
        def inspect_the_talent():
            # Check on our Whisper
            try:
                GLib.idle_add(self.set_whisper_status, "Checking", 50, "Testing the acoustics...")
                
                try:
                    sound_check = requests.get('http://localhost:5000/status', timeout=5)
                    if sound_check.ok:
                        # Test the microphone
                        silence = np.zeros(8000, dtype=np.float32)
                        files = {'audio': ('silence.wav', silence.tobytes())}
                        mic_check = requests.post('http://localhost:5000/transcribe', 
                                               files=files, timeout=10)
                        if mic_check.ok:
                            GLib.idle_add(self.set_whisper_status, "Running", 100, "Ready to whisper")
                        else:
                            GLib.idle_add(self.set_whisper_status, "Loading", 50, "Warming up...")
                    else:
                        GLib.idle_add(self.set_whisper_status, "Error", 0, "Lost their voice")
                except requests.exceptions.ConnectionError:
                    GLib.idle_add(self.set_whisper_status, "Error", 0, "Missed their cue")
                except requests.exceptions.Timeout:
                    GLib.idle_add(self.set_whisper_status, "Loading", 50, "Still in makeup...")
                
            except Exception as whisper_mishap:
                print(f"Whisper had a moment: {whisper_mishap}")
                GLib.idle_add(self.set_whisper_status, "Error", 0, str(whisper_mishap))

            # Check on our Oracle
            try:
                print("DEBUG: Consulting with the Oracle...")
                def verify_oracle_consciousness():
                    try:
                        response = requests.post(
                            'http://localhost:11434/api/generate',
                            json={
                                'model': self.config.get('ollama_model', 'mistral'),
                                'prompt': 'Speak, O wise one!',
                                'options': {
                                    'num_predict': 20
                                }
                            },
                            timeout=30
                        )
                        return response.ok and len(response.text.strip()) > 0
                    except:
                        return False
                
                # Try to wake the Oracle three times
                for attempt in range(3):
                    if verify_oracle_consciousness():
                        GLib.idle_add(self.set_ollama_status, "Running", 100, "Oracle is prophesying")
                        break
                    elif attempt < 2:
                        time.sleep(5)
                else:
                    GLib.idle_add(self.set_ollama_status, "Loading", 70, 
                                "Oracle is meditating (this may take time)...")
                    threading.Thread(target=self.awaken_oracle, daemon=True).start()
                    
            except Exception as oracle_confusion:
                print(f"Oracle is puzzled: {oracle_confusion}")
                if "Connection refused" in str(oracle_confusion):
                    msg = "Oracle missed their entrance - start with: systemctl start ollama"
                else:
                    msg = str(oracle_confusion)
                GLib.idle_add(self.set_ollama_status, "Error", 0, msg)
            
            # Update the timekeeper
            performance_time = time.strftime("%H:%M:%S")
            GLib.idle_add(self.last_check_label.set_text, f"Last curtain call: {performance_time}")
            
            # Reset the director's button
            GLib.idle_add(self._reset_verification_state)
        
        # Begin the inspection in the background
        threading.Thread(target=inspect_the_talent, daemon=True).start()
    def _reset_verification_state(self):
        """Let the director push their button again"""
        self.verification_in_progress = False
        self.check_button.set_sensitive(True)
    
    def summon_whisper_oracle(self):
        """Coax our shy performer onto the stage"""
        try:
            # Check if someone's hogging the microphone
            if is_stage_door_locked(5000):
                print("Politely removing previous performer...")
                escort_squatter_from_port(5000)
                time.sleep(1)  # Moment of silence
            
            # Clean up any remnants of past performances
            try:
                os.remove('/tmp/MAGI/whisper_progress')
            except FileNotFoundError:
                pass  # No encore to clean up
            
            # Send in our performer
            stage_directions = str(BACKSTAGE / 'start_whisper_server.sh')
            self.whisper_server_process = subprocess.Popen([stage_directions])
            print(f"Whisper enters stage left: {stage_directions}")
            self.set_whisper_status("Starting", 10, "Clearing throat...")
            
            def monitor_whisper_preparation():
                """Watch our performer prepare"""
                rehearsal_count = 0
                has_appeared = False
                
                while rehearsal_count < 180:  # 15 minutes of fame
                    try:
                        # Check if they're ready
                        status_check = requests.get('http://localhost:5000/status', timeout=5)
                        if status_check.ok:
                            status_report = status_check.json()
                            has_appeared = True
                            
                            if status_report['percentage'] == 100:
                                # Final sound check
                                try:
                                    silence = np.zeros(8000, dtype=np.float32)
                                    files = {'audio': ('silence.wav', silence.tobytes())}
                                    voice_test = requests.post(
                                        'http://localhost:5000/transcribe', 
                                        files=files, 
                                        timeout=10
                                    )
                                    if voice_test.ok:
                                        GLib.idle_add(
                                            self.set_whisper_status, 
                                            "Running", 
                                            100, 
                                            "Voice crystal clear"
                                        )
                                        return
                                except requests.exceptions.RequestException:
                                    GLib.idle_add(
                                        self.set_whisper_status, 
                                        "Starting",
                                        status_report['percentage'],
                                        status_report['message']
                                    )
                            else:
                                GLib.idle_add(
                                    self.set_whisper_status, 
                                    "Starting",
                                    status_report['percentage'],
                                    status_report['message']
                                )
                        
                    except requests.exceptions.ConnectionError:
                        if not has_appeared:
                            GLib.idle_add(
                                self.set_whisper_status, 
                                "Starting", 
                                10,
                                "In the green room..."
                            )
                    except Exception as stage_fright:
                        print(f"Performance anxiety: {stage_fright}")
                    
                    rehearsal_count += 1
                    time.sleep(5)
                
                if not has_appeared:
                    GLib.idle_add(
                        self.set_whisper_status, 
                        "Error", 
                        0,
                        "Missed their cue - check the dressing room"
                    )
            
            # Start our stage manager
            threading.Thread(target=monitor_whisper_preparation, daemon=True).start()
            
        except Exception as opening_night_disaster:
            print(f"Opening night crisis: {opening_night_disaster}")
            self.set_whisper_status(
                "Error", 
                0, 
                f"Failed to perform: {opening_night_disaster}"
            )
    
    def check_ollama_presence(self):
        """See if our Oracle has arrived at the theater"""
        try:
            self.set_ollama_status("Starting", 10, "Checking the crystal ball...")
            try:
                mystic_response = requests.get('http://localhost:11434/api/version', timeout=30)
                if mystic_response.ok:
                    # Oracle is in the building
                    threading.Thread(target=self.awaken_oracle, daemon=True).start()
                    self.set_ollama_status(
                        "Starting", 
                        20, 
                        "Oracle is preparing their prophecies..."
                    )
                else:
                    self.set_ollama_status(
                        "Error", 
                        0, 
                        "Oracle is confused. Summon with: systemctl start ollama"
                    )
            except requests.exceptions.ConnectionError:
                self.set_ollama_status(
                    "Error", 
                    0, 
                    "Oracle absent - summon with: systemctl start ollama"
                )
                print("Oracle not found - ensure their presence with: systemctl start ollama")
            except requests.exceptions.Timeout:
                self.set_ollama_status("Starting", 15, "Oracle is fashionably late...")
                threading.Thread(target=self.monitor_oracle_arrival, daemon=True).start()
        except Exception as mystical_mishap:
            msg = ("Oracle missed their entrance - start with: systemctl start ollama" 
                  if "Connection refused" in str(mystical_mishap) 
                  else f"Mystical malfunction: {mystical_mishap}")
            print(f"Oracle confusion: {mystical_mishap}")
            self.set_ollama_status("Error", 0, msg)
    
    def monitor_oracle_arrival(self):
        """Wait for our Oracle to make their grand entrance"""
        attempts = 0
        while attempts < 30:  # 15 minutes of patience
            try:
                mystic_check = requests.get('http://localhost:11434/api/version', timeout=30)
                if mystic_check.ok:
                    threading.Thread(target=self.awaken_oracle, daemon=True).start()
                    return
            except:
                attempts += 1
                progress = min(60, 15 + (attempts * 2))
                GLib.idle_add(
                    self.set_ollama_status, 
                    "Starting", 
                    progress,
                    "Awaiting the Oracle's arrival..."
                )
            time.sleep(30)
        
        GLib.idle_add(
            self.set_ollama_status, 
            "Error", 
            0,
            "Oracle got lost - check the mystic pathways"
        )
    
    def awaken_oracle(self):
        """Gently rouse our Oracle from their meditation"""
        try:
            model_name = self.config.get('ollama_model', 'mistral')
            print(f"\nDEBUG: Awakening the {model_name} Oracle")
            
            GLib.idle_add(
                self.set_ollama_status, 
                "Loading", 
                70,
                "Oracle entering trance state (patience required)..."
            )
            
            def verify_oracle_consciousness():
                """Check if the Oracle is truly awake"""
                try:
                    response = requests.post(
                        'http://localhost:11434/api/generate',
                        json={
                            'model': model_name,
                            'prompt': 'Are you awakened, O wise one?',
                            'options': {
                                'num_predict': 10,
                                'temperature': 0
                            }
                        },
                        timeout=30
                    )
                    return response.ok and len(response.text) > 0
                except:
                    return False
            
            # Begin the awakening ritual
            meditation_count = 0
            while meditation_count < 30:  # 15 minutes of spiritual patience
                try:
                    # Gentle prodding
                    response = requests.post(
                        'http://localhost:11434/api/generate',
                        json={
                            'model': model_name,
                            'prompt': 'Awaken',
                            'options': {
                                'num_predict': 1,
                                'temperature': 0
                            }
                        },
                        timeout=60
                    )
                    
                    if response.ok:
                        # Triple-check their consciousness
                        for _ in range(3):
                            if verify_oracle_consciousness():
                                GLib.idle_add(
                                    self.set_ollama_status,
                                    "Running",
                                    100,
                                    "Oracle's third eye is open"
                                )
                                return
                            time.sleep(5)
                        
                        # Semi-conscious state
                        meditation_count += 1
                        progress = min(95, 70 + meditation_count)
                        GLib.idle_add(
                            self.set_ollama_status,
                            "Loading",
                            progress,
                            "Oracle approaching enlightenment..."
                        )
                    else:
                        meditation_count += 1
                        progress = min(90, 70 + meditation_count)
                        GLib.idle_add(
                            self.set_ollama_status,
                            "Loading",
                            progress,
                            "Oracle deep in meditation..."
                        )
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                    meditation_count += 1
                    progress = min(90, 70 + meditation_count)
                    GLib.idle_add(
                        self.set_ollama_status,
                        "Loading",
                        progress,
                        "Oracle contemplating existence..."
                    )
                except Exception as spiritual_crisis:
                    print(f"DEBUG: Oracle's spiritual emergency: {spiritual_crisis}")
                
                time.sleep(30)
            
            # Meditation timeout
            GLib.idle_add(
                self.set_ollama_status,
                "Error",
                0,
                "Oracle stuck in meditation - check their incense"
            )
            
        except Exception as metaphysical_mishap:
            msg = ("Oracle needs summoning: systemctl start ollama" 
                  if "Connection refused" in str(metaphysical_mishap) 
                  else str(metaphysical_mishap))
            print(f"DEBUG: Oracle's existential crisis: {metaphysical_mishap}")
            GLib.idle_add(
                self.set_ollama_status,
                "Error",
                0,
                msg
            )

    def on_whisper_encore(self, button):
        """When Whisper needs a second take"""
        if self.verification_in_progress:
            return
            
        button.set_sensitive(False)
        
        # Escort our current performer offstage
        if self.whisper_server_process:
            try:
                self.whisper_server_process.terminate()
                self.whisper_server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.whisper_server_process.kill()
            self.whisper_server_process = None
        
        # Make sure their understudy isn't hiding in the wings
        if is_stage_door_locked(5000):
            escort_squatter_from_port(5000)
            time.sleep(1)  # Dramatic pause
        
        # Reset for the encore
        self.whisper_status = "Starting"
        self.whisper_progress = 0
        self.update_status_displays()
        self.summon_whisper_oracle()
        button.set_sensitive(True)
    
    def set_whisper_status(self, status, progress, message=""):
        """Update Whisper's status board"""
        self.whisper_status = status
        self.whisper_progress = progress
        self.whisper_progress_bar.set_fraction(progress / 100)
        self.whisper_status_label.set_text(message)
        self.update_status_displays()
    
    def set_ollama_status(self, status, progress=0, message=""):
        """Update the Oracle's prophecy board"""
        print(f"DEBUG: Oracle speaks - Status: {status}, Progress: {progress}, Message: {message}")
        self.ollama_status = status
        self.ollama_progress = progress
        self.ollama_progress_bar.set_fraction(progress / 100)
        self.ollama_status_label.set_text(message)
        self.update_status_displays()
        
    def update_status_displays(self):
        """Refresh all our status lights"""
        def update_performer_spotlight(spotlight, status):
            # Reset all moods
            spotlight.remove_css_class('status-running')
            spotlight.remove_css_class('status-error')
            spotlight.remove_css_class('status-loading')
            
            # Set the appropriate mood lighting
            if status == "Running":
                spotlight.add_css_class('status-running')
            elif status == "Error":
                spotlight.add_css_class('status-error')
            else:
                spotlight.add_css_class('status-loading')
        
        update_performer_spotlight(self.whisper_indicator, self.whisper_status)
        update_performer_spotlight(self.ollama_indicator, self.ollama_status)
    
    def update_gpu_status(self):
        """Check the power consumption of our performance"""
        try:
            import pynvml
            pynvml.nvmlInit()
            backstage_power = pynvml.nvmlDeviceGetHandleByIndex(0)
            
            # Check the power meter
            power_reading = pynvml.nvmlDeviceGetMemoryInfo(backstage_power)
            watts_used = power_reading.used / 1024**3
            total_capacity = power_reading.total / 1024**3
            
            # Check if we're overheating
            temperature = pynvml.nvmlDeviceGetTemperature(
                backstage_power, 
                pynvml.NVML_TEMPERATURE_GPU
            )
            
            self.gpu_info.set_text(
                f"Power Draw: {watts_used:.1f}GB/{total_capacity:.1f}GB | Temp: {temperature}°C"
            )
        except Exception:
            self.gpu_info.set_text("Power Meter: Unplugged")
        
        return True
    
    def cleanup(self):
        """Time to lower the final curtain"""
        if self.whisper_server_process:
            try:
                self.whisper_server_process.terminate()
                self.whisper_server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.whisper_server_process.kill()
            except Exception as farewell_mishap:
                print(f"Whisper's awkward exit: {farewell_mishap}")
        
        # Make sure Whisper really left the building
        if is_stage_door_locked(5000):
            try:
                escort_squatter_from_port(5000)
            except Exception as lingering_presence:
                print(f"Had to escort Whisper out: {lingering_presence}")


class ModelManagerApplication(Adw.Application):
    """The Theater Management Company"""
    def __init__(self):
        super().__init__(application_id='com.system.magi.models')
    
    def do_activate(self):
        """Open the theater for today's performance"""
        theater = ModelManager(self)
        theater.present()
        
        # Position our theater in the skyline
        cityscape = theater.get_display()
        district = cityscape.get_monitors()[0]
        plot_of_land = district.get_geometry()
        
        theater_width, theater_height = theater.get_default_size()
        # Find a nice spot near the top right
        x_position = plot_of_land.x + plot_of_land.width - theater_width - 10
        y_position = plot_of_land.y + 10
        
        def establish_theater_presence():
            try:
                # Get our theater's ID
                marquee = subprocess.check_output(
                    ['xdotool', 'search', '--name', '^MAGI Model Status$']
                ).decode().strip()
                if marquee:
                    theater_id = marquee.split('\n')[0]
                    
                    # Make sure we're visible from every street
                    subprocess.run(['wmctrl', '-i', '-r', theater_id, '-t', '-1'], check=True)
                    
                    # Keep us modest but noticeable
                    subprocess.run(
                        ['wmctrl', '-i', '-r', theater_id, '-b', 'add,below,sticky'], 
                        check=True
                    )
                    
                    # Move to our prime location
                    subprocess.run(
                        ['wmctrl', '-i', '-r', theater_id, '-e', 
                         f'0,{x_position},{y_position},-1,-1'], 
                        check=True
                    )
                    
                    # One more check for visibility
                    subprocess.run(
                        ['wmctrl', '-i', '-r', theater_id, '-b', 'add,sticky'], 
                        check=True
                    )
            except Exception as zoning_violation:
                print(f"Theater placement issues: {zoning_violation}")
                # Try again after the dust settles
                GLib.timeout_add(500, establish_theater_presence)
                return False
            return False
        
        # Give the city time to notice us
        GLib.timeout_add(100, establish_theater_presence)


def main():
    """The Show Must Go On"""
    import signal
    
    theatrical_company = ModelManagerApplication()
    
    def closing_time(signum=None, frame=None):
        """Time to send everyone home"""
        print("\nLowering the curtain...")
        for theater in theatrical_company.get_windows():
            if isinstance(theater, ModelManager):
                theater.cleanup()
                break
        theatrical_company.quit()
    
    # Handle the critics gracefully
    signal.signal(signal.SIGINT, closing_time)
    signal.signal(signal.SIGTERM, closing_time)
    
    try:
        final_review = theatrical_company.run(None)
        closing_time()
        return final_review
    except Exception as catastrophic_failure:
        print(f"The theater is on fire: {catastrophic_failure}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
