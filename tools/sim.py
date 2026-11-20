"""Headless FORK BOMB runner: a mock of the badge's Lua API (Python side), a bot that
plays, an instruction counter per callback, and PNG screenshots of the emulated screen.

  .venv/bin/python tools/sim.py [--seconds 120] [--seed 1] [--stage 1] [--shots out]
"""
import argparse, os, random, sys
from lupa import lua55
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 320, 218

THEME = {
    "text": 0xFFFFFF, "dim": 0x8A86A0, "bg": 0x000000, "panel": 0x1A1A24, "border": 0x333344,
    "purple": 0x9945FF, "green": 0x14F195, "pink": 0xFF6FB5, "lpurple": 0xC8A8FF, "blue": 0x3D5AFE,
    "aqua": 0x3FD8E8, "lime": 0x8BE04E, "yellow": 0xFFD84A, "orange": 0xFF8A3D,
}
BRAND = {"k": 0x000000, "w": 0xFFFFFF, "p": 0x9945FF, "g": 0x14F195, "m": 0xFF6FB5, "v": 0xC8A8FF,
         "b": 0x3D5AFE, "a": 0x3FD8E8, "l": 0x8BE04E, "y": 0xFFD84A, "o": 0xFF8A3D, "#": 0xFFFFFF}


def col(c):
    if isinstance(c, str):
        return THEME[c]
    return int(c)


