#!/usr/bin/env python3
"""A mystical voice assistant that remembers its past lives"""

from dataclasses import dataclass, field
from typing import Protocol, NewType, Callable, AsyncIterator, AsyncGenerator
from typing import Optional, Dict, Any, List, Set, FrozenSet, Deque
from functools import partial, reduce, lru_cache
from collections import deque
import os
import sys
from pathlib import Path
import time
import json
import re
import asyncio
import signal
from datetime import datetime
import subprocess
import requests
import threading
import contextlib
import yt_dlp
from contextlib import asynccontextmanager

WhisperedProphecy = NewType('WhisperedProphecy', str)
AncientKnowledge = NewType('AncientKnowledge', Dict[str, Any])

@dataclass(frozen=True)
class ScrollOfPower:
    incantation: str
    description: str
    summon: Callable[[Dict[str, Any]], AsyncIterator[str]]
    portal_state: Dict[str, bool] = field(default_factory=lambda: {'is_channeling': False})

    @property
    def is_actively_channeling(self) -> bool:
        return self.portal_state['is_channeling']
    
    @asynccontextmanager
    async def mystical_channeling(self):
        self.portal_state['is_channeling'] = True
        try:
            yield
        finally:
            self.portal_state['is_channeling'] = False

class SageOfMemories:
    """Keeper of the ancient scrolls, because even magic needs version control"""
    
    def __init__(self, memory_capacity: int = 5):
        self.questions_of_old = deque(maxlen=memory_capacity)
        self.whispers_of_wisdom = deque(maxlen=memory_capacity)
        self.temporal_runes = deque(maxlen=memory_capacity)
        self.mortal_identities = {}
    
    def inscribe_prophecy(self, mortal_query: str, mystical_response: str) -> None:
        time_rune = datetime.now().strftime("%I:%M %p")
        self.questions_of_old.append(mortal_query)
        self.whispers_of_wisdom.append(mystical_response)
        self.temporal_runes.append(time_rune)
    
    def recall_ancient_scrolls(self, scroll_limit: int = 3) -> str:
        ancient_prophecies = list(zip(
            self.questions_of_old,
            self.whispers_of_wisdom,
            self.temporal_runes
        ))[-scroll_limit:]
        
        return "\n\n".join(
            f"[Past Exchange at {time}]\n"
            f"Previous Mortal Query: {q}\n"
            f"Ancient Response: {a}"
            for q, a, time in ancient_prophecies
        )

class EchoesInTheVoid:
    """Because silence is just magic waiting to happen"""
    
    def __init__(self) -> None:
        self._vocal_enchantment = threading.Lock()
        self._voice_dir = Path("/tmp/magi_realm/say")
        self._voice_dir.mkdir(parents=True, exist_ok=True)
    
    async def echo_forth(self, prophecy: str) -> None:
        if not prophecy.strip():
            return
        
        def _inscribe_prophecy():
            try:
                with self._vocal_enchantment:
                    prophecy_file = self._voice_dir / f"speak_these_words_{time.time()}.txt"
                    prophecy_file.write_text(prophecy)
            except Exception as e:
                print(f"Voice enchantment failed: {e}", file=sys.stderr)
        
        threading.Thread(
            target=_inscribe_prophecy,
            daemon=True
        ).start()

