// Screenshots of the built site for review.
//
//   python3 build.py
//   python3 -m http.server 8099 --directory site &
//   npm i playwright && node shots.mjs      # writes into /tmp/shots
//
// The trap this file exists to avoid: a fullPage capture photographs the whole
// document while the browser sits at scroll position 0, so every scroll-revealed
// section is still at opacity 0 and comes out BLANK on a page that is perfectly
// fine. The first run of this showed the homepage's priced-flooring panel as an
// empty green box and it looked like a serious bug. prep() therefore walks the
// page, then forces the reveal end-state and waits for every image to decode,
// and reports anything still hidden rather than quietly photographing it.
//
// #lb-img is the lightbox target and is empty until something is clicked; it is
// excluded from the unloaded-image count rather than counted as a defect.

import { chromium } from 'playwright';
const B = process.env.VERIFY_BASE || 'http://127.0.0.1:8099';
const b = await chromium.launch(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {});

// A fullPage capture sits at scroll 0 and photographs the whole document, so any
// scroll-revealed section is legitimately still at opacity 0 and photographs blank
// while the page is perfectly fine. Force the end state for the capture only.
const prep = async p => {
  await p.evaluate(async () => {
    for (let y = 0; y < document.documentElement.scrollHeight; y += window.innerHeight * 0.8) {
      window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120));
    }
    window.scrollTo(0, 0);
    document.querySelectorAll('.reveal').forEach(e => {
      e.style.transitionDelay = '0s'; e.classList.add('is-in');
    });
    await new Promise(r => setTimeout(r, 300));
    await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
  });
  await p.waitForTimeout(900);
  const bad = await p.evaluate(() => ({
    hidden: [...document.querySelectorAll('.reveal')].filter(e => getComputedStyle(e).opacity !== '1').length,
    // #lb-img is the lightbox target: empty until something is clicked. Not a defect.
    unloaded: [...document.images].filter(i => i.id !== 'lb-img' && (!i.complete || i.naturalWidth === 0)).length,
  }));
  return bad;
};

const shot = async (path, file, vp) => {
  const p = await b.newPage({ viewport: vp });
  await p.goto(B + path, { waitUntil: 'networkidle' });
  const bad = await prep(p);
  await p.screenshot({ path: '/tmp/shots/' + file, fullPage: true });
  console.log(`${file.padEnd(28)} hidden=${bad.hidden} unloadedImgs=${bad.unloaded}`);
  await p.close();
};

await shot('/', '1-home-desktop.png', { width: 1440, height: 950 });
await shot('/vrati/vhodni-vrati/vhodni-vrati-za-apartament-g-door/seriya-dublin/', '2-category-prices.png', { width: 1440, height: 950 });

const p = await b.newPage({ viewport: { width: 1440, height: 1000 } });
await p.goto(B + '/produkt/d-012-lara-antratsit-2890/', { waitUntil: 'networkidle' });
await prep(p);
await p.screenshot({ path: '/tmp/shots/3-product-base-size.png' });
const pills = await p.$$('.size-pill');
await pills[pills.length - 1].click();
await p.waitForTimeout(800);
await p.screenshot({ path: '/tmp/shots/4-product-larger-size.png' });
console.log('product page: price after picking the largest size =',
  await p.$eval('.price-big', e => e.textContent.trim()));
await p.close();

const m = await b.newPage({ viewport: { width: 390, height: 844 } });
await m.goto(B + '/produkt/d-012-lara-antratsit-2890/', { waitUntil: 'networkidle' });
await m.waitForTimeout(700);
await m.evaluate(() => window.scrollTo(0, 1100));
await m.waitForTimeout(1000);
await m.screenshot({ path: '/tmp/shots/5-phone-sticky-bar.png' });
await m.close();
await b.close();