class Mock:
    def __init__(self, lua, rng):
        self.lua = lua
        self.rng = rng
        self.images = {}
        self.objs = {}
        self.order = []
        self.next = 1
        self.bg = 0
        self.keys = set()
        self.millis = 0
        self.storage = {}
        self.toasts = []
        self.hint = ""
        self.leds = [0] * 8
        self.errors = []
        self.awards = []
        self.http = []

    # images
    def load(self, rows, pal):
        rows = [rows[i] for i in range(1, len(rows) + 1)]
        p = dict(BRAND)
        if pal is not None:
            for k in pal.keys():
                v = pal[k]
                p[k] = None if v is False else col(v)
        h = len(rows)
        w = max(len(r) for r in rows)
        px = []
        for r in rows:
            for x in range(w):
                ch = r[x] if x < len(r) else "."
                if ch in (".", " "):
                    px.append(None)
                else:
                    if ch not in p:
                        raise RuntimeError(f"pixel art: character {ch!r} not in palette")
                    px.append(p[ch])
        iid = self.next
        self.next += 1
        self.images[iid] = (w, h, px)
        return iid

    def img_size(self, iid):
        w, h, _ = self.images[iid]
        return w, h

    # objects
    def new(self, kind, x, y, a=None, b=None, c=None):
        oid = self.next
        self.next += 1
        o = {"kind": kind, "x": int(x), "y": int(y), "show": True}
        if kind == "label":
            o.update(text=str(a), size=int(b["size"] or 14) if b else 14,
                     color=col(b["color"]) if b and b["color"] is not None else THEME["text"],
                     w=int(b["w"]) if b and b["w"] is not None else None,
                     align=(b["align"] if b and b["align"] else "left"))
        elif kind == "rect":
            o.update(w=int(a), h=int(b), color=col(c["color"]) if c and c["color"] is not None else THEME["panel"])
        elif kind == "gradient":
            o.update(w=int(a), h=int(b))
        elif kind == "image":
            o.update(img=int(a), scale=int(b["scale"]) if b and b["scale"] else 1)
        elif kind == "canvas":
            w, h, opts = int(a), int(b), c
            bgc = col(opts["color"]) if opts and opts["color"] is not None else None
            scale = int(opts["scale"]) if opts and opts["scale"] else 1
            o.update(w=w, h=h, scale=scale, px=[bgc] * (w * h))
        self.objs[oid] = o
        self.order.append(oid)
        live = sum(1 for k in self.order if k in self.objs)
        if live > 128:
            raise RuntimeError("more than 128 UI objects")
        return oid

    def call(self, oid, method, a=None, b=None, c=None, d=None, e=None):
        o = self.objs.get(oid)
        if o is None:
            return None
        if method == "pos":
            o["x"], o["y"] = int(a), int(b)
        elif method == "show":
            o["show"] = bool(a)
        elif method == "remove":
            del self.objs[oid]
        elif method == "text":
            o["text"] = str(a)
        elif method == "color":
            o["color"] = col(a)
        elif method == "set":
            o["img"] = int(a)
        elif method == "scale":
            o["scale"] = int(a)
        elif method == "size":
            o["w"], o["h"] = int(a), int(b)
        elif method == "image":  # canvas stamp
            self.stamp(o, int(a), int(b), int(c))
        elif method == "rect":
            for y in range(int(b), int(b) + int(d)):
                for x in range(int(a), int(a) + int(c)):
                    if 0 <= x < o["w"] and 0 <= y < o["h"]:
                        o["px"][y * o["w"] + x] = col(e)
        elif method == "pixel":
            x, y = int(a), int(b)
            if 0 <= x < o["w"] and 0 <= y < o["h"]:
                o["px"][y * o["w"] + x] = col(c)
        elif method == "clear":
            o["px"] = [None if a is None else col(a)] * (o["w"] * o["h"])
        return None

    def stamp(self, o, iid, x0, y0):
        w, h, px = self.images[iid]
        cw, ch = o["w"], o["h"]
        for y in range(h):
            yy = y0 + y
            if yy < 0 or yy >= ch:
                continue
            for x in range(w):
                c = px[y * w + x]
                if c is None:
                    continue
                xx = x0 + x
                if 0 <= xx < cw:
                    o["px"][yy * cw + xx] = c

    def clear(self):
        self.objs.clear()
        self.order = []

    # render
    def render(self, path):
        im = Image.new("RGB", (W, H), rgb(self.bg))
        dr = ImageDraw.Draw(im)
        try:
            fonts = {s: ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", s - 2) for s in (12, 14, 20, 32)}
        except Exception:
            fonts = {s: ImageFont.load_default() for s in (12, 14, 20, 32)}
        for oid in self.order:
            o = self.objs.get(oid)
            if not o or not o["show"]:
                continue
            k = o["kind"]
            if k == "rect":
                dr.rectangle([o["x"], o["y"], o["x"] + o["w"] - 1, o["y"] + o["h"] - 1], fill=rgb(o["color"]))
            elif k == "gradient":
                for i in range(o["w"]):
                    t = i / max(1, o["w"] - 1)
                    c = tuple(int(a + (b - a) * t) for a, b in zip((0x99, 0x45, 0xFF), (0x14, 0xF1, 0x95)))
                    dr.line([o["x"] + i, o["y"], o["x"] + i, o["y"] + o["h"] - 1], fill=c)
            elif k in ("image", "canvas"):
                if k == "image":
                    w, h, px = self.images[o["img"]]
                else:
                    w, h, px = o["w"], o["h"], o["px"]
                s = o["scale"]
                for y in range(h):
                    for x in range(w):
                        c = px[y * w + x]
                        if c is None:
                            continue
                        dr.rectangle([o["x"] + x * s, o["y"] + y * s, o["x"] + x * s + s - 1, o["y"] + y * s + s - 1], fill=rgb(c))
            elif k == "label":
                f = fonts[o["size"]]
                x = o["x"]
                if o["w"] and o["align"] != "left":
                    tw = dr.textlength(o["text"], font=f)
                    x = o["x"] + (o["w"] - tw) / 2 if o["align"] == "center" else o["x"] + o["w"] - tw
                dr.text((x, o["y"]), o["text"], fill=rgb(o["color"]), font=f)
        if self.hint:
            dr.rectangle([0, H - 16, W, H], fill=(20, 20, 30))
            dr.text((4, H - 15), self.hint, fill=(150, 150, 170), font=fonts[12])
        # LEDs strip along the top edge of the picture
        big = Image.new("RGB", (W, H + 10), (0, 0, 0))
        big.paste(im, (0, 10))
        d2 = ImageDraw.Draw(big)
        for i, c in enumerate(self.leds):
            d2.rectangle([8 + i * 38, 2, 30 + i * 38, 7], fill=rgb(c))
        big.save(path)


def rgb(c):
    c = int(c or 0)
    return ((c >> 16) & 255, (c >> 8) & 255, c & 255)


MOCK_LUA = r"""
local PY = ...
local function obj(id)
  return setmetatable({_id = id}, {__index = function(t, k)
    return function(self, ...) return PY.call(id, k, ...) end
  end})
end
local function src(s, opts)
  if type(s) == "table" and s._img then return s._img end
  if type(s) == "table" then return PY.load(s, opts and opts.palette) end
  error("mock: image paths are not supported")
end
ui = {W = 320, H = 218}
function ui.bg(c) PY.bg(c) end
function ui.label(x, y, t, o) return obj(PY.new("label", x, y, t, o or {})) end
function ui.rect(x, y, w, h, o) return obj(PY.new("rect", x, y, w, h, o or {})) end
function ui.gradient(x, y, w, h) return obj(PY.new("gradient", x, y, w, h)) end
function ui.load(s, opts)
  local id = src(s, opts)
  return {_img = id, size = function() return PY.size(id) end}
end
function ui.image(x, y, s, o)
  local id = src(s, o)
  local im = obj(PY.new("image", x, y, id, o or {}))
  local raw_set = im.set
  return setmetatable({_id = im._id}, {__index = function(t, k)
    if k == "set" then return function(self, s2, o2) return PY.call(im._id, "set", src(s2, o2)) end end
    return function(self, ...) return PY.call(im._id, k, ...) end
  end})
end
function ui.canvas(x, y, w, h, o)
  local c = obj(PY.new("canvas", x, y, w, h, o or {}))
  return setmetatable({_id = c._id}, {__index = function(t, k)
    if k == "image" then return function(self, s, x2, y2) return PY.call(c._id, "image", src(s), x2, y2) end end
    return function(self, ...) return PY.call(c._id, k, ...) end
  end})
end
function ui.hint(t) PY.hint(t) end
function ui.toast(t) PY.toast(t) end
function ui.clear() PY.clear() end
function ui.confirm(t, cb) cb(true) end
led = {count = 8}
function led.hex(i, c) PY.led(i, c) end
function led.set(i, r, g, b) PY.led(i, r * 65536 + g * 256 + b) end
function led.fill(r, g, b) for i = 1, 8 do led.set(i, r, g, b) end end
function led.off() for i = 1, 8 do PY.led(i, 0) end end
sys = {}
function sys.millis() return PY.millis() end
function sys.keys() return PY.keys() end
function sys.memory() return {used = math.floor(collectgarbage("count") * 1024), max = 6291456} end
function sys.exit() end
function sys.time() return PY.now() end
badge = {}
function badge.owner() return "@val" end
function badge.id() return "7K2Q9M" end
http = {}
function http.get(url, a, b) local cb = b or a local ok, r = PY.http("GET", url, "") cb(ok, r) end
function http.post(url, body, a, b) local cb = b or a local ok, r = PY.http("POST", url, json.encode(body)) cb(ok, r) end
json = {}
function json.encode(v) return PY.jenc(v) end
function json.decode(t) return PY.jdec(t) end
lamps = {}
function lamps.award(n, reason, cb) local ok, r = PY.award(n, reason) cb(ok, r) end
storage = {}
function storage.get(k) return PY.sget(k) end
function storage.set(k, v) PY.sset(k, v) end
function storage.remove(k) PY.sset(k, nil) end
"""


class Runner:
    def __init__(self, seed, stage=1, award=None, now=None, expose=None):
        """award(n, reason) -> (ok, dict) fakes the !LAMP server; now() -> unix seconds;
        expose: Lua code appended to main.lua (the chunk's locals are in scope there)."""
        self.rng = random.Random(seed)
        self.lua = lua55.LuaRuntime(unpack_returned_tuples=True)
        self.m = Mock(self.lua, self.rng)
        m = self.m
        py = {
            "load": m.load, "size": m.img_size, "new": m.new, "call": m.call,
            "bg": lambda c: setattr(m, "bg", col(c)), "hint": lambda t: setattr(m, "hint", t),
            "toast": lambda t: m.toasts.append((m.millis, t)), "clear": m.clear,
            "led": lambda i, c: m.leds.__setitem__(int(i) - 1, int(c)),
            "millis": lambda: m.millis,
            "now": now or (lambda: 1795000000 + m.millis // 1000),
            "award": self._award,
            "http": self._http,
            "jenc": self._jenc, "jdec": self._jdec,
            "keys": lambda: self.lua.table_from({k: True for k in m.keys}),
            "sget": lambda k: m.storage.get(k), "sset": lambda k, v: m.storage.__setitem__(k, v),
        }
        if stage > 1:
            m.storage["stage"] = stage
            m.storage["epoch"] = 1
        self.lua.execute(f"package.path = '{ROOT}/?.lua;' .. package.path")
        self.lua.execute(f"math.randomseed({seed})")
        self.lua.execute(MOCK_LUA, self.lua.table_from(py))
        # instruction counter: a count hook every 100 instructions
        self.lua.execute("""
          __icount = 0
          debug.sethook(function() __icount = __icount + 100 end, "", 100)
          function __call(f, ...)
            __icount = 0
            local ok, err = pcall(f, ...)
            return ok, err, __icount
          end
        """)
        self.http_answer = None
        self.answer = award or (lambda n, reason: (True, {"awarded": n, "balance": 100}))
        self.maxi = {}
        src = open(os.path.join(ROOT, "main.lua")).read() + ("\n" + expose if expose else "")
        self.lua.execute("__icount = 0")
        self.lua.execute(src)
        self.maxi["boot"] = self.lua.eval("__icount")

    def _to_lua(self, v):
        if isinstance(v, dict):
            return self.lua.table_from({k: self._to_lua(x) for k, x in v.items()})
        if isinstance(v, list):
            return self.lua.table_from([self._to_lua(x) for x in v])
        return v

    def _to_py(self, v):
        if hasattr(v, "items") and callable(getattr(v, "items")):
            d = {k: self._to_py(x) for k, x in v.items()}
            if d and all(isinstance(k, int) for k in d):
                return [d[k] for k in sorted(d)]
            return d
        return v

    def _jdec(self, text):
        import json as _j
        try:
            return self._to_lua(_j.loads(str(text)))
        except Exception:
            return None

    def _jenc(self, v):
        import json as _j
        return _j.dumps(self._to_py(v))

    def _http(self, method, url, body):
        self.m.http.append((method, str(url), str(body)))
        if self.http_answer:
            ok, res = self.http_answer(method, str(url), str(body))
        else:
            top = [{"r": i + 1, "n": n, "s": sc, "st": st, "e": 1} for i, (n, sc, st) in enumerate(
                [("@toly", 48200, 8), ("@mert", 31050, 7), ("@val", 22000, 5), ("anon", 9050, 3)])]
            import json as _j
            ok, res = True, {"status": 200, "body": _j.dumps({"top": top, "me": {"r": 3, "s": 22000}}),
                             "type": "application/json", "truncated": False}
        return ok, (self.lua.table_from(res) if isinstance(res, dict) else res)

    def _award(self, n, reason):
        self.m.awards.append((int(n), str(reason)))
        ok, res = self.answer(int(n), str(reason))
        return ok, (self.lua.table_from(res) if isinstance(res, dict) else res)

    def cb(self, name, *args):
        f = self.lua.globals()[name]
        if f is None:
            return None
        ok, err, n = self.lua.globals()["__call"](f, *args)
        if n > self.maxi.get(name, 0):
            self.maxi[name] = n
        if not ok:
            raise RuntimeError(f"{name}: {err}")
        return err

    def key(self, k, rep=False):
        return self.cb("on_key", k, rep)

    def tick(self, ms=30):
        self.m.millis += ms
        self.cb("on_tick", ms)


def bot_play(r, seconds, shots=None, shot_every=None, prefix="", menu_pick=0):
    for _ in range(menu_pick):
        r.key("down")
    r.key("select")
    t = 0
    hold = None
    hold_t = 0
    n = 0
    while t < seconds * 1000:
        if hold_t <= 0:
            hold = r.rng.choice(["left", "right", "up", "down", None])
            hold_t = r.rng.randint(150, 900)
            r.m.keys = {hold} if hold else set()
            if hold:
                r.key(hold)
        if r.rng.random() < 0.02:
            r.key("select")
        if r.rng.random() < 0.002:
            r.key("back")
            r.tick()
            r.key("select")
        r.tick(30)
        t += 30
        hold_t -= 30
        if shots and shot_every and t % shot_every == 0:
            n += 1
            r.m.render(os.path.join(shots, f"{prefix}{n:03d}.png"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=120)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--stage", type=int, default=1)
    ap.add_argument("--shots")
    ap.add_argument("--every", type=int, default=0)
    a = ap.parse_args()
    r = Runner(a.seed, a.stage)
    if a.shots:
        os.makedirs(a.shots, exist_ok=True)
        r.m.render(os.path.join(a.shots, "title.png"))
    bot_play(r, a.seconds, a.shots, a.every, menu_pick=1 if a.stage > 1 else 0)
    print("max instructions per callback:", r.maxi)
    print("awards:", r.m.awards, "total", sum(n for n, _ in r.m.awards))
    print("toasts:", [t for _, t in r.m.toasts][-8:])
    print("storage:", r.m.storage)
