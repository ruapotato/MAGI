#!/usr/bin/env python3
from pathlib import Path
import sys
import argparse
from typing import Optional, Protocol
import time

class ScrollScribbler(Protocol):
   def inscribe_prophecy(self, utterance: str) -> None: ...

class TheGreatScribe:
   def __init__(self, sacred_grounds: Path = Path("/tmp/magi_realm/say")):
       self.hall_of_whispers = sacred_grounds
       self.hall_of_whispers.mkdir(parents=True, exist_ok=True)
       
   def inscribe_prophecy(self, utterance: str) -> None:
       # Each prophecy gets its own scroll, marked by time
       prophecy_scroll = self.hall_of_whispers / f"speak_these_words_{time.time()}.txt"
       prophecy_scroll.write_text(utterance)

def summon_scroll_of_arguments() -> argparse.ArgumentParser:
   scroll_of_commands = argparse.ArgumentParser(
       description="A humble scribe for the voice that echoes through time"
   )
   scroll_of_commands.add_argument(
       '-f', '--from-ancient-scroll',
       help="Read prophecies from this existing scroll",
       type=argparse.FileType('r')
   )
   scroll_of_commands.add_argument(
       'words_of_power',
       nargs='?',
       help="The utterance to be transformed into ethereal vibrations"
   )
   return scroll_of_commands

def gather_mystical_utterance(args) -> Optional[str]:
   if args.from_ancient_scroll:
       return args.from_ancient_scroll.read().strip()
   elif not sys.stdin.isatty():
       return sys.stdin.read().strip()
   elif args.words_of_power:
       return args.words_of_power
   return None

def transcribe_into_reality(scribe: ScrollScribbler, prophecy: Optional[str]) -> None:
   if not prophecy:
       return
   scribe.inscribe_prophecy(prophecy)

def main() -> None:
   scroll_of_commands = summon_scroll_of_arguments()
   ancient_wisdom = scroll_of_commands.parse_args()
   
   try:
       mystical_scribe = TheGreatScribe()
       prophecy = gather_mystical_utterance(ancient_wisdom)
       transcribe_into_reality(mystical_scribe, prophecy)
   except Exception as cosmic_disturbance:
       print(f"The ink spills: {cosmic_disturbance}", file=sys.stderr)
       sys.exit(1)

if __name__ == "__main__":
   main()
