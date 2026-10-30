"""Generate the sound effects used by the pitch video, locally, with numpy.

Run with the Piper venv from the demos/ folder:
    ~/.local/share/dana-tts-venv/bin/python scripts/sfx.py
"""

import wave
from pathlib import Path

import numpy as np

RATE = 44100
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "public" / "audio" / "sfx"


def write(name: str, samples: np.ndarray) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    peak = np.max(np.abs(samples)) or 1.0
    pcm = (samples / peak * 0.8 * 32767).astype("<i2")
    with wave.open(str(OUT_DIR / f"{name}.wav"), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(RATE)
        wav_file.writeframes(pcm.tobytes())


def t_axis(seconds: float) -> np.ndarray:
    return np.linspace(0, seconds, int(RATE * seconds), endpoint=False)


def whoosh(seconds: float = 0.7) -> np.ndarray:
    t = t_axis(seconds)
    noise = np.random.default_rng(7).standard_normal(t.size)
    cutoff = np.linspace(0.02, 0.35, t.size)
    filtered = np.zeros_like(noise)
    acc = 0.0
    for i, (x, a) in enumerate(zip(noise, cutoff)):
        acc += a * (x - acc)
        filtered[i] = acc
    envelope = np.sin(np.pi * t / seconds) ** 2
    return filtered * envelope


def pop(seconds: float = 0.18) -> np.ndarray:
    t = t_axis(seconds)
    freq = np.linspace(520, 980, t.size)
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    return np.sin(phase) * np.exp(-t * 28)


def click(seconds: float = 0.05) -> np.ndarray:
    t = t_axis(seconds)
    return np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 120)


def chime(notes: list[float], seconds: float = 1.2) -> np.ndarray:
    t = t_axis(seconds)
    out = np.zeros_like(t)
    for i, freq in enumerate(notes):
        start = i * 0.09
        local = np.clip(t - start, 0, None)
        tone = np.sin(2 * np.pi * freq * local) + 0.3 * np.sin(4 * np.pi * freq * local)
        out += tone * np.exp(-local * 4.5) * (t >= start)
    return out


def main() -> None:
    write("whoosh", whoosh())
    write("pop", pop())
    write("click", click())
    write("chime", chime([659.25, 783.99, 987.77, 1318.5]))
    write("success", chime([523.25, 659.25, 783.99], seconds=0.9))
    print(f"wrote sound effects to {OUT_DIR}")


if __name__ == "__main__":
    main()
