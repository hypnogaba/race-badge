"""Walks every screen of FIBER RUN in the badge mock and checks what each one does:
menu, demo, a real run, game over (board submit, rank), share QR, leaderboard tabs, stats,
achievements, settings, reset, IBRL and gm codes, pause and quit, !LAMP rules, pending scores.

  .venv/bin/python tools/test_screens.py      (screenshots in tools/out/screens/)
"""
import json, os, sys
from urllib.parse import unquote_plus

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim import Runner  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "screens")
os.makedirs(OUT, exist_ok=True)
EXPOSE = """
function __S() return S end
function __scene() return scene end
function __demo() return demo end
function __ibrl() return ibrl end
function __last_run() return last_run end
function __save() return save end
function __settings() return settings end
function __lb() return lb end
function __autopilot() return autopilot(S) end
function __share() show_share() end
function __stats() show_stats() end
function __persist() persist() end
function __start() start_run(false) end
function __set_last(t) last_run = t end
"""

fails = 0


def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        fails += 1


def labels(r):
    return [o["text"] for o in r.m.objs.values() if o["kind"] == "label" and o["show"]]


def has_text(r, s):
    return any(s in t for t in labels(r))


def shot(r, name):
    r.m.render(os.path.join(OUT, name + ".png"))


def g(r, name):
    return r.lua.globals()[name]()


def play_until_over(r, autopilot=True, max_ticks=40000):
    for _ in range(max_ticks):
        if g(r, "__scene") != "play":
            break
        if autopilot and g(r, "__autopilot"):
            r.key("up")
        r.tick(17)
    for _ in range(200):
        if g(r, "__scene") != "dying":
            break
        r.tick(17)


# ---------------------------------------------------------------- title and menu
r = Runner(3, expose=EXPOSE)
shot(r, "01_title")
check("title shows the name FIBER RUN", has_text(r, "FIBER RUN"))
check("title shows the menu", all(has_text(r, s) for s in ("RUN", "LEADERBOARD", "STATS", "HOW TO PLAY", "SETTINGS")))
check("sys.tick asked for 60 Hz (17 ms)", getattr(r.m, "tick_ms", None) == 17)

for n, (scene, name) in enumerate((("lb", "leaderboard"), ("stats", "stats"), ("help", "help"),
                                   ("settings", "settings")), start=1):
    for _ in range(n):
        r.key("down")
    r.key("select")
    check(f"menu opens {name}", g(r, "__scene") == scene)
    shot(r, f"02_{name}")
    r.key("back")
    check(f"back from {name} to the title", g(r, "__scene") == "title")

# leaderboard: the mock server answers; tabs switch the query
r = Runner(4, expose=EXPOSE)
r.key("down")
r.key("select")
check("board asks all time first", r.m.http and "when=all" in r.m.http[-1][1])
check("board rows filled", has_text(r, "@toly"))
r.key("right")
check("RIGHT switches to today", "when=today" in r.m.http[-1][1] and g(r, "__lb")["when"] == "today")
shot(r, "03_board_today")
r.key("back")

# offline board
r = Runner(5, expose=EXPOSE)
r.http_answer = lambda method, url, body: (False, "offline")
r.key("down")
r.key("select")
check("offline board says so", has_text(r, "Offline"))
r.key("back")

# ---------------------------------------------------------------- codes
r = Runner(6, expose=EXPOSE)
for k in ("up", "up", "down", "down", "left", "right", "left", "right"):
    r.key(k)
check("Konami code turns IBRL MODE on", g(r, "__ibrl") is True and has_text(r, "IBRL MODE ON"))
for k in ("left", "right", "left", "right", "up", "up"):
    r.key(k)
r.tick(30)
check("gm code says gm and lights the LEDs", any(t == "gm" for _, t in r.m.toasts) and any(r.m.leds))
for k in ("up", "up", "down", "down", "left", "right", "left", "right"):
    r.key(k)
check("Konami again turns it off", g(r, "__ibrl") is False)

# ---------------------------------------------------------------- demo
r = Runner(7, expose=EXPOSE)
for _ in range(int(13000 / 30)):
    r.tick(30)
check("idle title starts the demo", g(r, "__scene") == "play" and g(r, "__demo") is True)
for _ in range(300):
    r.tick(17)
shot(r, "04_demo")
r.key("left")
check("any key leaves the demo", g(r, "__scene") == "title")
check("demo does not count as a run", g(r, "__save")["runs"] == 0)

# demo ends by itself at the title
r = Runner(8, expose=EXPOSE)
for _ in range(int(13000 / 30)):
    r.tick(30)
