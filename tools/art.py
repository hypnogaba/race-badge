"""Builds art.lua for the badge from pixel-art rows.

Sources:
- art/web_pixel_sprites.json: the pixel art from the first (pixel) version of the web game
  race.speedlab.pro (hero, shark, obstacles, venue coins, landmarks), extracted from its git history.
- this file: new sprites the badge needs (router, firewall, packet loss, small coins, gold 00, fog,
  coin slots, ocean landmarks) and the far skyline of each world.

  .venv/bin/python tools/art.py          -> art.lua
  .venv/bin/python tools/art.py --png    -> also tools/out/sprites.png (contact sheet)
"""
import json, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = json.load(open(os.path.join(ROOT, "art", "web_pixel_sprites.json")))

PAL = dict(SRC["PAL"])
PAL.update({
    "f": 0x8C93B0,  # fog
    "z": 0xFFE08A,  # gold highlight
    "Y": 0xC9962E,  # gold shadow
})

# Each world: sky, earth under the cable, far skyline (F), its lights (L), stars (S), cable glow (c).
WORLDS = [
    {"id": "city", "name": "CITY", "sky": 0x0B1030, "earth": 0x070B1E, "F": 0x1B2550, "L": 0xC9A24A, "S": 0x5A6390},
    {"id": "exchange", "name": "EXCHANGE", "sky": 0x07170F, "earth": 0x040E09, "F": 0x123A2A, "L": 0x14F195, "S": 0x3E6B58},
    {"id": "ocean", "name": "OCEAN", "sky": 0x051A2E, "earth": 0x03101E, "F": 0x0E3050, "L": 0x3FF5E0, "S": 0x4D7598},
    {"id": "singapore", "name": "SINGAPORE", "sky": 0x180D2C, "earth": 0x0E0719, "F": 0x2E1C52, "L": 0xFF8AD8, "S": 0x6A5A90},
    {"id": "london", "name": "LONDON", "sky": 0x10151F, "earth": 0x090C12, "F": 0x222C3C, "L": 0xF2C9A0, "S": 0x5C6678},
]

# Sky tint while a venue bonus is on (last coin taken), and in the DZ tunnel.
THEMES = {"S": 0x23104A, "K": 0x003826, "H": 0x08362F, "P": 0x3A1606, "T": 0x12062A}

sprites = {}   # name -> rows
palettes = {}  # name -> palette overrides (only letters that differ from PAL)


def add(name, rows, pal=None):
    w = len(rows[0])
    for i, r in enumerate(rows):
        if len(r) != w:
            raise SystemExit(f"{name}: row {i} is {len(r)} wide, want {w}")
    sprites[name] = rows
    if pal:
        palettes[name] = pal


class Grid:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.c = [["."] * w for _ in range(h)]

    def fill(self, x, y, w, h, ch):
        for yy in range(max(0, y), min(self.h, y + h)):
            for xx in range(max(0, x), min(self.w, x + w)):
                self.c[yy][xx] = ch
        return self

    def dot(self, x, y, ch):
        return self.fill(x, y, 1, 1, ch)

    def rows(self):
        return ["".join(r) for r in self.c]


# ------------------------------------------------------------------ sprites from the web game
def frames(group, name):
    return SRC[group][name]["frames"]


for name in ("traderRun", "traderJump", "shark", "hypurr", "multicast", "grass", "shield"):
    for i, f in enumerate(frames("ACTORS", name)):
        add(f"{name}{i + 1}", f)

for name in ("lag", "jam", "candle", "bot", "anchor", "jelly", "bite", "merlion", "gap"):
    for i, f in enumerate(frames("OBSTACLES", name)):
        add(f"{name}{i + 1}", f)

for k, c in SRC["COINS"].items():
    add(f"coin{k}", c["frames"][0], c["pal"])
    # empty slot in the HUD: the same round shape, dark
    slot = ["".join("." if ch == "." else ("g" if ch == "R" else "n") for ch in r) for r in c["frames"][0]]
    add(f"slot{k}", slot)
