# src/magi_shell/models/voice.py
"""
Voice model management for MAGI Shell.
"""

import subprocess
import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple
from pathlib import Path
from ..utils.paths import get_bin_path

@dataclass
class BaritoneWrangler:
    """Master of the Deep-Voiced Performers"""
    voice_artist: Optional[subprocess.Popen] = None
    green_room: Path = Path('/tmp/magi_realm/say')
    current_voice: str = "p326"  # Our leading bass
    
    def summon_the_bass_section(self) -> Tuple[bool, str]:
        """Raise the curtain on our deep-voiced performers"""
        try:
            self.green_room.mkdir(parents=True, exist_ok=True)
            self._escort_current_performer_offstage()
            
            script_path = get_bin_path() / 'start_voice_server.sh'
            self.voice_artist = subprocess.Popen(
                str(script_path),
                shell=True,
                executable='/bin/bash'
            )
            
            return self._await_dramatic_entrance()
            
        except Exception as stage_fright:
            return False, f"Performance anxiety: {stage_fright}"
    
    def _escort_current_performer_offstage(self):
        """Politely show our current voice actor to the exit"""
        if self.voice_artist:
            try:
                self.voice_artist.terminate()
                self.voice_artist.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.voice_artist.kill()
            self.voice_artist = None
    
    def _await_dramatic_entrance(self) -> Tuple[bool, str]:
        """Wait in the wings for our voice to warm up"""
        test_script = self.green_room / f"sound_check_{time.time()}.txt"
        try:
            test_script.write_text("♪ Do-Re-Mi ♪")
            time.sleep(2)  # Brief pause for dramatic effect
            
            if not test_script.exists():
                return True, "Voice warmed up and ready for the spotlight!"
            else:
                test_script.unlink()
                return False, "Voice caught a case of stage fright"
        except Exception as vocal_strain:
            return False, f"Technical difficulties: {vocal_strain}"
    
    def still_breathing(self) -> bool:
        """Make sure our vocalist hasn't fainted"""
        return self.voice_artist and self.voice_artist.poll() is None
    
    def clear_the_stage(self):
        """Time to go home, everyone"""
        self._escort_current_performer_offstage()
