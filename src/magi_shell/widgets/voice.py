# src/magi_shell/widgets/voice.py
"""
Voice input widgets for MAGI Shell.

Provides GUI components for voice input and speech-to-text functionality
using system audio devices and the Whisper ASR service.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GLib
import numpy as np
import sounddevice as sd
import threading
import requests
import subprocess
import time
import os
from ..utils.config import load_config

class WhisperingEarButton(Gtk.Button):
    """
    Button that launches the voice assistant in a terminal window.
    
    Provides a simple interface to start the voice assistant pipeline
    in a separate terminal window for extended voice interaction sessions.
    """
    
    def __init__(self):
        super().__init__()
        self._ethereal_portal = None
        
        self.set_child(Gtk.Image.new_from_icon_name("audio-card-symbolic"))
        self.add_css_class('whispering-ear-button')
        self.connect('clicked', self._summon_listening_portal)
    
    def _summon_listening_portal(self, _):
        """Launch the voice assistant in a terminal window."""
        if self._ethereal_portal:
            return
            
        try:
            sacred_scroll_path = os.path.dirname(os.path.abspath(__file__))
            listening_spell = (
                f"cd {sacred_scroll_path} && "
                f"./asr.py | ./voice_assistant.py"
            )
            
            self._ethereal_portal = subprocess.Popen(
                ['mate-terminal', '--title=MAGI Voice Assistant', 
                 '--command', f'bash -c "{listening_spell}"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            def portal_watcher():
                if self._ethereal_portal:
                    self._ethereal_portal.wait()
                    self._ethereal_portal = None
                return False
            
            GLib.timeout_add(1000, portal_watcher)
            
        except Exception as e:
            print(f"Failed to open the listening portal: {e}")
            if self._ethereal_portal:
                self._ethereal_portal.terminate()
                self._ethereal_portal = None

class VoiceInputButton(Gtk.Button):
    """
    Button for quick voice-to-text input.
    
    Provides press-and-hold functionality for recording audio and converting
    it to text using the Whisper ASR service. The resulting text is typed
    into the currently focused window.
    """
    
    def __init__(self):
        super().__init__()
        
        self._recording = False
        self._transcribing = False
        self._stream = None
        self._audio_buffer = []
        self._start_time = 0
        
        self._setup_ui()
        self._setup_gestures()
    
    def _setup_ui(self):
        """Initialize button UI components."""
        self._mic_icon = Gtk.Image.new_from_icon_name("audio-input-microphone-symbolic")
        self._record_icon = Gtk.Image.new_from_icon_name("media-record-symbolic")
        self.set_child(self._mic_icon)
    
    def _setup_gestures(self):
        """Set up button click gestures."""
        click = Gtk.GestureClick.new()
        click.connect('begin', self._start_recording)
        click.connect('end', self._stop_recording)
        self.add_controller(click)

    def _start_recording(self, gesture, sequence):
        """Start audio recording with system default device"""
        if self._transcribing:
            return
        
        print("Starting recording...")
        self._recording = True
        self._start_time = time.monotonic()
        self._audio_buffer.clear()
        
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except:
                pass
            self._stream = None
        
        # Use system default audio input
        try:
            config = load_config()
            sample_rate = config.get('sample_rate', 16000)
            
            self._stream = sd.InputStream(
                channels=1,
                callback=self._audio_callback,
                blocksize=1024,
                samplerate=sample_rate,
                dtype=np.float32
            )
            self._stream.start()
            self.set_child(self._record_icon)
            self.add_css_class('recording')
            print(f"Recording started with default device at {sample_rate}Hz")
        except Exception as e:
            print(f"Recording error: {e}")
            self._recording = False
            self.set_child(self._mic_icon)
            dialog = Adw.MessageDialog.new(
                self.get_root(),
                "Recording Error",
                str(e)
            )
            dialog.add_response("ok", "OK")
            dialog.present()
    
    def _audio_callback(self, indata, *args):
        """Handle audio input"""
        if self._recording:
            self._audio_buffer.append(indata.copy())
    
    def _stop_recording(self, gesture, sequence):
        """Stop and process recording"""
        if self._transcribing:
            return
        
        print("Stopping recording...")
        self._recording = False
        duration = time.monotonic() - self._start_time
        
        # Stop recording
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            except Exception as e:
                print(f"Error stopping recording: {e}")
        
        # Reset button state
        self.set_child(self._mic_icon)
        self.remove_css_class('recording')
        
        # Handle short recordings
        if duration < 0.5:
            print("Recording too short")
            if not hasattr(self, '_speaking'):
                self._speaking = True
                subprocess.run(['magi_espeak', "Press and hold to record audio"])
                GLib.timeout_add(2000, self._reset_speaking_state)
            return
        
        # Process audio
        if self._audio_buffer:
            try:
                print("Processing audio...")
                self._transcribing = True
                self.set_sensitive(False)
                
                # Create a copy of audio data
                audio_data = np.concatenate(self._audio_buffer.copy())
                self._audio_buffer.clear()
                
                # Process in background
                threading.Thread(
                    target=self._transcribe_audio,
                    args=(audio_data,),
                    daemon=True
                ).start()
                
            except Exception as e:
                print(f"Audio processing error: {e}")
                self._transcribing = False
                self.set_sensitive(True)
    
    def _reset_speaking_state(self):
        """Reset the speaking state flag"""
        if hasattr(self, '_speaking'):
            delattr(self, '_speaking')
        return False
    
    def _transcribe_audio(self, audio_data):
        """Transcribe audio in background"""
        config = load_config()
        try:
            print("Sending to whisper...")
            endpoint = config.get('whisper_endpoint', 'http://localhost:5000/transcribe')
            files = {'audio': ('audio.wav', audio_data.tobytes())}
            response = requests.post(endpoint, files=files)
            
            GLib.idle_add(self._handle_transcription, response)
            
        except Exception as e:
            print(f"Transcription error: {e}")
            GLib.idle_add(self._reset_state)
    
    def _handle_transcription(self, response):
        """Handle transcription response"""
        try:
            if response.ok:
                text = response.json().get('transcription', '')
                if text:
                    subprocess.run(['xdotool', 'type', text], check=True)
        except Exception as e:
            print(f"Transcription handling error: {e}")
        finally:
            self._reset_state()
        return False
    
    def _reset_state(self):
        """Reset button state"""
        self._transcribing = False
        self.set_sensitive(True)
        return False
    
    def _transcribe_audio(self, audio_data):
        """Transcribe audio in background"""
        config = load_config()
        try:
            print("Sending to whisper...")
            files = {'audio': ('audio.wav', audio_data.tobytes())}
            response = requests.post(config['whisper_endpoint'], files=files)
            
            GLib.idle_add(self._handle_transcription, response)
            
        except Exception as e:
            print(f"Transcription error: {e}")
            GLib.idle_add(self._reset_state)
    
    def _handle_transcription(self, response):
        """Handle transcription response"""
        try:
            if response.ok:
                text = response.json().get('transcription', '')
                if text:
                    subprocess.run(['xdotool', 'type', text], check=True)
        except Exception as e:
            print(f"Transcription handling error: {e}")
        finally:
            self._reset_state()
        return False
    
    def _reset_state(self):
        """Reset button state"""
        self._transcribing = False
        self.set_sensitive(True)
        return False