bp = SRC["BROKEN_PIXEL"]
add("brokenPixel1", bp["frames"][0], bp["pal"])

for name in ("bigBen", "bus", "mbs", "merlionStatue", "candles", "skyline"):
    add(name, SRC["LANDMARKS"][name]["frames"][0])

# ------------------------------------------------------------------ new obstacles (face left, bottom = cable)
add("router1", [
    "...c...c...",
    "...g...g...",
    "...g...g...",
    "kgggggggggk",
    "gnnnnnnnnng",
    "gnGnrnnnwng",
    "gnnnnnnnnng",
    "kgggggggggk",
    ".k.......k.",
])
add("router2", [
    "...w...c...",
    "...g...g...",
    "...g...g...",
    "kgggggggggk",
    "gnnnnnnnnng",
    "gnGnnnrnwng",
    "gnnnnnnnnng",
    "kgggggggggk",
    ".k.......k.",
])
FIRE_A = ["...y.....", "..yo..y..", ".yoo.yoy.", ".oro.oro.", "orrrorrro", "rrrrrrrrr"]
FIRE_B = [".....y...", "..y..oy..", ".yoy.ooy.", ".oro.oro.", "orrrorrro", "rrrrrrrrr"]
WALL = ["kkkkkkkkk", "oookoooko", "kkkkkkkkk", "okooookoo", "kkkkkkkkk", "oookoooko", "kkkkkkkkk", "okooookoo", "kkkkkkkkk"]
add("firewall1", FIRE_A + WALL)
add("firewall2", FIRE_B + WALL)
add("packetloss1", [
    "..cc......c...",
    "..cc.....cc...",
    "......cc......",
    "cc....cc...cc.",
    "cc..r......cc.",
    "....cc..r.....",
    "....cc....cc..",
])
add("packetloss2", [
    "...cc.....c...",
    "...cc....cc...",
    ".......cc.....",
    ".cc....cc..cc.",
    ".cc..r.....cc.",
    "....cc...r....",
    "....cc....cc..",
])

# ------------------------------------------------------------------ small coins, gold 00
add("bit1", [".zyy.", "zzyyy", "zyyyY", "yyyYY", ".YYY."])
add("bit2", ["..zy.", ".zyy.", ".zyY.", ".yyY.", "..YY."])
add("bit3", ["..y..", "..z..", "..y..", "..Y..", "..Y.."])
add("zero1", [
    ".zzzz..zzzz.",
    "zyyyyYzyyyyY",
    "zy..yYzy..yY",
    "zy..yYzy..yY",
    "zy..yYzy..yY",
    "zy..yYzy..yY",
    "zy..yYzy..yY",
    "zyyyyYzyyyyY",
    ".YYYY..YYYY.",
])

# ------------------------------------------------------------------ fog: a checker that lets threats show through
FOG_W, FOG_H = 40, 77
fog = []
frnd = random.Random(5)
for y in range(FOG_H):
    row = ""
    for x in range(FOG_W):
        # denser towards the right edge; a checker so threats still show through
        dens = 0.1 + 0.9 * (x / (FOG_W - 1)) ** 0.8
        on = (x + y) % 2 == 0 and frnd.random() < dens
        row += "f" if on else "."
    fog.append(row)
add("fog", fog)

# ------------------------------------------------------------------ ocean landmarks
g = Grid(10, 44)
g.fill(3, 8, 4, 36, "e").fill(2, 40, 6, 4, "g")
for y in range(12, 40, 6):
    g.fill(3, y, 4, 2, "r")
g.fill(2, 4, 6, 4, "g").fill(3, 5, 4, 2, "y").fill(4, 2, 2, 2, "g").fill(1, 8, 8, 1, "g")
add("lighthouse", g.rows())
g = Grid(34, 12)
g.fill(2, 7, 30, 4, "b").fill(4, 11, 26, 1, "n").fill(0, 6, 34, 1, "g")
for x, c in ((6, "r"), (10, "o"), (14, "y"), (18, "c"), (22, "r")):
    g.fill(x, 3, 4, 3, c)
