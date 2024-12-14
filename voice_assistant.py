#!/usr/bin/env python3
"""A mystical voice assistant that knows when to stop talking"""

from dataclasses import dataclass, field
from typing import Protocol, NewType, Callable, AsyncIterator, AsyncGenerator, Deque
from typing import Optional, Dict, Any, List, Set, FrozenSet
from functools import partial, reduce, lru_cache
from collections import deque
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
import yt_dlp
from contextlib import asynccontextmanager

@dataclass(frozen=True)
class EnchantedScroll:
    name: str
    description: str
    summon: Callable[[Dict[str, Any]], AsyncIterator[str]]
    _mystical_state: Dict[str, bool] = field(default_factory=lambda: {'portal_open': False})

    @property
    def is_summoning(self) -> bool:
        return self._mystical_state['portal_open']
    
    @asynccontextmanager
    async def summoning_circle(self):
        self._mystical_state['portal_open'] = True
        try:
            yield
        finally:
            self._mystical_state['portal_open'] = False

class MemoryKeeper:
    def __init__(self, memory_span: int = 5):
        self.past_questions = deque(maxlen=memory_span)
        self.past_answers = deque(maxlen=memory_span)
        self.known_mortals = {}
    
    def remember(self, question: str, answer: str) -> None:
        self.past_questions.append(question)
        self.past_answers.append(answer)
    
    def recall_recent(self, limit: int = 3) -> str:
        history = list(zip(self.past_questions, self.past_answers))[-limit:]
        return "\n\n".join(f"Human: {q}\nAssistant: {a}" for q, a in history)

