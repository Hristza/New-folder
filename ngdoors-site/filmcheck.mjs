/* Exercise the scene films in a real browser.
 *
 * Everything here is a thing a screenshot cannot tell you. A band is opacity 0 until
 * its reveal fires, so a full-page capture of an unscrolled page shows an empty box
 * and still reports a clean pass; a <video> that never started looks exactly like one
 * that did, because its poster is its own first frame; and a parallax that does nothing
 * is invisible in a still. So each of those is asserted, not photographed.
 *
 * The page sets `scroll-behavior: smooth`, which means a scroll returns before it has
 * happened. Every scroll here is 'instant' and then waited on.
 */
import { chromium } from 'playwright';

const B = process.env.VERIFY_BASE || 'http://127.0.0.1:8099';
const PAGES = [
  ['/', 'home'],
  ['/vrati/vhodni-vrati/', 'vhodni'],
  ['/nastilki/', 'nastilki'],
  ['/parvazi/', 'parvazi'],
  ['/vrati/', 'vrati'],
];
const WIDTHS = [390, 768, 1440];

let bad = 0;
const fail = (m) => { console.log('  FAIL ' + m); bad++; };
const ok = (m) => console.log('  ok   ' + m);

const b = await chromium.launch(
  process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {});

for (const w of WIDTHS) {
  const ctx = await b.newContext({ viewport: { width: w, height: 900 }, deviceScaleFactor: 1 });
  for (const [path, name] of PAGES) {
    const p = await ctx.newPage();
    const errs = [];
    p.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
    p.on('pageerror', (e) => errs.push(String(e)));
    const bad404 = [];
    p.on('response', (r) => { if (r.status() >= 400) bad404.push(r.status() + ' ' + r.url()); });

    await p.goto(B + path, { waitUntil: 'domcontentloaded' });
    await p.waitForTimeout(600);
    console.log(`\n[${w}] ${path}`);

    const films = await p.$$('[data-film]');
    if (!films.length) { fail('no [data-film] on the page'); await p.close(); continue; }
    ok(`${films.length} film element(s)`);

    for (const f of films) {
      const id = await f.evaluate((v) => v.getAttribute('aria-label').slice(0, 28));

      // Bring it into view the way a reader would, then let the observer and the
      // decoder actually do their work before asking whether they did.
      await f.evaluate((v) => v.scrollIntoView({ block: 'center', behavior: 'instant' }));
      await p.waitForTimeout(1400);

      const st = await f.evaluate((v) => {
        const box = v.parentNode;
        const cs = getComputedStyle(box);
        const r = v.getBoundingClientRect();
        return {
          revealed: !box.classList.contains('reveal') || box.classList.contains('is-in'),
          opacity: parseFloat(cs.opacity),
          t: v.currentTime, paused: v.paused, w: v.videoWidth, h: v.videoHeight,
          src: v.currentSrc.split('/').pop(),
          rectW: Math.round(r.width), rectH: Math.round(r.height),
          transform: getComputedStyle(v).transform,
        };
      });

      if (!st.revealed || st.opacity < 0.99) fail(`${id}: still hidden (opacity ${st.opacity})`);
      if (!st.w) fail(`${id}: no video decoded (videoWidth 0, src ${st.src || 'none'})`);
      if (st.paused || st.t <= 0) fail(`${id}: not playing (t=${st.t} paused=${st.paused})`);
      if (st.rectH < 100) fail(`${id}: rendered only ${st.rectH}px tall`);
      if (!st.w) continue;
      ok(`${id} — ${st.src} ${st.w}x${st.h} → ${st.rectW}x${st.rectH}, t=${st.t.toFixed(2)}s`);
    }

    // Parallax has to actually move. Read one band, scroll a screen, read it again.
    const band = await p.$('.scene .film');
    if (band) {
      const before = await band.evaluate((v) => v.style.transform);
      await p.evaluate(() => window.scrollBy({ top: 400, behavior: 'instant' }));
      await p.waitForTimeout(400);
      const after = await band.evaluate((v) => v.style.transform);
      if (!after || after === before) fail(`parallax did not move (${before} -> ${after})`);
      else ok(`parallax ${before || 'none'} -> ${after}`);
    }

    const over = await p.evaluate(() =>
      document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (over > 0) fail(`horizontal overflow: ${over}px`);
    else ok('no horizontal overflow');

    if (errs.length) fail('console: ' + errs.slice(0, 3).join(' | '));
    if (bad404.length) fail('bad responses: ' + bad404.slice(0, 3).join(' | '));
    if (!errs.length && !bad404.length) ok('console clean, no 4xx/5xx');

    await p.close();
  }
  await ctx.close();
}

// Reduced motion is its own contract: nothing plays, and nothing is invisible.
const rm = await b.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
const p = await rm.newPage();
await p.goto(B + '/vrati/vhodni-vrati/', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(1200);
console.log('\n[reduced-motion] /vrati/vhodni-vrati/');
const r = await p.evaluate(() => {
  const v = document.querySelector('[data-film]');
  return { paused: v.paused, autoplay: v.hasAttribute('autoplay'),
           opacity: parseFloat(getComputedStyle(v.parentNode).opacity),
           transform: getComputedStyle(v).transform };
});
if (!r.paused) fail('film still playing under prefers-reduced-motion');
else ok('film paused');
if (r.opacity < 0.99) fail(`band invisible under reduced motion (opacity ${r.opacity})`);
else ok('band visible');
if (r.transform !== 'none') fail(`parallax transform still applied: ${r.transform}`);
else ok('no parallax transform');
await b.close();

console.log(bad ? `\n${bad} FAILURE(S)` : '\nALL FILM CHECKS PASS');
process.exit(bad ? 1 : 0);
