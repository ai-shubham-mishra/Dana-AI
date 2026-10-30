"""Synthesise narration clips with Piper and write per-scene durations.

Run with the Piper venv from the demos/ folder:
    ~/.local/share/dana-tts-venv/bin/python scripts/narrate.py
"""

import json
import wave
from pathlib import Path

from piper import PiperVoice

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "src" / "script.json"
OUT_DIR = ROOT / "public" / "audio" / "narration"
TIMING = ROOT / "src" / "timing.json"
VOICE = Path.home() / ".local" / "share" / "dana-piper-voices" / "en_US-amy-medium.onnx"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    voice = PiperVoice.load(str(VOICE))
    timing = {}
    for scene in json.loads(SCRIPT.read_text()):
        out = OUT_DIR / f"{scene['id']}.wav"
        with wave.open(str(out), "wb") as wav_file:
            voice.synthesize_wav(scene["text"], wav_file)
        with wave.open(str(out), "rb") as wav_file:
            seconds = wav_file.getnframes() / wav_file.getframerate()
        timing[scene["id"]] = round(seconds, 2)
        print(f"{scene['id']}: {seconds:.2f}s")
    TIMING.write_text(json.dumps(timing, indent=2) + "\n")


if __name__ == "__main__":
    main()