g.fill(26, 1, 4, 5, "w").fill(27, 2, 2, 1, "c")
add("ship", g.rows())

# ------------------------------------------------------------------ far skylines (160 x 56, colours F L S of the world)
SKY_W, SKY_H = 160, 56


def stars(g, rnd, n):
    for _ in range(n):
        x, y = rnd.randrange(SKY_W), rnd.randrange(0, 24)
        if g.c[y][x] == ".":
            g.dot(x, y, "S")


def windows(g, x0, top, w, rnd, p=0.28):
    for y in range(top + 2, SKY_H - 2, 3):
        for x in range(x0 + 1, x0 + w - 1, 2):
            if rnd.random() < p:
                g.dot(x, y, "L")


def city(rnd):
    g = Grid(SKY_W, SKY_H)
    stars(g, rnd, 26)
    x = 0
    while x < SKY_W:
        w, h = rnd.randint(8, 18), rnd.randint(14, 44)
        g.fill(x, SKY_H - h, w, h, "F")
        if rnd.random() < 0.3:
            g.fill(x + w // 2, SKY_H - h - 5, 1, 5, "F")
        windows(g, x, SKY_H - h, w, rnd)
        x += w + rnd.randint(0, 2)
    return g


def exchange(rnd):
    g = Grid(SKY_W, SKY_H)
    stars(g, rnd, 14)
    level = 34
    for x in range(2, SKY_W - 3, 5):
        step = rnd.randint(-5, 6)
        top, bot = min(level, level - step), max(level, level - step)
        bot = max(bot, top + 2)
        g.fill(x + 1, top - rnd.randint(1, 4), 1, bot - top + rnd.randint(3, 7), "F")
        g.fill(x, top, 3, bot - top, "L" if step > 0 else "F")
        level = max(10, min(46, level - step))
    for x in range(0, SKY_W):
        g.dot(x, SKY_H - 1, "F")
    return g


def ocean(rnd):
    g = Grid(SKY_W, SKY_H)
    stars(g, rnd, 30)
    horizon = 40
    g.fill(0, horizon, SKY_W, SKY_H - horizon, "F")
    for y in range(horizon + 2, SKY_H, 3):
        for x in range(rnd.randrange(4), SKY_W, rnd.randint(6, 11)):
            g.fill(x, y, rnd.randint(2, 4), 1, "S")
    for x in range(70, 90):
        if rnd.random() < 0.5:
            g.dot(x, horizon + rnd.randint(1, 12), "L")
    return g


def singapore(rnd):
    g = Grid(SKY_W, SKY_H)
    stars(g, rnd, 18)
    x = 0
    while x < SKY_W:
        w, h = rnd.randint(6, 14), rnd.randint(16, 48)
        g.fill(x, SKY_H - h, w, h, "F")
        windows(g, x, SKY_H - h, w, rnd, 0.22)
        x += w + rnd.randint(1, 4)
    for tx in (20, 34, 120, 138):  # supertrees: trunk + glowing crown
        th = rnd.randint(18, 26)
        g.fill(tx, SKY_H - th, 2, th, "F")
        for i in range(7):
            g.dot(tx - 3 + i, SKY_H - th - (1 if i in (0, 6) else 2), "L")
    return g


def london(rnd):
    g = Grid(SKY_W, SKY_H)
    stars(g, rnd, 12)
    x = 0
    while x < SKY_W:
        w, h = rnd.randint(10, 20), rnd.randint(10, 26)
        g.fill(x, SKY_H - h, w, h, "F")
        windows(g, x, SKY_H - h, w, rnd, 0.18)
        x += w
    # the Shard
    for y in range(0, 50):
        half = max(0, y // 5)
        g.fill(118 - half, SKY_H - 50 + y, half * 2 + 1, 1, "F")
    # a dome
    for y in range(8):
        half = int((64 - (8 - y) ** 2) ** 0.5)
        g.fill(60 - half, SKY_H - 32 + y, half * 2, 1, "F")
    g.fill(52, SKY_H - 24, 16, 24, "F").fill(59, SKY_H - 38, 2, 6, "F")
    # the Eye
    cx, cy, r = 24, SKY_H - 22, 16
    for a in range(0, 360, 6):
        import math
        g.dot(int(cx + r * math.cos(math.radians(a))), int(cy + r * math.sin(math.radians(a))), "L")
    return g


for wi, fn in enumerate((city, exchange, ocean, singapore, london)):
    w = WORLDS[wi]
    add(f"far{wi + 1}", fn(random.Random(wi * 31 + 7)).rows(), {"F": w["F"], "L": w["L"], "S": w["S"]})


# ------------------------------------------------------------------ output
def lua_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_lua(path):
    out = ["-- RACE TO ZERO art. Generated by tools/art.py: edit that file, not this one.", "local A = {}"]
    out.append("A.pal = {" + ", ".join(f"{k}=0x{v:06X}" for k, v in PAL.items()) + "}")
    out.append("A.worlds = {")
    for w in WORLDS:
        out.append("  {" + ", ".join(
            f"{k}={lua_str(v)}" if isinstance(v, str) else f"{k}=0x{v:06X}" for k, v in w.items()) + "},")
    out.append("}")
    out.append("A.themes = {" + ", ".join(f"{k}=0x{v:06X}" for k, v in THEMES.items()) + "}")
    out.append("A.s = {")
    for name in sorted(sprites):
        out.append(f"  {name} = {{" + ",".join(lua_str(r) for r in sprites[name]) + "},")
    out.append("}")
    out.append("A.p = {")
    for name in sorted(palettes):
        out.append(f"  {name} = {{" + ", ".join(f"{k}=0x{v:06X}" for k, v in palettes[name].items()) + "},")
    out.append("}")
    out.append("return A")
    open(path, "w").write("\n".join(out) + "\n")


def contact_sheet(path):
    from PIL import Image
    names = sorted(sprites)
    S = 3
    pad = 6
    x = y = pad
    rowh = 0
    W = 1100
    placed = []
    for n in names:
        rows = sprites[n]
        w, h = len(rows[0]) * S, len(rows) * S
        if x + w > W:
            x, y, rowh = pad, y + rowh + pad, 0
        placed.append((n, x, y))
        x += w + pad
        rowh = max(rowh, h)
    im = Image.new("RGB", (W, y + rowh + pad), (12, 14, 30))
    for n, x0, y0 in placed:
        pal = dict(PAL)
        pal.update(palettes.get(n, {}))
        for yy, r in enumerate(sprites[n]):
            for xx, ch in enumerate(r):
                if ch != ".":
                    c = pal[ch]
                    for dy in range(S):
                        for dx in range(S):
                            im.putpixel((x0 + xx * S + dx, y0 + yy * S + dy), ((c >> 16) & 255, (c >> 8) & 255, c & 255))
    im.save(path)


if __name__ == "__main__":
    for n, rows in sprites.items():
        pal = dict(PAL)
        pal.update(palettes.get(n, {}))
        for r in rows:
            for ch in r:
                if ch != "." and ch not in pal:
                    raise SystemExit(f"{n}: colour {ch!r} not in palette")
    write_lua(os.path.join(ROOT, "art.lua"))
    print("art.lua:", os.path.getsize(os.path.join(ROOT, "art.lua")), "bytes,", len(sprites), "sprites")
    if "--png" in sys.argv:
        os.makedirs(os.path.join(ROOT, "tools", "out"), exist_ok=True)
        contact_sheet(os.path.join(ROOT, "tools", "out", "sprites.png"))
