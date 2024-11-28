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
import subprocess
import psutil
from contextlib import contextmanager
import logging

def is_espeak_running():
    """Check if espeak is currently running"""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            if proc.info['name'] == 'espeak' or (proc.info['cmdline'] and 'espeak' in proc.info['cmdline'][0]):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

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
        self.MIN_AUDIO_DURATION = 0.35
        
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
        
        # Add hallucination filtering
        self.assume_hallucination = [
            "Thank you.",
            ".",
            "You.",
            "Thanks for watching.",
            "Thanks for listening.",
            "Subscribe.",
            "Like and subscribe.",
            "Please subscribe.",
            "Thank you for watching.",
            "What is the name?",
            "I'm going to go to the next one.",
            "I'm going to go ahead and get some more.",
            "I'm going to put a little bit of water on the top.",
            "ご視聴ありがとうございました",
            "お願いします",
            "ありがとうございます",
            "字幕は自動生成されています"
        ]
        
        # Add regex for Japanese/Chinese character detection
        self.cjk_ranges = [
            (0x4E00, 0x9FFF),   # CJK Unified Ideographs
            (0x3040, 0x309F),   # Hiragana
            (0x30A0, 0x30FF),   # Katakana
            (0xFF65, 0xFF9F),   # Halfwidth Katakana
            (0x3000, 0x303F),   # CJK Symbols and Punctuation
            (0xFF00, 0xFFEF),   # Fullwidth Forms
        ]

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

    def contains_cjk(self, text):
        """Check if text contains CJK characters"""
        for char in text:
            code = ord(char)
            if any(start <= code <= end for start, end in self.cjk_ranges):
                return True
        return False

    def is_likely_hallucination(self, text):
        """Check if transcription is likely a hallucination"""
        if not text:
            return True
            
        # Check against known hallucinations
        if text.strip() in self.assume_hallucination:
            self.log.debug(f"Filtered known hallucination: {text}")
            return True
            
        # Check for CJK characters when not expected
        if self.contains_cjk(text):
            self.log.debug(f"Filtered text with CJK characters: {text}")
            return True
            
        return False

    def process_audio(self):
        if not self.frames:
            return
            
        self.update_status("processing")
        
        # Combine audio frames
        all_frames = list(self.prev_frames) + self.frames
        audio_data = np.concatenate([np.frombuffer(frame, dtype=np.float32) for frame in all_frames])
        
        # Calculate duration in seconds
        duration = len(audio_data) / self.RATE
        
        # Check if audio is too short
        if duration < self.MIN_AUDIO_DURATION:
            self.log.debug(f"Audio too short ({duration:.2f}s), skipping processing")
            # Reset state without processing
            self.frames = []
            self.prev_frames.clear()
            self.speech_history.clear()
            self.speech_history.extend([False] * self.SPEECH_MEMORY)
            self.silent_frames = 0
            self.voiced_frames = 0
            self.consecutive_silence = 0
            self.update_status("waiting")
            return
        
        # Get transcription
        transcription = self.transcribe_audio(audio_data)
        if transcription and not self.is_likely_hallucination(transcription):
            print(transcription, flush=True)
        else:
            self.log.debug("Transcription filtered or empty")
        
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
        
        # Check for espeak before processing audio
        if is_espeak_running():
            # Skip processing while espeak is running
            if self.status != "waiting":
                self.log.debug("Espeak detected, pausing audio processing")
                self.update_status("waiting")
                self.frames = []
                self.prev_frames.clear()
            return (in_data, pyaudio.paContinue)
            
        audio_data = np.frombuffer(in_data, dtype=np.float32)
        energy, zcr = self._calculate_features(audio_data)
        is_speech = self._is_speech(energy, zcr)
        
        if is_speech:
            if self.status == "waiting":
                # Double check espeak isn't starting up
                if is_espeak_running():
                    return (in_data, pyaudio.paContinue)
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
            # Check for espeak before starting
            if is_espeak_running():
                self.log.warning("Waiting for espeak to finish...")
                while is_espeak_running():
                    time.sleep(0.1)
            
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
