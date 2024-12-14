#!/usr/bin/env python3
"""
🔮 The Not Dead Yet Voice Assistant 🔮
Now with 100% more working and 50% less crashing!
"""

import os
import sys
import logging
import json
import re
import asyncio
import signal
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import subprocess
import requests
import threading
import yt_dlp
import argparse

def silence_screaming_alsa_demons():
    """Because ALSA never learned to use indoor voices"""
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stderr.fileno())

class BanishBrokenPipes:
    """Because broken pipes should be a plumber's problem, not ours"""
    def __enter__(self):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type == BrokenPipeError:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stderr.fileno())
            return True

class SpeakingInTongues:
    """For when silence isn't golden"""
    
    def __init__(self):
        self._voice_lock = threading.Lock()
    
    def shout_to_mortals(self, proclamation: str):
        """Speak forth into the void"""
        def _actually_speak():
            with self._voice_lock:
                try:
                    subprocess.run(
                        ['espeak', '-s', '150', '-p', '50', '-a', '200', proclamation],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True
                    )
                except Exception as e:
                    print(f"🔮 Lost my voice: {e}")
        
        threading.Thread(target=_actually_speak, daemon=True).start()

class WizardOfYouTube:
    """Master of cat videos and other important content"""
    
    def __init__(self):
        self.summoning_circle = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }
    
    async def find_moving_pictures(self, search_terms: str) -> Optional[str]:
        """Scry the tubes for relevant content"""
        try:
            with yt_dlp.YoutubeDL(self.summoning_circle) as crystal_ball:
                results = await asyncio.to_thread(
                    crystal_ball.extract_info,
                    f"ytsearch1:{search_terms}",
                    download=False
                )
                
                if not results.get('entries'):
                    return None
                
                chosen_one = results['entries'][0]
                return f"https://www.youtube.com/watch?v={chosen_one['id']}"
        except Exception as e:
            print(f"🔮 YouTube spirits are angry: {e}")
            return None

class MysticMind:
    """The Oracle of Ollama, now with better error handling"""
    
    def __init__(self):
        self.crystal_ball_url = "http://localhost:11434/api/generate"
    
    async def ponder_deeply(self, question: str) -> str:
        """Ask the Oracle, but don't wait too long"""
        try:
            response = requests.post(
                self.crystal_ball_url,
                json={
                    "model": "mistral",
                    "prompt": f"Respond very briefly and wittily to: {question}"
                },
                stream=True
            )
            
            if not response.ok:
                return "The Oracle is having a coffee break"
            
            prophecy = ""
            for whisper in response.iter_lines():
                if whisper:
                    chunk = json.loads(whisper)
                    if 'response' in chunk:
                        prophecy += chunk['response']
            
            return prophecy.strip()
            
        except Exception as e:
            return f"Oracle machine broke: {e}"

class NotSoVirtualAssistant:
    """A voice assistant that actually does something"""
    
    def __init__(self):
        self.vocal_cords = SpeakingInTongues()
        self.youtube_guru = WizardOfYouTube()
        self.oracle = MysticMind()
        self.magic_words = {'computer', 'magi', 'hey magi'}
        
        print("🔮 The assistant awakens, hoping for the best...")
    
    async def comprehend_mortals(self, utterance: str) -> Optional[str]:
        """Try to understand what the humans want"""
        if not utterance:
            return None
            
        print(f"🔮 Interpreting: {utterance}")
        
        if not self._summoned_properly(utterance):
            return None
        
        command = self._remove_summoning_words(utterance)
        return await self._do_the_thing(command)
    
    def _summoned_properly(self, words: str) -> bool:
        """Did they say the magic word?"""
        return any(word in words.lower() for word in self.magic_words)
    
    def _remove_summoning_words(self, words: str) -> str:
        """Strip the magic words out"""
        result = words.lower()
        for word in self.magic_words:
            if word in result:
                result = re.sub(f"{word}[,:]?\\s+", '', result, flags=re.IGNORECASE)
        return result.strip()
    
    async def _do_the_thing(self, command: str) -> str:
        """Figure out what they want and try to do it"""
        try:
            if 'time' in command:
                response = datetime.now().strftime("It's %I:%M %p")
            elif command.startswith('play'):
                response = await self._summon_entertainment(command[5:])
            else:
                response = await self.oracle.ponder_deeply(command)
            
            if response:
                self.vocal_cords.shout_to_mortals(response)
            return response
            
        except Exception as e:
            return f"Failed spectacularly: {e}"
    
    async def _summon_entertainment(self, request: str) -> str:
        """Try to play something without breaking everything"""
        if not request:
            return "Play what, exactly?"
        
        video_url = await self.youtube_guru.find_moving_pictures(request)
        if not video_url:
            return "Found nothing worth playing"
        
        try:
            subprocess.Popen(['freetube', video_url],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            return "Behold, entertainment!"
        except Exception as e:
            return f"Entertainment failed: {e}"

async def eternal_vigilance():
    """Main loop, now with more eternal and less crashing"""
    silence_screaming_alsa_demons()
    
    assistant = NotSoVirtualAssistant()
    print("🔮 Ready to assist (or at least try)...")
    
    with BanishBrokenPipes():
        while True:
            try:
                line = sys.stdin.readline().strip()
                if line:
                    response = await assistant.comprehend_mortals(line)
                    if response:
                        print(f"🔮 {response}", flush=True)
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"🔮 Oops: {e}")
                continue

if __name__ == "__main__":
    try:
        asyncio.run(eternal_vigilance())
    except KeyboardInterrupt:
        print("\n🔮 Farewell, mortals!")
    except Exception as e:
        print(f"🔮 Fatal error: {e}")
        sys.exit(1)
