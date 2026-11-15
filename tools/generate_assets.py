"""Generates the Goatman model, textures, jump-scare image, pack icons and scream sound.

Run:  tools/.venv/bin/python tools/generate_assets.py
"""
import json
import math
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RP = os.path.join(ROOT, "Goatman_RP")
BP = os.path.join(ROOT, "Goatman_BP")
rng = np.random.default_rng(666)

# ---------------------------------------------------------------- model
TEX_W, TEX_H = 128, 128

# (bone, origin, size, uv, paint-style)
CUBES = []
BONES = {}


def bone(name, parent, pivot, rotation=None):
    b = {"name": name, "pivot": pivot, "cubes": []}
    if parent:
        b["parent"] = parent
    if rotation:
        b["rotation"] = rotation
    BONES[name] = b


def cube(bone_name, origin, size, uv, style):
    BONES[bone_name]["cubes"].append({"origin": origin, "size": size, "uv": uv})
    CUBES.append((origin, size, uv, style))


bone("root", None, [0, 0, 0])
bone("leftLeg", "root", [2.5, 22, 0])
bone("rightLeg", "root", [-2.5, 22, 0])
bone("body", "root", [0, 22, 0])
bone("leftArm", "body", [6.5, 38, 0])
bone("rightArm", "body", [-6.5, 38, 0])
bone("neck", "body", [0, 39, 0])
bone("head", "neck", [0, 42, 0])
bone("hornL1", "head", [2.5, 49, 0], [-20, 0, -20])
bone("hornL2", "hornL1", [2.5, 54, 0], [-30, 0, -10])
bone("hornL3", "hornL2", [2.5, 59, 0], [-35, 0, 0])
bone("hornR1", "head", [-2.5, 49, 0], [-20, 0, 20])
bone("hornR2", "hornR1", [-2.5, 54, 0], [-30, 0, 10])
bone("hornR3", "hornR2", [-2.5, 59, 0], [-35, 0, 0])

cube("leftLeg", [1, 0, -1.5], [3, 22, 3], [0, 0], "limb")
cube("rightLeg", [-4, 0, -1.5], [3, 22, 3], [0, 0], "limb")
cube("body", [-4, 20, -2.5], [8, 6, 5], [24, 15], "fur")
cube("body", [-2, 26, -1.5], [4, 3, 3], [54, 0], "skin")
cube("body", [-5, 29, -2.5], [10, 10, 5], [24, 0], "chest")
cube("leftArm", [5, 12, -1.5], [3, 27, 3], [12, 0], "limb")
cube("rightArm", [-8, 12, -1.5], [3, 27, 3], [12, 0], "limb")
for x, length in ((5, 4), (6, 5), (7, 4)):
    uv = [68, 0] if length == 4 else [72, 0]
    cube("leftArm", [x, 12 - length, -1.5], [1, length, 1], uv, "claw")
    cube("rightArm", [-x - 1, 12 - length, -1.5], [1, length, 1], uv, "claw")
cube("neck", [-1.5, 38, -1.5], [3, 4, 3], [54, 6], "skin")
cube("head", [-3.5, 42, -3.5], [7, 7, 7], [0, 32], "skull")
cube("head", [-2.5, 41, -8.5], [5, 5, 5], [28, 32], "snout")
cube("head", [-2, 39.5, -8], [4, 2, 4], [48, 32], "jaw")
cube("head", [-1, 36.5, -7.5], [2, 3, 1], [96, 32], "fur")  # beard
cube("head", [3.5, 46, -1], [3, 1, 2], [88, 40], "skin")  # ears
cube("head", [-6.5, 46, -1], [3, 1, 2], [88, 40], "skin")
for side in ("L", "R"):
    s = 1 if side == "L" else -1
    cube(f"horn{side}1", [1.5 if s > 0 else -3.5, 49, -1], [2, 5, 2], [64, 32], "horn")
    cube(f"horn{side}2", [1.75 if s > 0 else -3.25, 54, -0.75], [1.5, 5, 1.5], [72, 32], "horn")
    cube(f"horn{side}3", [2 if s > 0 else -3, 59, -0.5], [1, 3, 1], [80, 32], "horn")

geo = {
    "format_version": "1.12.0",
    "minecraft:geometry": [
        {
            "description": {
                "identifier": "geometry.goatman",
                "texture_width": TEX_W,
                "texture_height": TEX_H,
                "visible_bounds_width": 3,
                "visible_bounds_height": 5,
                "visible_bounds_offset": [0, 2, 0],
            },
            "bones": list(BONES.values()),
        }
    ],
}
with open(os.path.join(RP, "models/entity/goatman.geo.json"), "w") as f:
    json.dump(geo, f, indent=2)