class GrimoireOfDigitalArts:
    """The tome that turns caffeine into code"""
    
    def __init__(self) -> None:
        self._mystical_toolbox = {
            "youtube_summoner": ScrollOfPower(
                "youtube_summoner",
                "Conjures digital entertainment",
                self._summon_digital_delights
            ),
            "time_oracle": ScrollOfPower(
                "time_oracle",
                "Reveals temporal truths",
                self._divine_temporal_secrets
            )
        }
    
    async def _summon_digital_delights(self, args: Dict[str, Any]) -> str:
        scroll = self._mystical_toolbox["youtube_summoner"]
        if scroll.is_actively_channeling:
            return "Patience, young wizard - one portal at a time!"
            
        async with scroll.mystical_channeling():
            try:
                with yt_dlp.YoutubeDL({
                    'format': 'best',
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': True
                }) as crystal_ball:
                    vision = await asyncio.to_thread(
                        crystal_ball.extract_info,
                        f"ytsearch1:{args['query']}",
                        download=False
                    )
                    
                    if not vision.get('entries'):
                        return "The digital aether is empty!"
                    
                    chosen_vision = vision['entries'][0]
                    portal_link = f"https://www.youtube.com/watch?v={chosen_vision['id']}"
                    
                    subprocess.Popen(
                        ['freetube', portal_link],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return f"Opening: {chosen_vision.get('title', 'a mysterious portal')}"
                    
            except Exception as mystical_mishap:
                return f"The entertainment portal misfired: {mystical_mishap}"
    
    async def _divine_temporal_secrets(self, _: Dict[str, Any]) -> str:
        return datetime.now().strftime("%I:%M %p")
    
    def fetch_mystical_scroll(self, scroll_name: str) -> Optional[ScrollOfPower]:
        return self._mystical_toolbox.get(scroll_name)
    
    @property
    def spell_anthology(self) -> str:
        return "\n".join(
            f"- {name}: {scroll.description}"
            for name, scroll in self._mystical_toolbox.items()
        )

class StreamingOracleOfWisdom:
    """Because even digital prophets need good bandwidth"""
    
    def __init__(self, grimoire: GrimoireOfDigitalArts, sage: SageOfMemories) -> None:
        self._mystical_gateway = "http://localhost:11434/api/generate"
        self._grimoire = grimoire
        self._sage = sage
        self._sacred_text = self._inscribe_sacred_rules()
    
    def _inscribe_sacred_rules(self) -> str:
        return f"""You are a witty assistant with mystical powers.
Available spells (use ONLY when explicitly requested):
{self._grimoire.spell_anthology}

Sacred Rules:
1. Focus on the current request, past exchanges are for context only
2. Never repeat or reprocess past commands
3. Past exchanges are marked with [Past Exchange at TIME] - these are just history
4. For calculations: Do math directly - no tools
   "What's 5 x 5?" -> "25, quicker than a caffeinated abacus!"

5. For jokes: Tell them directly - no videos
   "Tell a joke" -> "Why did the function feel sad? It had too many returns!"

6. Only use youtube_summoner for explicit video/music requests
   Good: "Play me a song" -> {{"tool": "youtube_summoner", "query": "relaxing music"}}
   Bad: "Tell me a joke" -> Just tell the joke

7. Only use time_oracle for current time requests
   Good: "What time is it?" -> Use {{"tool": "time_oracle"}}
   Bad: "What time is it?" -> something you made up, you must use a tool!

8. Keep responses short and witty
9. One tool per response
10. No explanations or commentary

Example mystical responses:
Time queries: 
- "Behold, the cosmic clock shows {{"tool": "time_oracle"}}"
- "The digital sundial reads {{"tool": "time_oracle"}}"

Music/video requests:
- "Your musical wish is granted: {{"tool": "youtube_summoner", "query": "requested song"}}"
- "Summoning entertainment: {{"tool": "youtube_summoner", "query": "specific video"}}"

Simple calculations:
- "7 x 6? That's 42, the answer to everything!"
- "Square root of 16? It's 4, faster than a caffeinated calculator!"

Jokes and wit:
- "Why did the programmer quit? They didn't get arrays!"
- "How do functions break up? They stop calling each other!"

Remember: Focus on the current request, past exchanges are just history!"""

    async def _channel_mystical_tool(self, spell_json: str) -> Optional[str]:
        try:
            command = json.loads(spell_json)
            if isinstance(command, dict) and 'tool' in command:
                if scroll := self._grimoire.fetch_mystical_scroll(command['tool']):
                    return await scroll.summon(command)
        except json.JSONDecodeError:
            pass
        return None

    async def channel_wisdom(self, mortal_query: str) -> AsyncGenerator[str, None]:
        ancient_wisdom = self._sage.recall_ancient_scrolls()
        contextual_prophecy = (
            f"Previous exchanges (for context only):\n{ancient_wisdom}\n\n"
            f"Current request to address:\nHuman: {mortal_query}"
        )
        
        response = requests.post(
            self._mystical_gateway,
            json={
                "model": "mistral",
                "prompt": f"System: {self._sacred_text}\n\n{contextual_prophecy}"
            },
            stream=True
        )

        if not response.ok:
            yield "The mystical connection is hazy"
            return

        current_prophecy = ""
        spell_buffer = ""
        channeling_spell = False

        for whisper in response.iter_lines():
            if not whisper:
                continue
                
            chunk = json.loads(whisper)
            if 'response' not in chunk:
                continue
                
            for rune in chunk['response']:
                if rune == '{':
                    channeling_spell = True
                    spell_buffer = rune
                elif channeling_spell:
                    spell_buffer += rune
                    if rune == '}':
                        channeling_spell = False
                        if spell_result := await self._channel_mystical_tool(spell_buffer):
                            current_prophecy = current_prophecy + spell_result
                            yield current_prophecy
                        spell_buffer = ""
                else:
                    current_prophecy += rune
                    if not channeling_spell:
                        yield current_prophecy

class MostExcellentAssistant:
    """The assistant that puts the 'fun' in 'functional programming'"""
    
    def __init__(self) -> None:
        self._sage = SageOfMemories()
        self._grimoire = GrimoireOfDigitalArts()
        self._oracle = StreamingOracleOfWisdom(self._grimoire, self._sage)
        self._voice = EchoesInTheVoid()
        self._mystical_triggers = frozenset({'computer', 'magi', 'hey magi'})
        
        print("🔮 A more historically-aware assistant materializes...")
    
    def _was_properly_invoked(self, utterance: str) -> bool:
        return bool(utterance and any(
            trigger in utterance.lower() 
            for trigger in self._mystical_triggers
        ))
    
    def _extract_pure_query(self, utterance: str) -> str:
        return reduce(
            lambda text, word: re.sub(
                f"{word}[,:]?\\s+", '', text, flags=re.IGNORECASE
            ),
            self._mystical_triggers,
            utterance.lower()
        ).strip()
    
    async def ponder_request(self, utterance: str) -> Optional[str]:
        if not self._was_properly_invoked(utterance):
            return None
            
        print(f"🔮 Pondering: {utterance}", file=sys.stderr)
        pure_question = self._extract_pure_query(utterance)
        final_wisdom = ""
        
        async for wisdom_fragment in self._oracle.channel_wisdom(pure_question):
            print(f"\r🔮 {wisdom_fragment}", end="", flush=True)
            final_wisdom = wisdom_fragment
        
        print(flush=True)
        
        if final_wisdom:
            await self._voice.echo_forth(final_wisdom)
            self._sage.inscribe_prophecy(pure_question, final_wisdom)
        
        return final_wisdom

async def maintain_eternal_vigil() -> None:
    """The endless watch, because sleep is for mortals"""
    with contextlib.suppress(KeyboardInterrupt):
        assistant = MostExcellentAssistant()
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
        
        while True:
            try:
                if mortal_words := sys.stdin.readline().strip():
                    await assistant.ponder_request(mortal_words)
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as mystical_mishap:
                print(f"🔮 Oops: {mystical_mishap}", file=sys.stderr)

if __name__ == "__main__":
    try:
        asyncio.run(maintain_eternal_vigil())
    except KeyboardInterrupt:
        print("\n🔮 Poof! Time for a mystical coffee break!")
    except Exception as catastrophic_failure:
        print(f"🔮 The magic went sideways: {catastrophic_failure}")
        sys.exit(1)
