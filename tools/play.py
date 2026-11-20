"""A bot plays RACE TO ZERO in the badge mock (tools/sim.py): it checks the game runs, counts VM
instructions per callback (the badge allows 200,000) and saves screenshots.

  .venv/bin/python tools/play.py [--runs 5] [--sigma 3] [--seed 1] [--shots tools/out/shots --every 1500]

sigma: timing noise of the bot in ticks (0 = perfect). Prints how long each run lasted and the score.
"""
import argparse, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim import Runner  # noqa: E402

EXPOSE = "function __S() return S end\nfunction __scene() return scene end"


def lua_list(t):
    out = []
    i = 1
    while t[i] is not None:
        out.append(t[i])
        i += 1
    return out


def want_jump(s, rnd, sigma, plan):
    """Jump so that the trader is in the air over the next obstacle. plan keeps the noisy
    jump point chosen for each obstacle (by its table identity)."""
    obs = lua_list(s["obs"])
    for o in obs:
        right = o["x"] + o["w"]
        if right < 20 + 2:  # already behind the trader's body
            continue
        dist = o["x"] - (20 + 12 - 3)
        key = (round(o["x"] + s["dist"]), o["kind"])  # where it sits on the road
        if key not in plan:
            plan[key] = rnd.gauss(0, sigma)
        v = s["_speed"]
        air = 2 * 3.5 / 0.19
        ideal = (air * v - (o["w"] + 7)) / 2
        return dist <= ideal + plan[key] * v and dist > -o["w"]
    return False


def run_once(seed, sigma, shots=None, every=0, max_s=600):
    r = Runner(seed, expose=EXPOSE)
    rnd = random.Random(seed * 7 + 1)
    r.key("select")  # RUN
    plan = {}
    t = 0
    n = 0
    while t < max_s * 1000:
        s = r.lua.globals()["__S"]()
        sc = r.lua.globals()["__scene"]()
        if sc != "play" and sc != "dying":
            break
        if sc == "play" and s is not None:
            # speed is a local function in main.lua: recompute from distance like the game does
            s_py = {"obs": s["obs"], "dist": s["dist"], "_speed": game_speed(s)}
            if s["y"] >= 150 and want_jump(s_py, rnd, sigma, plan):
                r.key("up")
        r.tick(30)
        t += 30
        if shots and every and t % every == 0:
            n += 1
            r.m.render(os.path.join(shots, f"run{seed}_{n:03d}.png"))
    s = r.lua.globals()["__S"]()
    return t / 1000, s["score"], r


def game_speed(s):
    tick, dist, lap, fx = s["tick"], s["dist"], s["lap"], s["fx"]
    v = 1.6 + min(dist / 9000, 0.9) + max(0, tick - 7200) / 3600 * 0.35 + lap * 0.25
    if fx["K"] > 0:
        v *= 1.6
    if fx["T"] > 0:
        v *= 2
    if fx["slow"] > 0:
        v *= 0.5
    return v


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--sigma", type=float, default=3)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--shots")
    ap.add_argument("--every", type=int, default=0)
    a = ap.parse_args()
    if a.shots:
        os.makedirs(a.shots, exist_ok=True)
        Runner(a.seed).m.render(os.path.join(a.shots, "title.png"))
    worst = {}
    times = []
    for i in range(a.runs):
        secs, score, r = run_once(a.seed + i, a.sigma, a.shots if i == 0 else None, a.every)
        times.append(secs)
        for k, v in r.maxi.items():
            worst[k] = max(worst.get(k, 0), v)
        s = r.lua.globals()["__S"]()
        st = s["stats"]
        print(f"run {i + 1}: {secs:6.1f} s  score {int(score):6d}  lap {s['lap'] + 1}  tunnels {st['tunnels']}"
              f"  coins {st['coins']}  bits {st['bits']}  hits {st['hits']}")
        if a.shots and i == 0:
            r.m.render(os.path.join(a.shots, f"run{a.seed}_end.png"))
    times.sort()
    print("median run:", times[len(times) // 2], "s")
    print("max instructions per callback:", worst)