# ---------------------------------------------------------------- entity texture
tex = np.zeros((TEX_H, TEX_W, 4), dtype=np.uint8)

PALETTE = {
    "skin": (58, 44, 38),
    "limb": (50, 39, 33),
    "fur": (42, 30, 22),
    "chest": (58, 44, 38),
    "skull": (212, 202, 178),
    "snout": (205, 194, 170),
    "jaw": (180, 168, 145),
    "horn": (70, 62, 55),
    "claw": (28, 24, 22),
}


def put(x, y, color, alpha=255):
    if 0 <= x < TEX_W and 0 <= y < TEX_H:
        tex[y, x] = (*color, alpha)


def shade(color, amount):
    return tuple(int(max(0, min(255, c + amount))) for c in color)


def faces(origin, size, uv):
    """Box-UV face rectangles: name -> (x, y, w, h)."""
    w, h, d = (int(math.floor(s)) or 1 for s in size)
    u, v = uv
    return {
        "top": (u + d, v, w, d),
        "bottom": (u + d + w, v, w, d),
        "right": (u, v + d, d, h),
        "front": (u + d, v + d, w, h),
        "left": (u + d + w, v + d, d, h),
        "back": (u + 2 * d + w, v + d, w, h),
    }


painted = set()
for origin, size, uv, style in CUBES:
    key = (tuple(uv), style)
    if key in painted:
        continue
    painted.add(key)
    base = PALETTE[style]
    f = faces(origin, size, uv)
    for name, (fx, fy, fw, fh) in f.items():
        for yy in range(fh):
            for xx in range(fw):
                n = rng.integers(-10, 11)
                c = shade(base, n)
                if style == "fur" and (xx + rng.integers(0, 2)) % 2 == 0:
                    c = shade(c, -12)
                if style == "limb" and yy % 11 in (0, 1):  # knobbly joints
                    c = shade(c, -14)
                if style == "horn" and yy % 2 == 0:
                    c = shade(c, -20)
                if style in ("skull", "snout") and rng.random() < 0.06:
                    c = shade(c, -60)  # cracks / grime
                if style == "chest" and name in ("front", "back") and yy % 2 == 1 and 0 < xx < fw - 1:
                    c = shade(base, 30)  # ribs
                put(fx + xx, fy + yy, c)

    if style == "skull":
        fx, fy, fw, fh = f["front"]
        for cx in (1, 4):  # eye sockets (2x2) with glowing red pupils
            for dy in (1, 2):
                for dx in (0, 1):
                    put(fx + cx + dx, fy + dy, (8, 4, 4))
            put(fx + cx + (1 if cx == 1 else 0), fy + 2, (255, 30, 20), alpha=0)
            put(fx + cx + (0 if cx == 1 else 1), fy + 1, (180, 10, 10), alpha=0)
    if style == "snout":
        fx, fy, fw, fh = f["front"]
        put(fx + 1, fy + 1, (10, 6, 6))
        put(fx + 3, fy + 1, (10, 6, 6))
        for xx in range(fw):  # teeth
            put(fx + xx, fy + fh - 1, (235, 228, 205) if xx % 2 == 0 else (20, 10, 10))
    if style == "jaw":
        fx, fy, fw, fh = f["front"]
        for xx in range(fw):
            put(fx + xx, fy, (240, 232, 210) if xx % 2 else (90, 10, 10))
    if style == "claw":
        fx, fy, fw, fh = f["front"]
        put(fx, fy + fh - 1, (120, 10, 10))  # bloody tip

Image.fromarray(tex, "RGBA").save(os.path.join(RP, "textures/entity/goatman.png"))

# ---------------------------------------------------------------- jump-scare face
AW, AH = 112, 64  # pixel-art canvas (16:9-ish so it fills a wide screen)
art = Image.new("RGB", (AW, AH), (0, 0, 0))
px = art.load()
cx, cy = AW // 2, AH // 2
for y in range(AH):  # blood-red vignette
    for x in range(AW):
        d = math.hypot((x - cx) / AW, (y - cy) / AH)
        r = int(max(0, 90 - d * 160) + rng.integers(0, 12))
        px[x, y] = (r, 0, 0)

