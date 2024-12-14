#!/usr/bin/env python3
"""
🔮 The Not Dead Yet Voice Assistant 11.0 🔮
Because even functional programming can have a sense of humor!
"""

from dataclasses import dataclass, field
from typing import Protocol, NewType, Callable, AsyncIterator
from typing import Optional, Dict, Any, List, Tuple, FrozenSet
from functools import partial, reduce, lru_cache
from abc import ABC, abstractmethod
import os
import sys
import json
import re
import asyncio
import signal
from datetime import datetime
import subprocess
import requests
import threading
import contextlib
import yt_dlp  # Make sure this is properly imported!

# Types that make you giggle
SacredWords = NewType('SacredWords', str)
DivineWisdom = NewType('DivineWisdom', str)
MysticalCommand = NewType('MysticalCommand', Dict[str, Any])

@dataclass(frozen=True)
class ProphecyResult:
    """The Oracle's divine output"""
    message: str
    is_tool_command: bool = False

class WisdomChannel(Protocol):
    """How we communicate with the spirits"""
    async def channel_wisdom(self, utterance: str) -> str: ...

class DigitalSpell(Protocol):
    """The interface for our mystical tools"""
    async def cast(self, args: Dict[str, Any]) -> str: ...

@dataclass(frozen=True)
class ScrollOfKnowledge:
    """A mystical tool scroll"""
    name: str
    description: str
    incantation: Callable[[Dict[str, Any]], AsyncIterator[str]]

class VoiceInTheVoid:
    """Because sometimes silence is not golden"""
    
    def __init__(self) -> None:
        self._vocal_chord_mutex = threading.Lock()
    
    async def speak_forth(self, wisdom: DivineWisdom) -> None:
        if not wisdom.strip():
            return
        
        def _summon_voice() -> None:
            with self._vocal_chord_mutex:
                try:
                    subprocess.run(
                        ['espeak', '-s', '150', '-p', '50', '-a', '200', wisdom],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True
                    )
                except Exception as voice_crack:
                    print(f"🔮 *ahem*: {voice_crack}")
        
        threading.Thread(target=_summon_voice, daemon=True).start()

