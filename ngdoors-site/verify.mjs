// Renders the built site in Chromium and checks what the HTML checker cannot:
// horizontal overflow, console errors, failed requests, and whether any content
// is still invisible after scrolling.
//
//   python3 build.py
//   python3 -m http.server 8099 --directory site &
//   npm i playwright && node verify.mjs
//
// Two traps, both of which once produced a false result here:
//  - Scroll by documentElement.scrollHeight, not body's. body is shorter, the loop
//    stops early, and unvisited cards are reported as a defect that is not there.
//  - Wait longer than the reveal takes (600ms transition + up to 300ms stagger).
//    A 500ms wait reports cards mid-fade as broken.
// Serve over HTTP. On file:// Chrome refuses the woff2 fetches and four fonts
// report net::ERR_FAILED on a page that is fine.

import { chromium } from 'playwright';
const B = 'http://127.0.0.1:8099';
const PAGES = ['/', '/vrati/', '/produkt/d-012-lara-antratsit-2890/', '/nastilki/', '/kontakti/'];
const WIDTHS = [390, 768, 1440];
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
let bad = 0;

const settle = async p => {
  // documentElement, not body: body is shorter and the loop stops early.
  await p.evaluate(async () => {
    for (let y = 0; y < document.documentElement.scrollHeight; y += window.innerHeight * 0.8) {
      window.scrollTo(0, y); await new Promise(r => setTimeout(r, 90));
    }
  });
  // 600ms transition + up to 300ms stagger: waiting less reports a false failure.
  await p.waitForTimeout(1200);
};

for (const w of WIDTHS) {
  const p = await b.newPage({ viewport: { width: w, height: 900 } });
  const errs = [];
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  p.on('pageerror', e => errs.push('PAGEERROR ' + e.message));
  p.on('requestfailed', r => errs.push('REQFAIL ' + r.url().split('/').pop()));
  for (const path of PAGES) {
    await p.goto(B + path, { waitUntil: 'networkidle' });
    await settle(p);
    const ov = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    const hid = await p.evaluate(() => [...document.querySelectorAll('.reveal')].filter(e => getComputedStyle(e).opacity === '0').length);
    if (ov > 0 || hid > 0) bad++;
    console.log(`${String(w).padStart(4)}  ${path.padEnd(38)} overflow=${ov}px hidden=${hid}${(ov||hid)?'  <-- PROBLEM':''}`);
  }
  if (errs.length) { bad++; console.log(`${w}: ERRORS`, [...new Set(errs)].slice(0, 6)); }
  else console.log(`${w}: no console errors, no failed requests`);
  await p.close();
}

// The real failure mode: jump to the bottom, skipping everything in between.
const jp = await b.newPage({ viewport: { width: 1440, height: 900 } });
await jp.goto(B + '/nastilki/', { waitUntil: 'networkidle' });
await jp.keyboard.press('End');
await jp.waitForTimeout(1500);
const jumpHidden = await jp.evaluate(() =>
  [...document.querySelectorAll('.reveal')].filter(e => getComputedStyle(e).opacity === '0' &&
    e.getBoundingClientRect().top < window.innerHeight).length);
console.log('End-key jump: on-screen-but-invisible cards =', jumpHidden, jumpHidden ? ' <-- PROBLEM' : '');
if (jumpHidden) bad++;
await jp.close();

const rp = await b.newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
await rp.goto(B + '/vrati/', { waitUntil: 'networkidle' });
const rHidden = await rp.evaluate(() => [...document.querySelectorAll('.reveal')].filter(e => getComputedStyle(e).opacity === '0').length);
console.log('reduced-motion: hidden reveals =', rHidden, rHidden ? ' <-- PROBLEM' : '');
if (rHidden) bad++;
await rp.close();
await b.close();
console.log(bad ? `\n${bad} PROBLEM(S)` : '\nALL GREEN');