class VoiceOfTheVoid:
    def __init__(self) -> None:
        self._voice_lock = threading.Lock()
        
    async def speak(self, wisdom: str) -> None:
        if not wisdom.strip():
            return
            
        threading.Thread(
            target=lambda: self._voice_lock.acquire()
            and subprocess.run(
                ['espeak', '-s', '150', '-p', '50', '-a', '200', wisdom],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            and self._voice_lock.release(),
            daemon=True
        ).start()

class Grimoire:
    def __init__(self) -> None:
        self._enchantments = {
            "youtube_summoner": EnchantedScroll(
                "youtube_summoner",
                "Summons digital entertainment",
                self._summon_tube_portal
            ),
            "time_oracle": EnchantedScroll(
                "time_oracle",
                "Reveals temporal truths",
                self._peek_at_time
            )
        }
    
    async def _summon_tube_portal(self, args: Dict[str, Any]) -> str:
        spell = self._enchantments["youtube_summoner"]
        if spell.is_summoning:
            return "One portal at a time, dear friend!"
            
        async with spell.summoning_circle():
            try:
                with yt_dlp.YoutubeDL({
                    'format': 'best',
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': True
                }) as crystal:
                    vision = await asyncio.to_thread(
                        crystal.extract_info,
                        f"ytsearch1:{args['query']}",
                        download=False
                    )
                    
                    if not vision.get('entries'):
                        return "The tubes are mysteriously empty!"
                    
                    chosen = vision['entries'][0]
                    portal = f"https://www.youtube.com/watch?v={chosen['id']}"
                    
                    subprocess.Popen(
                        ['freetube', portal],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return f"Opening: {chosen.get('title', 'a mysterious portal')}"
                    
            except Exception as e:
                return f"The portal failed: {e}"
    
    async def _peek_at_time(self, _: Dict[str, Any]) -> str:
        return datetime.now().strftime("%I:%M %p")
    
    def fetch_spell(self, name: str) -> Optional[EnchantedScroll]:
        return self._enchantments.get(name)
    
    @property
    def spell_list(self) -> str:
        return "\n".join(
            f"- {name}: {scroll.description}"
            for name, scroll in self._enchantments.items()
        )

class StreamingOracle:
    def __init__(self, grimoire: Grimoire, memory: MemoryKeeper) -> None:
        self._portal = "http://localhost:11434/api/generate"
        self._grimoire = grimoire
        self._memory = memory
        self._sacred_text = f"""You are a witty assistant with mystical powers.
Available spells (use ONLY when explicitly requested):
{self._grimoire.spell_list}

Sacred Rules:
1. For calculations: Do math directly - no tools
   "What's 5 x 5?" -> "25, quicker than a caffeinated abacus!"

2. For jokes: Tell them directly - no videos
   "Tell a joke" -> "Why did the function feel sad? It had too many returns!"

3. Only use youtube_summoner for explicit video/music requests
   Good: "Play me a song" -> Use youtube_summoner
   Bad: "Tell me a joke" -> Just tell the joke

4. Only use time_oracle for time requests
   Good: "What time is it?" -> Use time_oracle
   Bad: "Tell a joke" -> Just tell the joke
   Bad: "What time is it?" -> something you made up, use {{"tool": "time_oracle"}}

5. Keep responses short and witty
6. Remember context from past exchanges
7. One tool per response
8. No explanations or commentary

Example responses:
Math: "7 x 6? That's 42, the answer to everything!"
Joke: "Why did the programmer quit? They didn't get arrays!"
Time: "The mystical clock shows {{"tool": "time_oracle"}}"
Video: "Summoning your requested entertainment: {{"tool": "youtube_summoner", "query": "requested song"}}"

Remember: Brief, witty, and precisely on-task!"""

    async def _process_spell(self, spell_json: str) -> Optional[str]:
        try:
            command = json.loads(spell_json)
            if isinstance(command, dict) and 'tool' in command:
                if spell := self._grimoire.fetch_spell(command['tool']):
                    return await spell.summon(command)
        except json.JSONDecodeError:
            pass
        return None

    async def divine_wisdom(self, query: str) -> AsyncGenerator[str, None]:
        context = self._memory.recall_recent()
        response = requests.post(
            self._portal,
            json={
                "model": "mistral",
                "prompt": f"System: {self._sacred_text}\n\nPrevious exchanges:\n{context}\n\nHuman: {query}"
            },
            stream=True
        )

        if not response.ok:
            yield "The mystical connection is hazy"
            return

        prophecy = ""
        spell_buffer = ""
        casting_spell = False

        for line in response.iter_lines():
            if not line:
                continue
                
            chunk = json.loads(line)
            if 'response' not in chunk:
                continue
                
            for rune in chunk['response']:
                if rune == '{':
                    casting_spell = True
                    spell_buffer = rune
                elif casting_spell:
                    spell_buffer += rune
                    if rune == '}':
                        casting_spell = False
                        if spell_result := await self._process_spell(spell_buffer):
                            prophecy = prophecy + spell_result
                            yield prophecy
                        spell_buffer = ""
                else:
                    prophecy += rune
                    if not casting_spell:
                        yield prophecy

class WiseAssistant:
    def __init__(self) -> None:
        self._memories = MemoryKeeper()
        self._grimoire = Grimoire()
        self._oracle = StreamingOracle(self._grimoire, self._memories)
        self._voice = VoiceOfTheVoid()
        self._wake_words = frozenset({'computer', 'magi', 'hey magi'})
        
        print("🔮 A more focused assistant materializes...")
    
    def _was_summoned(self, words: str) -> bool:
        return bool(words and any(
            wake_word in words.lower() 
            for wake_word in self._wake_words
        ))
    
    def _strip_wake_words(self, words: str) -> str:
        return reduce(
            lambda text, word: re.sub(
                f"{word}[,:]?\\s+", '', text, flags=re.IGNORECASE
            ),
            self._wake_words,
            words.lower()
        ).strip()
    
    async def ponder(self, query: str) -> Optional[str]:
        if not self._was_summoned(query):
            return None
            
        print(f"🔮 Pondering: {query}", file=sys.stderr)
        pure_query = self._strip_wake_words(query)
        last_wisdom = ""
        
        async for wisdom in self._oracle.divine_wisdom(pure_query):
            print(f"\r🔮 {wisdom}", end="", flush=True)
            last_wisdom = wisdom
        
        print(flush=True)
        
        if last_wisdom:
            await self._voice.speak(last_wisdom)
            self._memories.remember(pure_query, last_wisdom)
        
        return last_wisdom

async def eternal_watch() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        assistant = WiseAssistant()
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
        
        while True:
            try:
                if query := sys.stdin.readline().strip():
                    await assistant.ponder(query)
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"🔮 Oops: {e}", file=sys.stderr)

if __name__ == "__main__":
    try:
        asyncio.run(eternal_watch())
    except KeyboardInterrupt:
        print("\n🔮 Poof! Coffee break time!")
    except Exception as e:
        print(f"🔮 Everything exploded: {e}")
        sys.exit(1)