play_until_over(r, autopilot=False)
check("a lost demo returns to the title", g(r, "__scene") == "title" and g(r, "__save")["runs"] == 0)
check("demo sends nothing", not any("/score" in u for _, u, _ in r.m.http))

# ---------------------------------------------------------------- a real run
r = Runner(9, expose=EXPOSE)
r.key("select")
check("RUN starts a run", g(r, "__scene") == "play" and not g(r, "__demo"))
for _ in range(60):
    r.tick(17)
shot(r, "05_run")
# pause and resume
r.key("back")
check("CANCEL pauses", has_text(r, "PAUSED"))
r.key("select")
check("SELECT resumes", not has_text(r, "PAUSED"))
play_until_over(r, autopilot=True)
check("the run ends on the game over screen", g(r, "__scene") == "over")
shot(r, "06_over")
lr = g(r, "__last_run")
sent = [json.loads(b) for m, u, b in r.m.http if u.endswith("/score")]
check("score sent to the board with lap, tunnels, secs, name", len(sent) == 1 and sent[0]["score"] == lr["score"]
      and sent[0]["lap"] == lr["lap"] and sent[0]["secs"] >= 1 and sent[0]["name"] == "@val")
check("rank shown from the server", has_text(r, "YOU ARE #3"))
sv = g(r, "__save")
check("stats saved", sv["runs"] == 1 and sv["best"] == lr["score"] and sv["secs"] >= lr["secs"])
st = r.m.storage.get("save")
check("storage holds the save", st is not None)
print("   run:", lr["score"], "ms, lap", lr["lap"], "secs", lr["secs"])

# share QR
for _ in range(60):
    r.tick(17)
r.key("up")
check("UP opens the share screen", g(r, "__scene") == "share")
shot(r, "07_share")
qr = [o for o in r.m.objs.values() if o["kind"] == "rect" and o["w"] == 204]
check("a QR is on screen", len(qr) == 1)
r.key("back")

# ---------------------------------------------------------------- QR text: length and content
r2 = Runner(10, expose=EXPOSE + "\nfunction __enc(s) return urlenc(s) end")
r2.lua.globals()["__set_last"](r2.lua.table_from({"score": 4999999, "lap": 999, "tunnels": 99, "secs": 7200}))
cap = {}
r2.lua.globals()["ui"]["qr"] = lambda x, y, size, text: cap.setdefault("t", text) and None
g(r2, "__share")
t = cap.get("t", "")
check("QR text fits 256 bytes with the biggest numbers", 0 < len(t) <= 256)
txt = unquote_plus(t.split("text=", 1)[1]) if "text=" in t else ""
check("post text names the score, @doublezero, @SolanaFndn and the link",
      "4999999 ms" in txt and "@doublezero" in txt and "@SolanaFndn" in txt and "race.speedlab.pro" in txt and "Fiber Run" in txt and "zero" not in txt.lower().replace("doublezero",""))
print("   QR:", len(t), "bytes:", txt)

# ---------------------------------------------------------------- server refused / offline: pending score
r = Runner(11, expose=EXPOSE)
r.http_answer = lambda method, url, body: (False, "offline")
r.key("select")
play_until_over(r, autopilot=False)
check("offline run is kept for later", isinstance(r.m.storage.get("lb_pending"), object) and r.m.storage.get("lb_pending") is not None)
check("offline over screen says not sent", has_text(r, "not sent"))
r.http_answer = None
for _ in range(60):
    r.tick(17)
r.key("back")
check("back on the title the pending score is sent", sum(1 for _, u, _ in r.m.http if u.endswith("/score")) == 2
      and r.m.storage.get("lb_pending") is None)

# ---------------------------------------------------------------- !LAMPs
r = Runner(12, expose=EXPOSE)
r.key("select")
g(r, "__S")["score"] = 100
play_until_over(r, autopilot=False)
first_best = [a for a in r.m.awards if a[1] == "new best"]
check("no 'new best' award for the very first run", not first_best)
for _ in range(60):
    r.tick(17)
r.key("select")  # run again
play_until_over(r, autopilot=True)
check("a better second run earns 'new best'", any(a[1] == "new best" for a in r.m.awards))
n_best = sum(1 for a in r.m.awards if a[1] == "new best")
for _ in range(60):
    r.tick(17)
