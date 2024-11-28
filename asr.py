#!/usr/bin/env python3

import pyaudio
import wave
import numpy as np
import os
import sys
from datetime import datetime
import time
from collections import deque
from scipy.signal import butter, lfilter
import requests
import json
import argparse
import signal
from contextlib import contextmanager
import logging

class VoiceProcessor:
    def __init__(self, debug=False):
        # Configure logging
        level = logging.DEBUG if debug else logging.ERROR
        logging.basicConfig(
            level=level,
            format='[%(levelname)s] %(message)s',
            stream=sys.stderr
        )
        self.log = logging.getLogger('ears')
        
        # Audio parameters
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paFloat32
        self.CHANNELS = 1
        self.RATE = 16000
        
        # Detection parameters
        self.SILENCE_LIMIT = 0.7
        self.PREV_AUDIO = 0.5
        self.MIN_SILENCE_DETECTIONS = 3
        
        # Thresholds
        self.BASE_ENERGY_THRESHOLD = 0.005
        self.ENERGY_THRESHOLD = self.BASE_ENERGY_THRESHOLD
        self.ZCR_THRESHOLD = 0.2
        self.SPEECH_MEMORY = 8
        
        # State
        self.status = "waiting"
        self.frames = []
        self.prev_frames = deque(maxlen=int(self.PREV_AUDIO * self.RATE / self.CHUNK))
        self.silent_frames = 0
        self.voiced_frames = 0
        self.consecutive_silence = 0
        self.running = True
        
        # Analysis buffers
        self.energy_history = deque(maxlen=20)
        self.zcr_history = deque(maxlen=20)
        self.speech_history = deque([False] * self.SPEECH_MEMORY, maxlen=self.SPEECH_MEMORY)
        
        # Calibration
        self.calibration_frames = []
        self.calibrated = False
        
        # Initialize audio and filters
        self.p = pyaudio.PyAudio()
        self.butter_filter = self._create_butter_filter()
        
        # Load config
        self.config = self.load_config()
        
        # Status indicators
        self.status_chars = {
            "waiting": "🎤",
            "listening": "📝",
            "processing": "⚙️ ",
            "error": "❌"
        }

    def load_config(self):
        config_path = os.path.expanduser("~/.config/magi/config.json")
        try:
            with open(config_path) as f:
                return json.load(f)
        except Exception:
            return {
                'whisper_endpoint': 'http://localhost:5000/transcribe',
                'sample_rate': 16000
            }

    def _create_butter_filter(self):
        nyquist = self.RATE / 2
        low = 300 / nyquist
        high = 3000 / nyquist
        b, a = butter(4, [low, high], btype='band')
        return b, a

    def _apply_bandpass(self, data):
        return lfilter(self.butter_filter[0], self.butter_filter[1], data)

    def _calculate_features(self, audio_data):
        filtered_data = self._apply_bandpass(audio_data)
        energy = np.sqrt(np.mean(filtered_data**2))
        self.energy_history.append(energy)
        zcr = np.mean(np.abs(np.diff(np.signbit(filtered_data))))
        self.zcr_history.append(zcr)
        
        self.log.debug(
            f"Energy: {energy:.6f}, ZCR: {zcr:.6f}, " +
            f"Silent Frames: {self.silent_frames}, " +
            f"Consecutive Silence: {self.consecutive_silence}"
        )
        
        return energy, zcr

    def _calibrate(self, energy, zcr):
        self.calibration_frames.append((energy, zcr))
        if len(self.calibration_frames) >= int(self.RATE / self.CHUNK):
            energies = [f[0] for f in self.calibration_frames]
            zcrs = [f[1] for f in self.calibration_frames]
            self.ENERGY_THRESHOLD = max(
                self.BASE_ENERGY_THRESHOLD,
                np.mean(energies) * 2 + np.std(energies)
            )
            self.ZCR_THRESHOLD = np.mean(zcrs) + np.std(zcrs)
            self.log.debug(
                f"Calibration complete:\n" +
                f"Energy threshold: {self.ENERGY_THRESHOLD:.6f}\n" +
                f"ZCR threshold: {self.ZCR_THRESHOLD:.6f}"
            )
            self.calibrated = True

    def _is_speech(self, energy, zcr):
        if not self.calibrated:
            self._calibrate(energy, zcr)
            return False

        if len(self.energy_history) > 1:
            recent_energy = np.mean(list(self.energy_history)[-10:])
            self.ENERGY_THRESHOLD = max(
                self.BASE_ENERGY_THRESHOLD,
                recent_energy * 1.2
            )

        is_speech = (energy > self.ENERGY_THRESHOLD and 
                    zcr > self.ZCR_THRESHOLD * 0.5)
        
        self.speech_history.append(is_speech)
        
        if not is_speech and self.status == "listening":
            self.consecutive_silence += 1
        else:
            self.consecutive_silence = 0
            
        return sum(self.speech_history) >= 3

    def transcribe_audio(self, audio_data):
        try:
            endpoint = self.config.get('whisper_endpoint', 'http://localhost:5000/transcribe')
            files = {'audio': ('audio.wav', audio_data.tobytes())}
            response = requests.post(endpoint, files=files)
            
            if response.ok:
                result = response.json()
                return result.get('transcription', '')
            else:
                self.log.error(f"Transcription error: {response.status_code}")
                return None
                
        except Exception as e:
            self.log.error(f"Transcription error: {e}")
            return None

    def process_audio(self):
        if not self.frames:
            return
            
        self.update_status("processing")
        
        # Combine audio frames
        all_frames = list(self.prev_frames) + self.frames
        audio_data = np.concatenate([np.frombuffer(frame, dtype=np.float32) for frame in all_frames])
        
        # Get transcription
        transcription = self.transcribe_audio(audio_data)
        if transcription:
            print(transcription, flush=True)
        
        # Reset state
        self.frames = []
        self.prev_frames.clear()
        self.speech_history.clear()
        self.speech_history.extend([False] * self.SPEECH_MEMORY)
        self.silent_frames = 0
        self.voiced_frames = 0
        self.consecutive_silence = 0
        
        self.update_status("waiting")

    def update_status(self, new_status):
        """Update status and display indicator"""
        self.status = new_status
        indicator = self.status_chars.get(new_status, "?")
        print(f"\r{indicator}", end="", file=sys.stderr, flush=True)

    def audio_callback(self, in_data, frame_count, time_info, status):
        if not self.running:
            return (None, pyaudio.paComplete)
            
        audio_data = np.frombuffer(in_data, dtype=np.float32)
        energy, zcr = self._calculate_features(audio_data)
        is_speech = self._is_speech(energy, zcr)
        
        if is_speech:
            if self.status == "waiting":
                self.update_status("listening")
                self.frames.extend(list(self.prev_frames))
            self.frames.append(in_data)
            self.voiced_frames += 1
            self.silent_frames = 0
        else:
            if self.status == "waiting":
                self.prev_frames.append(in_data)
            elif self.status == "listening":
                self.silent_frames += 1
                self.frames.append(in_data)
                
                if (self.silent_frames * self.CHUNK / self.RATE >= self.SILENCE_LIMIT and 
                    self.consecutive_silence >= self.MIN_SILENCE_DETECTIONS):
                    self.process_audio()
        
        return (in_data, pyaudio.paContinue)

    def cleanup(self):
        self.running = False
        self.update_status("waiting")
        print("\n", end="", file=sys.stderr)

    def start(self):
        signal.signal(signal.SIGINT, lambda s, f: self.cleanup())
        
        try:
            self.log.info("Starting audio capture...")
            self.update_status("waiting")
            
            stream = self.p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
                stream_callback=self.audio_callback
            )
            
            while self.running and stream.is_active():
                time.sleep(0.1)
                
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            self.p.terminate()

def main():
    parser = argparse.ArgumentParser(description='MAGI Ears - Voice Input Processing')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output')
    args = parser.parse_args()
    
    processor = VoiceProcessor(debug=args.debug)
    processor.start()

if __name__ == "__main__":
    main()
