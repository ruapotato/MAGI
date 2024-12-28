#!/usr/bin/env python3
from dataclasses import dataclass
from functools import partial
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
from typing import Iterator, Optional, Literal, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
import prctl
from TTS.api import TTS
import torch
import sounddevice as sd
import soundfile as sf

VoiceActor = Literal[
    "p226",  # The Mysterious Baritone
    "p326",  # The Dramatic Bass
    "p330",  # The Smooth Operator
    "p347"   # The Gentle Giant
]

CURRENT_VOICE_ACTOR: VoiceActor = "p326"  # Our star performer for today's show

@dataclass
class ModelTreasureMap:
    possible_hideouts: List[Path] = None
    
    def __post_init__(self):
        home_stage = Path.home() / "voice_models"
        corporate_theater = Path("/opt/magi/voice_models")
        touring_company = Path("tts_models/en/vctk/vits")
        
        self.possible_hideouts = [
            home_stage / "magi_voice",
            corporate_theater / "magi_voice",
            touring_company  # Our touring performer, always ready to go
        ]

@dataclass
class BaritoneBoxOfWonders:
    deep_voiced_oracle: TTS
    temporary_bass_chamber: Path = Path(tempfile.mkdtemp())
    
    @classmethod
    def summon_barry_white_but_open_source(cls) -> 'BaritoneBoxOfWonders':
        treasure_map = ModelTreasureMap()
        
        # Our talent scout searches high and low for the perfect voice
        for potential_dressing_room in treasure_map.possible_hideouts:
            try:
                if potential_dressing_room.exists() and potential_dressing_room.is_dir():
                    print(f"🎭 Found our star in {potential_dressing_room}!")
                    return cls(TTS.load_from_pretrained(potential_dressing_room)
                             .to("cuda" if torch.cuda.is_available() else "cpu"))
                elif str(potential_dressing_room).startswith("tts_models"):
                    print("🌟 Summoning our touring performer!")
                    return cls(TTS(
                        model_name=str(potential_dressing_room),
                        progress_bar=False
                    ).to("cuda" if torch.cuda.is_available() else "cpu"))
            except Exception as stage_fright:
                print(f"😅 No luck at {potential_dressing_room}: {stage_fright}")
                continue
                
        raise RuntimeError("🎭 Catastrophe! All our performers called in sick!")
    
    def transmute_whispers_to_rumbles(self, utterance_of_mortals: str) -> Path:
        manly_manifestation = self.temporary_bass_chamber / f"deep_thoughts_{time.time()}.wav"
        self.deep_voiced_oracle.tts_to_file(
            text=utterance_of_mortals, 
            file_path=str(manly_manifestation),
            speaker=CURRENT_VOICE_ACTOR
        )
        return manly_manifestation

class ScrollKeeperOfTheDeepVoices(FileSystemEventHandler):
    def __init__(self, vocal_titan: BaritoneBoxOfWonders):
        self.voice = vocal_titan
        
    def on_created(self, event: FileCreatedEvent):
        if not event.is_directory and event.src_path.endswith('.txt'):
            self.summon_the_bass_drop(Path(event.src_path))
    
    def summon_the_bass_drop(self, ancient_scroll: Path):
        try:
            profound_utterances = ancient_scroll.read_text().strip()
            if not profound_utterances:
                return
                
            manly_scroll = self.voice.transmute_whispers_to_rumbles(profound_utterances)
            self.perform_movie_trailer_voice(manly_scroll)
            manly_scroll.unlink()  # The echoes fade to silence
            ancient_scroll.unlink() # Our work here is done
        except Exception as voice_crack:
            print(f"The bass dropped too hard: {voice_crack}", file=sys.stderr)

    def perform_movie_trailer_voice(self, sonic_scroll: Path):
        mild_mannered_alter_ego = prctl.get_name()
        prctl.set_name("espeak")  # Don the mask of the vanilla voice
        
        bass_frequencies, sampling_rate_of_destiny = sf.read(str(sonic_scroll))
        sd.play(bass_frequencies, sampling_rate_of_destiny)
        sd.wait()  # Hold for dramatic effect
        
        prctl.set_name(mild_mannered_alter_ego)  # Return to our day job

def prepare_backstage_area() -> Path:
    voice_actors_lounge = Path('/tmp/magi_realm/say')
    voice_actors_lounge.mkdir(parents=True, exist_ok=True)
    return voice_actors_lounge

def eternal_improv_session(green_room: Path):
    leading_man = BaritoneBoxOfWonders.summon_barry_white_but_open_source()
    talent_scout = ScrollKeeperOfTheDeepVoices(leading_man)
    
    casting_director = Observer()
    casting_director.schedule(talent_scout, str(green_room), recursive=False)
    casting_director.start()
    
    try:
        while True:
            time.sleep(1)  # Awaiting our cue
    except KeyboardInterrupt:
        casting_director.stop()
    casting_director.join()

if __name__ == "__main__":
    stage_door = prepare_backstage_area()
    eternal_improv_session(stage_door)