r.key("select")
g(r, "__S")["score"] = 0
play_until_over(r, autopilot=True)
check("'new best' at most once a day", sum(1 for a in r.m.awards if a[1] == "new best") == n_best)
# tunnel award via events
g(r, "__start")
s = g(r, "__S")
s["got"] = r.lua.table_from({"S": True, "K": True, "H": True})
s["ngot"] = 3
s["obs"] = r.lua.table_from([])
s["pick"] = r.lua.table_from([r.lua.table_from({"kind": "P", "x": 26, "y": 143})])
for _ in range(5):
    r.tick(17)
check("first tunnel of the day earns !LAMPs", any(a[1] == "first DZ tunnel today" for a in r.m.awards))
check("first tunnel unlocks the achievement", g(r, "__save")["ach"]["tunnel"] is True)
print("   awards:", r.m.awards)

# ---------------------------------------------------------------- hold to jump higher
def peak(held):
    r = Runner(13, expose=EXPOSE)
    r.key("select")
    s = g(r, "__S")
    s["obs"] = r.lua.table_from([])
    s["next_spawn"] = 1e9
    r.m.keys = {"up"} if held else set()
    r.key("up")
    top = 999
    for _ in range(90):
        r.tick(17)
        top = min(top, g(r, "__S")["y"])
    return 150 - top
lo, hi = peak(False), peak(True)
check(f"holding jumps higher ({lo:.1f} vs {hi:.1f} units)", hi > lo * 1.25)

# ---------------------------------------------------------------- Hypurr form, light-speed sky
r = Runner(14, expose=EXPOSE)
r.key("select")
g(r, "__S")["fx"]["H"] = 300
for _ in range(10):
    r.tick(17)
shot(r, "08_hypurr")
g(r, "__S")["score"] = 9999.9
for _ in range(10):
    r.tick(17)
check("10 000 ms: light speed banner", has_text(r, "LIGHT SPEED"))
check("10 000 ms: 10K CLUB achievement", g(r, "__save")["ach"]["k10"] is True)
shot(r, "09_zero_sky")

# ---------------------------------------------------------------- stats screen, settings, reset
r = Runner(15, expose=EXPOSE)
sv = g(r, "__save")
sv["ach"]["tunnel"] = True
sv["ach"]["lap2"] = True
sv["runs"], sv["best"] = 7, 1234
g(r, "__persist")
g(r, "__stats")
check("stats list achievements", has_text(r, "ACHIEVEMENTS 2/11") and has_text(r, "[x] FIRST DZ TUNNEL"))
shot(r, "10_stats")
r.key("back")
for _ in range(4):
    r.key("down")
r.key("select")
check("settings open", g(r, "__scene") == "settings")
r.key("select")
check("LEDs can be turned off", g(r, "__settings")["leds"] is False and r.m.storage["settings"]["leds"] is False)
r.tick(30)
check("LEDs stay dark when off", not any(r.m.leds))
r.key("down")
r.key("select")
check("name on board can be anon", g(r, "__settings")["name"] is False)
r.key("down")
r.key("select")  # reset: the mock confirms yes
check("reset clears the stats", g(r, "__save")["runs"] == 0 and g(r, "__save")["best"] == 0)
shot(r, "11_settings")
r.key("back")
r.key("select")
play_until_over(r, autopilot=False)
sent = [json.loads(b) for m, u, b in r.m.http if u.endswith("/score")]
check("anon name is sent when chosen", sent and sent[-1]["name"] == "anon")

# ---------------------------------------------------------------- pause and quit counts the run
r = Runner(16, expose=EXPOSE)
r.key("select")
g(r, "__S")["next_spawn"] = 1e9  # nothing to hit: the run is alive when we pause
for _ in range(200):
    r.tick(17)
r.key("back")
r.key("back")
check("quit from pause goes to the title and counts the run", g(r, "__scene") == "title" and g(r, "__save")["runs"] == 1)
check("a run quit from pause is still sent to the board", any(u.endswith("/score") for _, u, _ in r.m.http))

# HOME during the death animation: the run is counted and kept for the next launch
r = Runner(17, expose=EXPOSE)
r.key("select")
for _ in range(2000):
    if g(r, "__scene") == "dying":
        break
    r.tick(17)
check("reached the death animation", g(r, "__scene") == "dying")
r.cb("on_exit")
check("exit while dying counts the run", g(r, "__save")["runs"] == 1)
check("exit while dying keeps the run to send later", isinstance(r.m.storage.get("lb_pending"), object)
      and r.m.storage.get("lb_pending") is not None)

print("max instructions per callback:", r.maxi)
print(f"FAILED {fails}" if fails else "all passed")
sys.exit(1 if fails else 0)
