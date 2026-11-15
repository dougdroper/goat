"""Generates all Goatman sounds as .ogg files.

Run:  tools/.venv/bin/python -I tools/generate_sounds.py
Uses the macOS `say` command for the voices.

Mono files are positional in Minecraft (you can tell which direction they come from).
Stereo files play "inside your head" — used for the jump scare and the whisper.
"""
import os
import subprocess
import tempfile

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "Goatman_RP", "sounds", "goatman")
SR = 44100
rng = np.random.default_rng(13)


# ----------------------------------------------------------------- helpers
def say(voice, text, rate=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "v.aiff")
        cmd = ["say", "-v", voice, "-o", path]
        if rate:
            cmd += ["-r", str(rate)]
        subprocess.run(cmd + [text], check=True)
        data, sr = sf.read(path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return resample(data, sr, 1.0)


def resample(x, sr_in, factor):
    """Resample to SR. factor < 1 = slower + deeper, factor > 1 = faster + higher."""
    n_out = int(len(x) * SR / sr_in / factor)
    return np.interp(np.linspace(0, len(x) - 1, n_out), np.arange(len(x)), x).astype(np.float32)


def deeper(x, factor):
    return resample(x, SR, factor)


def band(x, lo, hi):
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    mask = 1.0 / (1 + (lo / np.maximum(f, 1)) ** 4) / (1 + (f / hi) ** 4)
    return np.fft.irfft(spec * mask, len(x)).astype(np.float32)


def reverb(x, seconds=1.8, wet=0.4, decay=3.5):
    n = int(SR * seconds)
    ir = rng.uniform(-1, 1, n) * np.exp(-np.arange(n) / SR * decay)
    ir[0] = 0
    size = len(x) + n
    wet_sig = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:size]
    wet_sig /= np.max(np.abs(wet_sig)) + 1e-9
    out = np.zeros(size, dtype=np.float32)
    out[: len(x)] += x * (1 - wet)
    out += wet_sig * wet * np.max(np.abs(x))
    return out


def pad(x, before=0.0, after=0.0):
    return np.concatenate([np.zeros(int(SR * before)), x, np.zeros(int(SR * after))]).astype(np.float32)


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n, dtype=np.float32)
    for p in parts:
        out[: len(p)] += p
    return out


def normalize(x, peak=0.9):
    return (x / (np.max(np.abs(x)) + 1e-9) * peak).astype(np.float32)


def save(name, x, ceiling=0.97):
    """Write Ogg Vorbis, turning it down until the *decoded* file doesn't clip
    (lossy encoding of harsh noise can overshoot by 70%+)."""
    path = os.path.join(OUT, name + ".ogg")
    for _ in range(8):
        sf.write(path, x, SR, format="OGG", subtype="VORBIS")
        peak = float(np.max(np.abs(sf.read(path, dtype="float32")[0])))
        if peak <= ceiling:
            break
        x = (x * (ceiling / peak) * 0.98).astype(np.float32)
    ch = 1 if x.ndim == 1 else x.shape[1]
    print(f"  {name}.ogg  {len(x) / SR:.1f}s  {'mono' if ch == 1 else 'stereo'}  peak {peak:.2f}")


def saw(freq):
    return 2.0 * ((np.cumsum(freq) / SR) % 1.0) - 1.0


# ----------------------------------------------------------------- screams
def scream(dur, start_hz, drop_hz, impact=True, detune=1.0):
    t = np.arange(int(SR * dur)) / SR
    f0 = start_hz - drop_hz * (t / dur) ** 0.7 + 45 * np.sin(2 * np.pi * 7.5 * t)
    sig = sum(saw(f0 * k * detune) for k in (1.0, 1.012, 0.991, 1.414))
    sig *= 0.62 + 0.38 * np.sin(2 * np.pi * 17 * t)  # goat-like bleat warble
    growl = saw(np.full_like(t, 68 * detune)) * (0.6 + 0.4 * rng.random(len(t)))
    env = np.clip(t / 0.01, 0, 1) * np.clip((dur - t) / (dur * 0.3), 0, 1)
    out = (sig * 0.5 + growl * 0.45 + rng.uniform(-0.35, 0.35, len(t))) * env
    if impact:
        out += rng.uniform(-1, 1, len(t)) * np.exp(-t * 25) * 3.0 + np.sin(2 * np.pi * 50 * t) * np.exp(-t * 8) * 2.0
    out = np.tanh(out * 2.2)
    return normalize(band(out.astype(np.float32), 30, 7000), 0.95)  # tame the fizz


os.makedirs(OUT, exist_ok=True)
print("Generating sounds:")

# Jump scare: stereo, right in your face.
save("jumpscare", np.stack([scream(2.4, 1150, 420), scream(2.4, 1150, 420, detune=1.006)], axis=1))

# Roar when he stops staring and starts to chase: mono so you can hear where he is.
save("roar", normalize(reverb(scream(1.4, 800, 350, impact=False), 1.2, 0.3), 0.95))

# "I see you" — whispered in your ear, with a deep voice underneath.
for i, (text, rate, slow) in enumerate((("I see you.", 110, 0.85), ("I... see... you...", 90, 0.8)), start=1):
    whisper = deeper(say("Whisper", text, rate), slow)
    deep = deeper(say("Ralph", text, rate), 0.62) * 0.35
    voice = normalize(reverb(mix(whisper, deep), 1.4, 0.3))
    if i == 2:  # reversed reverb swell before the words
        swell = reverb(voice[::-1].copy(), 1.5, 0.9)[::-1]
        voice = normalize(mix(pad(voice, 1.0), swell[: len(voice) + SR]))
    voice = pad(voice, 0.1, 0.3)
    t = np.arange(len(voice)) / SR
    pan = 0.5 + 0.45 * np.sin(2 * np.pi * 0.35 * t)  # slowly drifts from ear to ear
    save(f"i_see_you_{i}", np.stack([voice * (1 - pan), voice * pan], axis=1) * 1.05)

# Distant cries for help (mono = positional).
HELP = (
    ("Samantha", "Help! Somebody, help me!", 175, 1.0),
    ("Moira", "Is anyone there? Please, help me!", 165, 1.0),
    ("Karen", "Help! Help!", 180, 1.02),
)
for i, (voice_name, text, rate, pitch) in enumerate(HELP, start=1):
    v = deeper(say(voice_name, text, rate), pitch)
    v = band(v, 350, 2400)  # far away = thin and muffled
    save(f"help_{i}", normalize(pad(reverb(v, 2.2, 0.55, 2.5), 0.05), 0.85))

# The creepy one: a voice calling for help... that drops into something not human.
v = say("Samantha", "Help me.", 150)
low = deeper(v, 0.5)
creepy = mix(v, pad(low, len(v) / SR + 0.6))
creepy = band(creepy, 120, 2600)
save("help_4", normalize(pad(reverb(creepy, 2.5, 0.55, 2.2), 0.05), 0.85))
