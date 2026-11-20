// RACE TO ZERO (badge) leaderboard: a Cloudflare Worker with a D1 database.
// Every request must come through the badge server, which signs it (X-Badge-* headers).
//   POST /score  {score, lap, tunnels, secs, name}  -> keeps the player's best, all time and today (UTC)
//   GET  /top?n=10&when=all|today                   -> {top: [{r, n, s, l}], me: {r, s} | null, when}
// See https://solana.com/breakpoint/badge/apps/docs (http: "What your server receives").

export const APP = 'race-to-zero';
const SERVER = 'https://badge-api.solana.com';
const MAX_SCORE = 5_000_000;
// The most a run can earn per second: the game speeds up without a ceiling, so a 30 minute run with
// score x2, the tunnel's x3 and IBRL earns about 370/s; 1000/s leaves room. A score above this for the time
// it claims is refused. The badge reports that time itself, so this only stops clumsy cheats; a real
// check would need the run's inputs replayed on the server.
const MAX_PER_SEC = 1000;
const BONUS_ROOM = 5000;
const MAX_SECS = 86_400;

const keys = new Map(); // key id -> CryptoKey
const seen = new Map(); // X-Badge-Request -> time
let fetching = null;
let fetchedAt = 0;

export const hooks = { fetchKey: async () => (await fetch(`${SERVER}/api/http/key`)).json(), now: () => Date.now() };

async function badgeKey(id) {
  if (!keys.has(id) && !fetching && hooks.now() - fetchedAt > 60_000) {
    fetchedAt = hooks.now();
    fetching = (async () => {
      const k = await hooks.fetchKey();
      const raw = Uint8Array.from(atob(k.key), (c) => c.charCodeAt(0));
      keys.set(k.id, await crypto.subtle.importKey('raw', raw, 'Ed25519', false, ['verify']));
    })()
      .catch(() => { fetchedAt = 0; })
      .finally(() => { fetching = null; });
  }
  if (!keys.has(id) && fetching) await fetching;
  return keys.get(id) ?? null;
}

function once(id, time) {
  for (const [k, t] of seen) if (hooks.now() - t > 60_000) seen.delete(k);
  if (seen.has(id)) return false;
  seen.set(id, time);
  return true;
}

const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');

/** The badge and player behind a request from RACE TO ZERO, or null. */
export async function fromBadge(req, body) {
  const h = (n) => req.headers.get(n) ?? '';
  const time = Number(h('x-badge-time'));
  const id = h('x-badge-request');
  if (h('x-badge-app') !== APP || !(Math.abs(hooks.now() - time) < 60_000) || !id) return null;
  const key = await badgeKey(h('x-badge-key'));
  if (!key) return null;
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(body));
  const signed = ['badge-http-v1', req.method, req.url, hex(hash), APP, h('x-badge-id'),
    h('x-badge-user'), h('x-badge-time'), id].join('\n');
  let sig;
  try { sig = Uint8Array.from(atob(h('x-badge-signature')), (c) => c.charCodeAt(0)); } catch { return null; }
  if (!(await crypto.subtle.verify('Ed25519', key, sig, new TextEncoder().encode(signed)))) return null;
  if (!once(id, time)) return null;
  return { badge: h('x-badge-id'), user: h('x-badge-user') };
}

const json = (data, status = 200) => new Response(JSON.stringify(data), {
  status, headers: { 'content-type': 'application/json' },
});

/** A name safe to show on a 320 px screen: printable ASCII, 16 chars at most. */
export function cleanName(v) {
  const s = String(v ?? '').replace(/[^\x20-\x7E]/g, '').trim().slice(0, 16);
  return s || 'anon';
}

const int = (v, lo, hi) => Number.isInteger(v) && v >= lo && v <= hi;

export const day = (ms) => Math.floor(ms / 86_400_000);

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const body = req.method === 'GET' || req.method === 'HEAD' ? '' : await req.text();
    const who = await fromBadge(req, body);
    if (!who) return json({ error: 'not from a badge' }, 401);

    if (req.method === 'POST' && url.pathname === '/score') {
      let d;
      try { d = JSON.parse(body); } catch { return json({ error: 'bad json' }, 400); }
      if (!int(d.score, 1, MAX_SCORE) || !int(d.lap, 1, 999) || !int(d.tunnels, 0, 9999) || !int(d.secs, 1, MAX_SECS)) {
        return json({ error: 'bad score' }, 400);
      }
      if (d.score > d.secs * MAX_PER_SEC + BONUS_ROOM) return json({ error: 'too fast' }, 400);
      const now = hooks.now();
      const name = cleanName(d.name);
      // the best per player, all time (one row per badge owner) and per UTC day
      await env.DB.batch([
        env.DB.prepare(
          `INSERT INTO scores (user, badge, name, score, lap, tunnels, at) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
           ON CONFLICT(user) DO UPDATE SET badge = ?2, name = ?3, score = ?4, lap = ?5, tunnels = ?6, at = ?7
           WHERE excluded.score > scores.score`,
        ).bind(who.user, who.badge, name, d.score, d.lap, d.tunnels, now),
        env.DB.prepare(
          `INSERT INTO daily (day, user, name, score, lap, at) VALUES (?1, ?2, ?3, ?4, ?5, ?6)
           ON CONFLICT(day, user) DO UPDATE SET name = ?3, score = ?4, lap = ?5, at = ?6
           WHERE excluded.score > daily.score`,
        ).bind(day(now), who.user, name, d.score, d.lap, now),
        env.DB.prepare('UPDATE scores SET runs = runs + 1 WHERE user = ?1').bind(who.user),
      ]);
      return json(await board(env, who.user, 10, url.searchParams.get('when') === 'today' ? 'today' : 'all'));
    }

    if (req.method === 'GET' && url.pathname === '/top') {
      const n = Math.min(10, Math.max(1, Number(url.searchParams.get('n')) || 10));
      return json(await board(env, who.user, n, url.searchParams.get('when') === 'today' ? 'today' : 'all'));
    }
    return json({ error: 'not found' }, 404);
  },
};

async function board(env, user, n, when) {
  const today = when === 'today';
  const from = today ? 'daily WHERE day = ?2' : 'scores WHERE ?2 = ?2';
  const d = day(hooks.now());
  const top = await env.DB.prepare(
    `SELECT name, score, lap FROM ${from} ORDER BY score DESC, at ASC LIMIT ?1`,
  ).bind(n, d).all();
  const rows = (top.results ?? []).map((r, i) => ({ r: i + 1, n: r.name, s: r.score, l: r.lap }));
  const mine = await env.DB.prepare(`SELECT score FROM ${from} AND user = ?1`).bind(user, d).first();
  let me = null;
  if (mine) {
    const above = await env.DB.prepare(`SELECT COUNT(*) AS c FROM ${from} AND score > ?1`).bind(mine.score, d).first();
    me = { r: (above?.c ?? 0) + 1, s: mine.score };
  }
  return { top: rows, me, when };
}
