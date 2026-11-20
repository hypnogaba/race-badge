// node --experimental-sqlite server/test.mjs  (RACE TO ZERO badge leaderboard)
// Signs requests the way the badge server does (own Ed25519 key) and runs them
// against the worker with an in-memory SQLite standing in for D1.
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import worker, { hooks, cleanName } from './worker.js';

const db = new DatabaseSync(':memory:');
db.exec(readFileSync(new URL('./schema.sql', import.meta.url), 'utf8'));
const D1 = {
  prepare(sql) {
    const st = db.prepare(sql.replace(/\?(\d+)/g, '?'));
    // D1 numbers its parameters (?1, ?2 ...); node:sqlite takes them in order of appearance
    const order = [...sql.matchAll(/\?(\d+)/g)].map((m) => Number(m[1]) - 1);
    return {
      bind: (...args) => {
        const vals = order.map((k) => args[k]);
        return {
          run: async () => st.run(...vals),
          all: async () => ({ results: st.all(...vals) }),
          first: async () => st.get(...vals) ?? null,
        };
      },
    };
  },
};
D1.batch = async (stmts) => { for (const s of stmts) await s.run(); };
const env = { DB: D1 };

const kp = await crypto.subtle.generateKey('Ed25519', true, ['sign', 'verify']);
const pub = Buffer.from(await crypto.subtle.exportKey('raw', kp.publicKey)).toString('base64');
hooks.fetchKey = async () => ({ id: 'k1', key: pub });

const hex = (b) => Buffer.from(b).toString('hex');
let reqN = 0;
async function call(method, path, bodyObj, { user = 'u1', badge = '7K2Q9M', app = 'race-to-zero', time = Date.now(), tamper = false, req: rid } = {}) {
  const url = `https://race-badge-scores.example.workers.dev${path}`;
  const body = bodyObj === undefined ? '' : JSON.stringify(bodyObj);
  const id = rid ?? `r${++reqN}`;
  const hash = hex(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(body)));
  const signed = ['badge-http-v1', method, url, hash, app, badge, user, String(time), id].join('\n');
  const sig = Buffer.from(await crypto.subtle.sign('Ed25519', kp.privateKey, new TextEncoder().encode(signed))).toString('base64');
  const headers = {
    'x-badge-app': app, 'x-badge-id': badge, 'x-badge-user': user, 'x-badge-time': String(time),
    'x-badge-request': id, 'x-badge-key': 'k1', 'x-badge-signature': sig,
  };
  const sent = tamper ? JSON.stringify({ ...bodyObj, score: 4_999_999 }) : body;
  const res = await worker.fetch(new Request(url, { method, headers, body: method === 'GET' ? undefined : sent }), env);
  return { status: res.status, data: await res.json() };
}

let fails = 0;
const check = (name, ok) => { console.log((ok ? 'ok   ' : 'FAIL ') + name); if (!ok) fails++; };

const S = (score, extra = {}) => ({ score, lap: 1, tunnels: 0, secs: 120, name: '@alice', ...extra });
let r = await call('POST', '/score', S(1200), { user: 'u1' });
check('signed score accepted', r.status === 200 && r.data.top[0].s === 1200 && r.data.me.r === 1);
r = await call('POST', '/score', S(900), { user: 'u1' });
check('lower score does not replace the best', r.data.top[0].s === 1200);
r = await call('POST', '/score', S(3000, { name: '@bob', lap: 3 }), { user: 'u2' });
check('ranking order', r.data.top[0].n === '@bob' && r.data.top[0].l === 3 && r.data.top[1].n === '@alice' && r.data.me.r === 1);
r = await call('GET', '/top?n=10', undefined, { user: 'u1' });
check('top + my rank', r.status === 200 && r.data.top.length === 2 && r.data.me.r === 2 && r.data.me.s === 1200);
r = await call('GET', '/top?n=10&when=today', undefined, { user: 'u1' });
check('today board', r.data.when === 'today' && r.data.top.length === 2 && r.data.me.r === 2);
// next day: the all-time board keeps everyone, today's starts empty
const realNow = hooks.now;
hooks.now = () => realNow() + 86_400_000;
r = await call('GET', '/top?when=today', undefined, { user: 'u1', time: hooks.now() });
check('new day: today is empty', r.data.top.length === 0 && r.data.me === null);
r = await call('POST', '/score', S(500), { user: 'u1', time: hooks.now() });
r = await call('GET', '/top?when=today', undefined, { user: 'u1', time: hooks.now() });
check('new day: a lower run leads today', r.data.top[0].s === 500 && r.data.me.r === 1);
r = await call('GET', '/top', undefined, { user: 'u1', time: hooks.now() });
check('new day: all time keeps the best', r.data.top[0].s === 3000 && r.data.me.s === 1200);
hooks.now = realNow;
r = await call('GET', '/top?n=10', undefined, { user: 'u9' });
check('player without a score: me is null', r.data.me === null);

r = await call('POST', '/score', S(100), { tamper: true });
check('body changed after signing: refused', r.status === 401);
r = await call('POST', '/score', S(100), { app: 'forkbomb' });
check('other app id: refused', r.status === 401);
r = await call('POST', '/score', S(100), { time: Date.now() - 120_000 });
check('old request: refused', r.status === 401);
await call('GET', '/top', undefined, { req: 'same' });
r = await call('GET', '/top', undefined, { req: 'same' });
check('replayed request: refused', r.status === 401);
const plain = await worker.fetch(new Request('https://x.workers.dev/top'), env);
check('unsigned request: refused', plain.status === 401);
r = await call('POST', '/score', S(99_000_000));
check('absurd score: refused', r.status === 400);
r = await call('POST', '/score', S(50_000, { secs: 30 }));
check('score too high for its time: refused', r.status === 400);
r = await call('POST', '/score', S(10, { lap: 0 }));
check('lap out of range: refused', r.status === 400);
r = await call('POST', '/score', { score: 10, lap: 1, tunnels: 0 });
check('missing secs: refused', r.status === 400);
check('name cleaning', cleanName('@verylongname_1234567890\u0007') === '@verylongname_12' && cleanName('') === 'anon');

console.log(fails ? `FAILED ${fails}` : 'all passed');
process.exit(fails ? 1 : 0);
