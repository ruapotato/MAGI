#!/usr/bin/env python3

import pyaudio
import wave
import numpy as np
import os
import sys
from datetime import datetime
import time
from collections import deque
import requests
import json
import argparse
import signal
import psutil
import logging
import torch
import queue
from threading import Thread

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
        self.CHUNK = 512  # Silero VAD requires 512 samples for 16kHz
        self.FORMAT = pyaudio.paFloat32
        self.CHANNELS = 1
        self.RATE = 16000
        
        # Detection parameters
        self.SILENCE_LIMIT = 0.7
        self.PREV_AUDIO = 0.5
        self.MIN_SILENCE_DETECTIONS = 3
        
        # Minimum audio duration in seconds
        self.MIN_AUDIO_DURATION = 0.35
        
        # State
        self.status = "waiting"
        self.frames = []
        self.prev_frames = deque(maxlen=int(self.PREV_AUDIO * self.RATE / self.CHUNK))
        self.running = True
        
        # Initialize audio
        self.p = pyaudio.PyAudio()
        
        # Load config
        self.config = self.load_config()
        
        # Status indicators
        self.status_chars = {
            "waiting": "🎤",
            "listening": "📝",
            "processing": "⚙️ ",
            "error": "❌"
        }
        
        # Initialize Silero VAD
        torch.set_num_threads(1)
        self.model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                         model='silero_vad',
                                         force_reload=False)
        self.get_speech_timestamps = utils[0]
        
        # VAD parameters
        self.USE_ONNX = False  # Can be enabled for potentially faster inference
        self.VAD_THRESHOLD = 0.5
        self.audio_buffer = queue.Queue()
        self.processing_thread = Thread(target=self._process_vad, daemon=True)
        self.processing_thread.start()
        
        # Model requires 512 samples for 16kHz
        if self.RATE != 16000:
            raise ValueError("Sample rate must be 16kHz for Silero VAD")
        
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

    def _process_vad(self):
        """Process audio chunks using Silero VAD in a separate thread"""
        audio_chunks = []
        silence_chunks = 0
        is_speaking = False
        
        while self.running:
            try:
                chunk = self.audio_buffer.get(timeout=0.1)
                # Convert to numpy array and make it writable
                audio_data = np.frombuffer(chunk, dtype=np.float32).copy()
                # Convert to tensor and ensure correct shape
                audio_data = torch.from_numpy(audio_data)
                
                # Verify chunk size
                if len(audio_data) != self.CHUNK:
                    self.log.debug(f"Skipping irregular chunk size: {len(audio_data)}")
                    continue
                
                # Add batch dimension and get speech probability
                audio_data = audio_data.unsqueeze(0)  # Add batch dimension
                speech_prob = self.model(audio_data, self.RATE).item()
                
                if speech_prob >= self.VAD_THRESHOLD:
                    if not is_speaking:
                        is_speaking = True
                        self.update_status("listening")
                        # Include previous audio for context
                        audio_chunks.extend(list(self.prev_frames))
                    
                    audio_chunks.append(chunk)
                    silence_chunks = 0
                else:
                    if is_speaking:
                        silence_chunks += 1
                        audio_chunks.append(chunk)
                        
                        # Check if silence duration exceeds limit
                        if (silence_chunks * self.CHUNK / self.RATE >= self.SILENCE_LIMIT and 
                            silence_chunks >= self.MIN_SILENCE_DETECTIONS):
                            self._process_speech_segment(audio_chunks)
                            audio_chunks = []
                            silence_chunks = 0
                            is_speaking = False
                    else:
                        self.prev_frames.append(chunk)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.log.error(f"Error in VAD processing: {e}")
                self.update_status("error")

    def _process_speech_segment(self, audio_chunks):
        """Process a complete speech segment"""
        if not audio_chunks:
            return
            
        self.update_status("processing")
        
        # Combine audio chunks
        audio_data = np.concatenate([np.frombuffer(chunk, dtype=np.float32) 
                                   for chunk in audio_chunks])
        
        # Calculate duration in seconds
        duration = len(audio_data) / self.RATE
        
        # Check if audio is too short
        if duration < self.MIN_AUDIO_DURATION:
            self.log.debug(f"Audio too short ({duration:.2f}s), skipping processing")
            self.update_status("waiting")
            return
        
        # Get transcription
        transcription = self.transcribe_audio(audio_data)
        if transcription and not self.is_likely_hallucination(transcription):
            print(transcription, flush=True)
        else:
            self.log.debug("Transcription filtered or empty")
        
        self.update_status("waiting")

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
            return (in_data, pyaudio.paContinue)
        
        # Add audio chunk to processing queue
        self.audio_buffer.put(in_data)
        
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