dr = ImageDraw.Draw(art)
horn = (66, 56, 48)
horn_dark = (40, 33, 28)
dr.line([(cx - 10, 10), (cx - 18, 3), (cx - 30, 0), (cx - 40, 4), (cx - 44, 12)], fill=horn, width=5)
dr.line([(cx + 10, 10), (cx + 18, 3), (cx + 30, 0), (cx + 40, 4), (cx + 44, 12)], fill=horn, width=5)
for i in range(0, 60, 4):  # ridges on horns
    dr.point([(cx - 14 - i // 2, 4 + (i % 3)), (cx + 14 + i // 2, 4 + (i % 3))], fill=horn_dark)

bone_c = (214, 204, 180)
dr.ellipse([cx - 18, 6, cx + 18, 36], fill=bone_c)  # cranium
dr.polygon([(cx - 13, 28), (cx + 13, 28), (cx + 8, 58), (cx - 8, 58)], fill=bone_c)  # long snout
dr.polygon([(cx - 24, 16), (cx - 17, 14), (cx - 17, 20)], fill=bone_c)  # ears
dr.polygon([(cx + 24, 16), (cx + 17, 14), (cx + 17, 20)], fill=bone_c)

for ex in (-9, 9):  # eye sockets
    dr.ellipse([cx + ex - 6, 15, cx + ex + 6, 27], fill=(6, 0, 0))
    dr.rectangle([cx + ex - 1, 19, cx + ex + 1, 22], fill=(255, 25, 10))
    dr.point([(cx + ex, 20)], fill=(255, 220, 180))
dr.polygon([(cx - 4, 34), (cx + 4, 34), (cx, 41)], fill=(6, 0, 0))  # nasal hole
dr.ellipse([cx - 8, 44, cx + 8, 62], fill=(8, 0, 0))  # screaming mouth
for i, tx in enumerate(range(cx - 6, cx + 7, 3)):  # teeth
    dr.polygon([(tx - 1, 45), (tx + 1, 45), (tx, 49 + i % 2)], fill=(238, 230, 205))
    dr.polygon([(tx - 1, 61), (tx + 1, 61), (tx, 57 - i % 2)], fill=(238, 230, 205))

for _ in range(40):  # cracks & grime
    x, y = cx + int(rng.integers(-16, 17)), int(rng.integers(8, 56))
    if px[x, y] == bone_c:
        px[x, y] = (110, 100, 88)
for x0 in (cx - 9, cx + 9, cx - 3, cx + 5):  # blood dripping from eyes and mouth
    start = 27 if abs(x0 - cx) > 5 else 60
    for y in range(start, min(AH, start + int(rng.integers(5, 14)))):
        px[x0, y] = (150, 0, 0)

scale = 8
face = art.resize((AW * scale, AH * scale), Image.NEAREST)
face.save(os.path.join(RP, "textures/ui/goatman_jumpscare.png"))

icon = art.crop((cx - 32, 0, cx + 32, 64)).resize((256, 256), Image.NEAREST)
icon.save(os.path.join(RP, "pack_icon.png"))
icon.save(os.path.join(BP, "pack_icon.png"))

# ---------------------------------------------------------------- scream sound
SR = 44100
DUR = 2.4
t = np.arange(int(SR * DUR)) / SR


def saw(freq):
    phase = np.cumsum(freq) / SR
    return 2.0 * (phase % 1.0) - 1.0


def make_channel(detune):
    f0 = 1150 - 420 * (t / DUR) ** 0.7 + 45 * np.sin(2 * np.pi * 7.5 * t)
    scream = sum(saw(f0 * k * detune) for k in (1.0, 1.012, 0.991, 1.414))
    scream *= 0.62 + 0.38 * np.sin(2 * np.pi * 17 * t)  # goat-like bleat warble
    growl = saw(np.full_like(t, 68) * detune) * (0.6 + 0.4 * rng.random(len(t)))
    hiss = rng.uniform(-1, 1, len(t)) * 0.35

    env = np.clip(t / 0.01, 0, 1) * np.clip((DUR - t) / 0.7, 0, 1)
    impact = rng.uniform(-1, 1, len(t)) * np.exp(-t * 25) * 3.0
    thump = np.sin(2 * np.pi * 50 * t) * np.exp(-t * 8) * 2.0

    sig = (scream * 0.5 + growl * 0.45 + hiss) * env + impact + thump
    sig = np.tanh(sig * 2.2)
    return sig / np.max(np.abs(sig)) * 0.95


stereo = np.stack([make_channel(1.0), make_channel(1.006)], axis=1)
pcm = (stereo * 32767).astype("<i2")
wav_path = os.path.join(ROOT, "tools", "jumpscare.wav")
with wave.open(wav_path, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())

ogg_path = os.path.join(RP, "sounds/goatman/jumpscare.ogg")
subprocess.run(
    ["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path, "-c:a", "vorbis", "-strict", "-2", "-q:a", "6", ogg_path],
    check=True,
)
print("Assets generated.")
