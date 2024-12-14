#!/usr/bin/env python3
"""
🔮 The Not Dead Yet Voice Assistant 4.0 🔮
Finally executing tools instead of just talking about them!
"""

import os
import sys
import json
import re
import asyncio
import signal
from datetime import datetime
from typing import Union, Literal, TypedDict, Optional, Dict, Any, List, Callable, AsyncIterator, Tuple
from dataclasses import dataclass
import subprocess
import requests
import threading
from functools import partial
import yt_dlp
from typing_extensions import TypeGuard

@dataclass
class MysticalTool:
    name: str
    description: str
    async_spell: Callable
    example_incantation: str

@dataclass
class ProphecyParts:
    """Because sometimes prophecies need parsing"""
    tool_command: Optional[Dict[str, Any]] = None
    mortal_speech: Optional[str] = None

class TheVoiceInTheMachine:
    """For when silence isn't golden"""
    
    def __init__(self):
        self._throat_clearing_lock = threading.Lock()
    
    def speak_forth(self, proclamation: str) -> None:
        """Let the mortals hear our wisdom"""
        if not proclamation.strip():
            return
            
        def _summon_the_voice():
            with self._throat_clearing_lock:
                try:
                    subprocess.run(
                        ['espeak', '-s', '150', '-p', '50', '-a', '200', proclamation],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True
                    )
                except Exception as laryngitis:
                    print(f"🔮 Lost my voice: {laryngitis}")
        
        threading.Thread(target=_summon_the_voice, daemon=True).start()

