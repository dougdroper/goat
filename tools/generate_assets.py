"""Generates the Goatman model, texture, jump-scare image and pack icons.

Run:  tools/.venv/bin/python -I tools/generate_assets.py
(Sounds are made by tools/generate_sounds.py)
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RP = os.path.join(ROOT, "Goatman_RP")
BP = os.path.join(ROOT, "Goatman_BP")
rng = np.random.default_rng(666)

TEX_W, TEX_H = 128, 128

# ======================================================================= model
BONES = {}
CUBES = []  # (size, uv, style)
_uv_cache = {}
_shelf = {"x": 0, "y": 0, "row": 0}


def alloc_uv(size, style):
    """Shelf-pack a box-UV region for this cube shape+style (shared by identical cubes)."""
    key = (tuple(size), style)
    if key in _uv_cache:
        return _uv_cache[key]
    w, h, d = (math.ceil(s) for s in size)
    rw, rh = 2 * (w + d), d + h
    if _shelf["x"] + rw > TEX_W:
        _shelf["x"] = 0
        _shelf["y"] += _shelf["row"]
        _shelf["row"] = 0
    uv = [_shelf["x"], _shelf["y"]]
    _shelf["x"] += rw
    _shelf["row"] = max(_shelf["row"], rh)
    assert _shelf["y"] + rh <= TEX_H, "texture atlas full"
    _uv_cache[key] = uv
    CUBES.append((size, uv, style))
    return uv


def bone(name, parent, pivot, rotation=None):
    b = {"name": name, "pivot": pivot, "cubes": []}
    if parent:
        b["parent"] = parent
    if rotation:
        b["rotation"] = rotation
    BONES[name] = b


def cube(bone_name, origin, size, style):
    BONES[bone_name]["cubes"].append({"origin": origin, "size": size, "uv": alloc_uv(size, style)})


def mx(origin, size):
    """Mirror a cube origin across x=0."""
    return [-(origin[0] + size[0]), origin[1], origin[2]]


bone("root", None, [0, 0, 0])

# --- goat legs: thigh forward, shin back, hoof (digitigrade)
for side, s in (("left", 1), ("right", -1)):
    T, S, H = f"{side}Thigh", f"{side}Shin", f"{side}Hoof"
    bone(T, "root", [2.5 * s, 22, 0], [-20, 0, 0])
    bone(S, T, [2.5 * s, 12, 0], [45, 0, 0])
    bone(H, S, [2.5 * s, 4, 0], [-25, 0, 0])
    for b, o, sz, st in (
        (T, [0.75, 12, -1.75], [3.5, 10, 3.5], "fur"),
        (S, [1.25, 4, -1.25], [2.5, 8, 2.5], "limb"),
        (H, [1.25, 1.5, -1.25], [2.5, 2.5, 2.5], "limb"),
        (H, [1, 0, -1.75], [3, 1.5, 3.5], "hoof"),
    ):
        cube(b, o if s > 0 else mx(o, sz), sz, st)

# --- body, hunched forward
bone("body", "root", [0, 22, 0])
cube("body", [-4, 19, -2.5], [8, 6, 5], "fur")
cube("body", [-2.5, 25, -2], [5, 4, 4], "skin")
bone("chest", "body", [0, 29, 0], [15, 0, 0])
cube("chest", [-5, 29, -2.5], [10, 10, 5], "chest")
for y in (30, 33, 36):  # spine bumps
    cube("chest", [-0.5, y, 2.5], [1, 1.5, 1.5], "horn")

# --- long arms with elbows and claws
for side, s in (("left", 1), ("right", -1)):
    A, F = f"{side}Arm", f"{side}Forearm"
    bone(A, "chest", [6.5 * s, 38, 0])
    bone(F, A, [6.5 * s, 25, 0])
    for b, o, sz, st in (
        (A, [5, 25, -1.5], [3, 14, 3], "limb"),
        (F, [5.25, 12, -1.25], [2.5, 13, 2.5], "limb"),
        (F, [5, 6, -1.5], [1, 6, 1], "claw"),
        (F, [6, 5, -1.5], [1, 7, 1], "claw"),
        (F, [7, 6, -1.5], [1, 6, 1], "claw"),
    ):
        cube(b, o if s > 0 else mx(o, sz), sz, st)

# --- neck & head (head sits on a crooked "tilt" bone so it always looks demented)
bone("neck", "chest", [0, 39, 0], [20, 0, 0])
cube("neck", [-1.5, 38, -1.5], [3, 5, 3], "skin")
bone("head", "neck", [0, 43, 0])
bone("tilt", "head", [0, 43, 0], [-30, 0, 24])
cube("tilt", [-3.5, 43, -3.5], [7, 7, 7], "skull")
cube("tilt", [-4, 49, -4.5], [8, 1, 1.5], "skull")  # heavy brow
cube("tilt", [-2.5, 43.5, -8], [5, 4.5, 4.5], "snout")  # long, pointed snout
cube("tilt", [-2, 44, -11.5], [4, 3.5, 3.5], "snout")
cube("tilt", [-1.25, 44.5, -14], [2.5, 2.5, 2.5], "snout")
cube("tilt", [1.25, 48, -3.75], [1.75, 1, 0.5], "eye")  # mismatched glowing eyes
cube("tilt", [-2.75, 47.75, -3.75], [1.5, 1.5, 0.5], "eye")
cube("tilt", [3.5, 46, -1], [3.5, 1, 2], "skin")  # floppy ears
cube("tilt", [-7, 45.5, -1], [3.5, 1, 2], "skin")

UPPER = [  # (half-width at that z, bottom y, z positions) for each snout segment
    (2.5, 43.5, (-7.5, -6.5, -5.5, -4.5)),
    (2.0, 44.0, (-11.0, -10.0, -9.0)),
    (1.25, 44.5, (-13.5, -12.5)),
]
for hw, bottom, zs in UPPER:  # rows of upper teeth
    for z in zs:
        for s in (1, -1):
            cube("tilt", [s * (hw - 0.3) - 0.25, bottom - 1.5, z], [0.5, 1.5, 0.5], "tooth")
for x in (-0.6, 0.1):  # front fangs
    cube("tilt", [x, 42.3, -13.9], [0.5, 2.2, 0.5], "tooth")

bone("jaw", "tilt", [0, 43.5, -3], [25, 0, 0])  # hangs open
cube("jaw", [-2.25, 42, -8], [4.5, 1.5, 5], "jaw")
cube("jaw", [-1.75, 42.25, -11.5], [3.5, 1.25, 3.5], "jaw")
cube("jaw", [-1, 42.5, -13.5], [2, 1, 2], "jaw")
cube("jaw", [-1, 39, -7], [2, 3, 1.5], "fur")  # goat beard
LOWER = [(2.25, 43.5, (-7.0, -6.0, -5.0, -4.0)), (1.75, 43.5, (-11.0, -10.0, -9.0)), (1.0, 43.5, (-13.0,))]
for hw, top, zs in LOWER:  # rows of lower teeth
    for z in zs:
        for s in (1, -1):
            cube("jaw", [s * (hw - 0.3) - 0.25, top, z], [0.5, 1.2, 0.5], "tooth")

for side, s in (("L", 1), ("R", -1)):  # big curling horns
    bone(f"horn{side}1", "tilt", [2.5 * s, 50, 0], [-25, 0, -25 * s])
    bone(f"horn{side}2", f"horn{side}1", [2.5 * s, 55, 0], [-35, 0, -15 * s])
    bone(f"horn{side}3", f"horn{side}2", [2.5 * s, 60, 0], [-40, 0, 0])
    for b, o, sz in (
        (f"horn{side}1", [1.5, 50, -1], [2, 5, 2]),
        (f"horn{side}2", [1.75, 55, -0.75], [1.5, 5, 1.5]),
        (f"horn{side}3", [2, 60, -0.5], [1, 4, 1]),
    ):
        cube(b, o if s > 0 else mx(o, sz), sz, "horn")

geo = {
    "format_version": "1.12.0",
    "minecraft:geometry": [
        {
            "description": {
                "identifier": "geometry.goatman",
                "texture_width": TEX_W,
                "texture_height": TEX_H,
                "visible_bounds_width": 4,
                "visible_bounds_height": 5,
                "visible_bounds_offset": [0, 2, 0],
            },
            "bones": list(BONES.values()),
        }
    ],
}
with open(os.path.join(RP, "models/entity/goatman.geo.json"), "w") as f:
    json.dump(geo, f, indent=2)

# ===================================================================== texture
tex = np.zeros((TEX_H, TEX_W, 4), dtype=np.uint8)
PALETTE = {
    "skin": (58, 44, 38),
    "limb": (50, 39, 33),
    "fur": (40, 29, 21),
    "chest": (58, 44, 38),
    "skull": (212, 202, 178),
    "snout": (205, 194, 170),
    "jaw": (185, 172, 148),
    "tooth": (226, 214, 170),
    "eye": (255, 30, 15),
    "horn": (70, 62, 55),
    "claw": (28, 24, 22),
    "hoof": (18, 16, 15),
}
MOUTH = (95, 12, 12)


def put(x, y, color, alpha=255):
    if 0 <= x < TEX_W and 0 <= y < TEX_H:
        tex[y, x] = (*color, alpha)


def shade(color, amount):
    return tuple(int(max(0, min(255, c + amount))) for c in color)


def faces(size, uv):
    w, h, d = (max(1, math.ceil(s)) for s in size)
    u, v = uv
    return {
        "top": (u + d, v, w, d),
        "bottom": (u + d + w, v, w, d),
        "right": (u, v + d, d, h),
        "front": (u + d, v + d, w, h),
        "left": (u + d + w, v + d, d, h),
        "back": (u + 2 * d + w, v + d, w, h),
    }


for size, uv, style in CUBES:
    base = PALETTE[style]
    for name, (fx, fy, fw, fh) in faces(size, uv).items():
        for yy in range(fh):
            for xx in range(fw):
                c = shade(base, rng.integers(-10, 11))
                alpha = 255
                if style == "fur" and (xx + rng.integers(0, 2)) % 2 == 0:
                    c = shade(c, -12)
                if style == "limb" and yy % 7 == 0:
                    c = shade(c, -14)  # knobbly joints
                if style == "horn" and yy % 2 == 0:
                    c = shade(c, -20)  # ridges
                if style in ("skull", "snout", "jaw") and rng.random() < 0.07:
                    c = shade(c, -60)  # cracks
                if style == "chest" and name in ("front", "back") and yy % 2 == 1 and 0 < xx < fw - 1:
                    c = shade(base, 30)  # ribs showing through
                if style == "snout" and name == "bottom":
                    c = shade(MOUTH, rng.integers(-15, 15))  # roof of mouth
                if style == "jaw" and name == "top":
                    c = shade(MOUTH, rng.integers(-15, 15))
                if style == "claw" and yy == fh - 1:
                    c = (120, 10, 10)  # bloody tips
                if style == "tooth" and yy == fh - 1:
                    c = (150, 120, 90)
                if style == "eye":
                    alpha = 0  # transparent pixels glow with entity_emissive_alpha
                    if xx == 0 and yy == 0:
                        c = (255, 220, 160)
                put(fx + xx, fy + yy, c, alpha)
    if style == "skull":  # dark sockets behind the glowing eyes
        fx, fy, fw, fh = faces(size, uv)["front"]
        if fw == 7:
            for xx in (0, 1, 2, 4, 5, 6):
                put(fx + xx, fy + 1, (10, 4, 4))
                put(fx + xx, fy + 2, (10, 4, 4))

Image.fromarray(tex, "RGBA").save(os.path.join(RP, "textures/entity/goatman.png"))

# ============================================================ jump-scare face
AW, AH = 112, 64
bg = Image.new("RGB", (AW, AH))
px = bg.load()
cx, cy = AW // 2, AH // 2
for y in range(AH):
    for x in range(AW):
        d = math.hypot((x - cx) / AW, (y - cy) / AH)
        px[x, y] = (int(max(0, 95 - d * 170) + rng.integers(0, 12)), 0, 0)

S = 2  # draw the face bigger, then rotate it so the whole head is crooked
M = 12  # headroom so the horns are not clipped when rotated
face = Image.new("RGBA", (AW * S, (AH + 2 * M) * S), (0, 0, 0, 0))
dr = ImageDraw.Draw(face)
c = (cx * S, (cy + M) * S)
bone_c, horn, horn_dark, black = (214, 204, 180, 255), (66, 56, 48, 255), (38, 31, 26, 255), (6, 0, 0, 255)
red, tooth = (255, 25, 10, 255), (232, 222, 190, 255)
X = lambda v: c[0] + v * S
Y = lambda v: (v + M) * S

for s in (-1, 1):  # horns
    dr.line([(X(10 * s), Y(9)), (X(18 * s), Y(4)), (X(31 * s), Y(3)), (X(42 * s), Y(7)), (X(46 * s), Y(16)), (X(41 * s), Y(23))], fill=horn, width=6 * S)
    for i in range(6):
        dr.line([(X((16 + i * 5) * s), Y(2)), (X((17 + i * 5) * s), Y(8))], fill=horn_dark, width=S)
dr.ellipse([X(-17), Y(4), X(17), Y(30)], fill=bone_c)  # cranium
dr.polygon([(X(-13), Y(22)), (X(13), Y(22)), (X(3), Y(66)), (X(-3), Y(66))], fill=bone_c)  # long pointed snout
for s in (-1, 1):
    dr.polygon([(X(24 * s), Y(18)), (X(16 * s), Y(13)), (X(16 * s), Y(21))], fill=bone_c)  # ears
dr.polygon([(X(-17), Y(13)), (X(-3), Y(18)), (X(-4), Y(26)), (X(-15), Y(24))], fill=black)  # slanted sockets
dr.polygon([(X(17), Y(11)), (X(3), Y(18)), (X(5), Y(27)), (X(16), Y(25))], fill=black)
dr.rectangle([X(-11), Y(18), X(-8), Y(21)], fill=red)  # small pupil
dr.rectangle([X(8), Y(17), X(12), Y(22)], fill=red)  # big pupil
dr.point([(X(-10), Y(19)), (X(10), Y(19))], fill=(255, 230, 190, 255))
dr.polygon([(X(-3), Y(28)), (X(3), Y(28)), (X(0), Y(33))], fill=black)  # nose hole
dr.polygon([(X(-9), Y(36)), (X(9), Y(36)), (X(3), Y(64)), (X(-3), Y(64))], fill=(30, 0, 0, 255))  # gaping mouth
for i, yy in enumerate(range(37, 63, 2)):  # rows and rows of teeth
    hw = 9 - (yy - 36) * 6 / 28
    dr.polygon([(X(-hw), Y(yy)), (X(-hw), Y(yy + 2)), (X(-hw + 3.5 + i % 2), Y(yy + 1))], fill=tooth)
    dr.polygon([(X(hw), Y(yy + 1)), (X(hw), Y(yy + 3)), (X(hw - 3.5 - i % 2), Y(yy + 2))], fill=tooth)
for x in range(-7, 8, 2):  # top row of fangs
    dr.polygon([(X(x - 0.8), Y(36)), (X(x + 0.8), Y(36)), (X(x), Y(40 + abs(x) % 3))], fill=tooth)
fpx = face.load()
for _ in range(120):  # cracks
    x, y = int(rng.integers(0, AW * S)), int(rng.integers(0, (AH + 2 * M) * S))
    if fpx[x, y] == bone_c:
        fpx[x, y] = (110, 100, 88, 255)
for x0, y0 in ((-10, 24), (10, 26), (-2, 62), (2, 62)):  # blood
    dr.line([(X(x0), Y(y0)), (X(x0), Y(y0 + int(rng.integers(6, 14))))], fill=(150, 0, 0, 255), width=S)

face = face.rotate(-16, resample=Image.NEAREST, center=c)
face = face.resize((AW, AH + 2 * M), Image.NEAREST)
bg.paste(face, (0, -M + 4), face)

bg.resize((AW * 8, AH * 8), Image.NEAREST).save(os.path.join(RP, "textures/ui/goatman_jumpscare.png"))
icon = bg.crop((cx - 32, 0, cx + 32, 64)).resize((256, 256), Image.NEAREST)
icon.save(os.path.join(RP, "pack_icon.png"))
icon.save(os.path.join(BP, "pack_icon.png"))
print(f"Model: {sum(len(b['cubes']) for b in BONES.values())} cubes, {len(BONES)} bones. Texture/face/icons written.")