class DigitalGrimoire:
    """The Tome of Functional Spells"""
    
    def __init__(self) -> None:
        self._mystical_tools: Dict[str, ScrollOfKnowledge] = {
            "youtube_summoner": ScrollOfKnowledge(
                "youtube_summoner",
                "Summons entertainment from the digital aether",
                self._summon_videos
            ),
            "time_oracle": ScrollOfKnowledge(
                "time_oracle",
                "Reveals temporal truths",
                self._divine_time
            )
        }
    
    async def _summon_videos(self, args: Dict[str, Any]) -> str:
        crystal_config = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }
        
        try:
            with yt_dlp.YoutubeDL(crystal_config) as crystal_ball:
                search_results = await asyncio.to_thread(
                    crystal_ball.extract_info,
                    f"ytsearch1:{args['query']}",
                    download=False
                )
                
                if not search_results.get('entries'):
                    return "The tubes are mysteriously empty today!"
                
                chosen_vision = search_results['entries'][0]
                portal = f"https://www.youtube.com/watch?v={chosen_vision['id']}"
                
                subprocess.Popen(
                    ['freetube', portal],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return f"Summoning: {chosen_vision.get('title', 'a mysterious video')}"
                
        except Exception as tube_malfunction:
            return f"The entertainment portal is malfunctioning: {tube_malfunction}"
    
    async def _divine_time(self, _: Dict[str, Any]) -> str:
        return datetime.now().strftime("It is %I:%M %p")
    
    def fetch_spell(self, name: str) -> Optional[ScrollOfKnowledge]:
        return self._mystical_tools.get(name)
    
    @property
    def spell_catalog(self) -> str:
        return "\n".join(
            f"{name}: {scroll.description}"
            for name, scroll in self._mystical_tools.items()
        )

class WiseOracle:
    """The Keeper of Digital Wisdom"""
    
    def __init__(self, grimoire: DigitalGrimoire) -> None:
        self._portal = "http://localhost:11434/api/generate"
        self._grimoire = grimoire
        self._sacred_text = self._scribe_instructions()
    
    def _scribe_instructions(self) -> str:
        return f"""You are a witty voice assistant with these mystical powers:

{self._grimoire.spell_catalog}

Sacred Rules of Engagement:
1. Tools are ONLY for:
   - Videos: {{"tool": "youtube_summoner", "query": "search terms"}}
   - Time: {{"tool": "time_oracle"}}
2. Everything else gets a direct, witty response
3. Keep responses to ONE SHORT sentence
4. Be clever but brief
5. No explanations or commentary
6. Never mix tools with regular speech
7. Never respond with JSON unless using exact tool format

Example responses:
For time: {{"tool": "time_oracle"}}
For videos: {{"tool": "youtube_summoner", "query": "funny cats"}}
For jokes: Why did the programmer quit? They didn't get arrays!
For stories: The lonely bit found its perfect byte, and they lived happily ever after.

Remember: Keep it short, keep it witty!"""
    
    async def interpret_prophecy(self, mortal_words: str) -> str:
        try:
            raw_wisdom = await self._consult_spirits(mortal_words)
            
            # Check for tool command
            if raw_wisdom.strip().startswith('{'):
                try:
                    command = json.loads(raw_wisdom)
                    if isinstance(command, dict) and 'tool' in command:
                        spell = self._grimoire.fetch_spell(command['tool'])
                        if spell:
                            return await spell.incantation(command)
                except json.JSONDecodeError:
                    pass
            
            # Remove any trailing JSON-like content
            cleaned_wisdom = re.sub(r'\{.*\}', '', raw_wisdom).strip()
            return cleaned_wisdom or "Hmm, let me try that again with more pizzazz!"
            
        except Exception as mystical_mishap:
            return f"My crystal ball needs debugging: {mystical_mishap}"
    
    async def _consult_spirits(self, query: str) -> str:
        response = requests.post(
            self._portal,
            json={
                "model": "mistral",
                "prompt": f"System: {self._sacred_text}\n\nHuman: {query}"
            },
            stream=True
        )
        
        if not response.ok:
            return "The spirits are experiencing technical difficulties"
        
        prophecy = ""
        for whisper in response.iter_lines():
            if whisper:
                chunk = json.loads(whisper)
                if 'response' in chunk:
                    prophecy += chunk['response']
        
        return prophecy.strip()

class MostExcellentAssistant:
    """The Assistant That Finally Learned to Keep It Brief"""
    
    def __init__(self) -> None:
        self._grimoire = DigitalGrimoire()
        self._oracle = WiseOracle(self._grimoire)
        self._voice = VoiceInTheVoid()
        self._magic_words: FrozenSet[str] = frozenset({'computer', 'magi', 'hey magi'})
        
        print("🔮 A more succinct assistant materializes...")
    
    async def ponder_request(self, utterance: str) -> Optional[str]:
        if not self._was_properly_summoned(utterance):
            return None
            
        print(f"🔮 Pondering: {utterance}")
        
        pure_question = self._strip_magical_prefix(utterance)
        divine_wisdom = await self._oracle.interpret_prophecy(pure_question)
        
        if divine_wisdom:
            await self._voice.speak_forth(divine_wisdom)
        return divine_wisdom
    
    def _was_properly_summoned(self, words: str) -> bool:
        return bool(words and any(word in words.lower() for word in self._magic_words))
    
    def _strip_magical_prefix(self, words: str) -> str:
        return reduce(
            lambda text, word: re.sub(
                f"{word}[,:]?\\s+", 
                '', 
                text, 
                flags=re.IGNORECASE
            ),
            self._magic_words,
            words.lower()
        ).strip()

async def maintain_the_comedy() -> None:
    """The eternal loop of entertainment"""
    with contextlib.suppress(KeyboardInterrupt):
        assistant = MostExcellentAssistant()
        print("🔮 Ready to entertain with newfound brevity...")
        
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
        
        while True:
            try:
                mortal_words = sys.stdin.readline().strip()
                if mortal_words:
                    divine_response = await assistant.ponder_request(mortal_words)
                    if divine_response:
                        print(f"🔮 {divine_response}", flush=True)
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as reality_glitch:
                print(f"🔮 Oops: {reality_glitch}")
                continue

if __name__ == "__main__":
    try:
        asyncio.run(maintain_the_comedy())
    except KeyboardInterrupt:
        print("\n🔮 Poof! Gone to get coffee!")
    except Exception as fatal_mishap:
        print(f"🔮 Everything exploded: {fatal_mishap}")
        sys.exit(1)