class GrandArchiveOfTools:
    """The Tool Grimoire"""
    
    def __init__(self):
        self._sacred_toolbox = {
            "youtube_expert": MysticalTool(
                name="youtube_expert",
                description="Summons moving pictures from the tubes",
                async_spell=self._summon_youtube_content,
                example_incantation='{"tool": "youtube_expert", "query": "funny cats"}'
            ),
            "time_sage": MysticalTool(
                name="time_sage",
                description="Reveals the current position of celestial bodies",
                async_spell=self._consult_chronometer,
                example_incantation='{"tool": "time_sage"}'
            )
        }
    
    async def _summon_youtube_content(self, args: Dict[str, Any]) -> str:
        tube_gazing_config = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }
        
        try:
            with yt_dlp.YoutubeDL(tube_gazing_config) as crystal_ball:
                search_results = await asyncio.to_thread(
                    crystal_ball.extract_info,
                    f"ytsearch1:{args['query']}",
                    download=False
                )
                
                if not search_results.get('entries'):
                    return "The tubes are clogged. No videos found."
                
                chosen_video = search_results['entries'][0]
                video_portal = f"https://www.youtube.com/watch?v={chosen_video['id']}"
                
                subprocess.Popen(
                    ['freetube', video_portal],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return f"Summoning your entertainment: {chosen_video.get('title', 'a mysterious video')}"
                
        except Exception as tube_malfunction:
            return f"The tubes are broken: {tube_malfunction}"
    
    async def _consult_chronometer(self, _: Dict[str, Any]) -> str:
        return datetime.now().strftime("It is %I:%M %p in your mortal realm")
    
    def get_tool(self, tool_name: str) -> Optional[MysticalTool]:
        return self._sacred_toolbox.get(tool_name)
    
    @property
    def tool_descriptions(self) -> str:
        return "\n".join(
            f"{tool.name}: {tool.description}\nExample: {tool.example_incantation}\n"
            for tool in self._sacred_toolbox.values()
        )

class ProphecyInterpreter:
    """For when the Oracle speaks in riddles"""
    
    @staticmethod
    def extract_tool_command(prophecy: str) -> ProphecyParts:
        """Split the prophecy into tool commands and mortal speech"""
        tool_pattern = r'\{[^}]+\}'
        
        # Find the first JSON-like pattern
        tool_match = re.search(tool_pattern, prophecy)
        if not tool_match:
            return ProphecyParts(mortal_speech=prophecy.strip())
            
        try:
            tool_json = json.loads(tool_match.group())
            if isinstance(tool_json, dict) and 'tool' in tool_json:
                # Split the prophecy around the tool command
                parts = re.split(tool_pattern, prophecy, maxsplit=1)
                remaining_text = ' '.join(part.strip() for part in parts if part.strip())
                
                return ProphecyParts(
                    tool_command=tool_json,
                    mortal_speech=remaining_text if remaining_text else None
                )
        except json.JSONDecodeError:
            pass
            
        return ProphecyParts(mortal_speech=prophecy.strip())

class TheOmniscientOracle:
    """The Grand Orchestrator of Tools and Tales"""
    
    def __init__(self, tool_grimoire: GrandArchiveOfTools):
        self._sacred_gateway = "http://localhost:11434/api/generate"
        self._tool_grimoire = tool_grimoire
        self._prophecy_interpreter = ProphecyInterpreter()
        self._system_prompt = self._scribe_sacred_instructions()
    
    def _scribe_sacred_instructions(self) -> str:
        return f"""You are a witty voice assistant with access to these magical tools:

{self._tool_grimoire.tool_descriptions}

Important Instructions:
1. For tool use, respond with ONLY the tool JSON
2. For conversation, keep responses brief and witty
3. Choose either tool use OR conversation, never mix them
4. No need to describe what you're doing, just do it

Remember: Actions speak louder than words!"""
    
    async def divine_answer(self, mortal_query: str) -> Tuple[Optional[str], Optional[str]]:
        """Returns (tool_result, speech_result)"""
        try:
            raw_prophecy = await self._summon_wisdom(mortal_query)
            prophecy_parts = self._prophecy_interpreter.extract_tool_command(raw_prophecy)
            
            tool_result = None
            if prophecy_parts.tool_command:
                tool = self._tool_grimoire.get_tool(prophecy_parts.tool_command['tool'])
                if tool:
                    tool_result = await tool.async_spell(prophecy_parts.tool_command)
            
            return tool_result, prophecy_parts.mortal_speech
            
        except Exception as mystical_mishap:
            return None, f"The Oracle is having technical difficulties: {mystical_mishap}"
    
    async def _summon_wisdom(self, query: str) -> str:
        """Consult the Ollama spirits"""
        response = requests.post(
            self._sacred_gateway,
            json={
                "model": "mistral",
                "prompt": f"System: {self._system_prompt}\n\nHuman: {query}"
            },
            stream=True
        )
        
        if not response.ok:
            return "The Oracle is temporarily unreachable"
        
        prophecy = ""
        for whisper in response.iter_lines():
            if whisper:
                chunk = json.loads(whisper)
                if 'response' in chunk:
                    prophecy += chunk['response']
        
        return prophecy.strip()

class TheMostEnlightenedAssistant:
    """A voice assistant that finally does what it's told"""
    
    def __init__(self):
        self._tool_grimoire = GrandArchiveOfTools()
        self._oracle = TheOmniscientOracle(self._tool_grimoire)
        self._voice = TheVoiceInTheMachine()
        self._summoning_words = {'computer', 'magi', 'hey magi'}
        
        print("🔮 A properly working assistant awakens...")
    
    async def interpret_mortal_wishes(self, utterance: str) -> Optional[str]:
        """Now with 100% more tool execution!"""
        if not utterance or not self._heard_the_magic_words(utterance):
            return None
            
        print(f"🔮 Pondering: {utterance}")
        
        command = self._remove_magic_words(utterance)
        tool_result, speech_result = await self._oracle.divine_answer(command)
        
        if tool_result:
            self._voice.speak_forth(tool_result)
            return tool_result
        elif speech_result:
            self._voice.speak_forth(speech_result)
            return speech_result
        return None
    
    def _heard_the_magic_words(self, words: str) -> bool:
        return any(word in words.lower() for word in self._summoning_words)
    
    def _remove_magic_words(self, words: str) -> str:
        mortal_speech = words.lower()
        for magic_word in self._summoning_words:
            if magic_word in mortal_speech:
                mortal_speech = re.sub(
                    f"{magic_word}[,:]?\\s+", 
                    '', 
                    mortal_speech, 
                    flags=re.IGNORECASE
                )
        return mortal_speech.strip()

async def maintain_eternal_vigilance():
    """The main loop, now with actual tool execution"""
    # Silence the ALSA demons
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stderr.fileno())
    
    assistant = TheMostEnlightenedAssistant()
    print("🔮 Ready to serve (and actually execute tools)...")
    
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    
    while True:
        try:
            mortal_whispers = sys.stdin.readline().strip()
            if mortal_whispers:
                response = await assistant.interpret_mortal_wishes(mortal_whispers)
                if response:
                    print(f"🔮 {response}", flush=True)
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            break
        except Exception as cosmic_disturbance:
            print(f"🔮 A disturbance in the force: {cosmic_disturbance}")
            continue

if __name__ == "__main__":
    try:
        asyncio.run(maintain_eternal_vigilance())
    except KeyboardInterrupt:
        print("\n🔮 The spirits bid you farewell!")
    except Exception as catastrophic_failure:
        print(f"🔮 The magic has failed catastrophically: {catastrophic_failure}")
        sys.exit(1)
