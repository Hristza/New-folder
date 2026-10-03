import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';

const live = process.argv.includes('--live');
const root = path.resolve('site');
const catalogue = JSON.parse(await fs.readFile(path.join(root, 'admin/catalogue.json'), 'utf8'));
const mime = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
  '.avif': 'image/avif', '.webp': 'image/webp', '.woff2': 'font/woff2', '.json': 'application/json'};
let server;
let origin = 'https://ngdoors.pages.dev';
if (!live) {
  server = http.createServer(async (req, res) => {
    try {
      const requested = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
      const target = path.resolve(root, '.' + requested, requested.endsWith('/') ? 'index.html' : '');
      if (!target.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
      const data = await fs.readFile(target);
      res.writeHead(200, {'Content-Type': mime[path.extname(target)] || 'application/octet-stream'}).end(data);
    } catch { res.writeHead(404).end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = 'http://127.0.0.1:' + server.address().port;
}
const browser = await chromium.launch({headless: true,
  executablePath: 'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe',
  args: ['--no-first-run', '--no-default-browser-check']});
try {
  for (const key of ['door:2714', 'door:1820']) {
    const item = catalogue.items.find(x => x.key === key);
    assert.ok(item, 'Missing target product');
    for (const width of [390, 1440]) {
      const context = await browser.newContext({viewport: {width, height: 980}, reducedMotion: 'reduce'});
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push(String(e)));
      await page.goto(origin + item.url, {waitUntil: 'networkidle'});
      await page.addStyleTag({content: '*,*::before,*::after{transition:none!important;animation:none!important}'});
      await page.waitForFunction(() => { const i = document.querySelector('#pmain img'); return i?.complete && i.naturalWidth > 0; });
      const image = await page.locator('#pmain img').evaluate(i => ({src: i.currentSrc, width: i.naturalWidth}));
      assert.match(image.src, /-gpt-.*\.avif$/);
      assert.match(await page.evaluate(async src => (await fetch(src)).headers.get('content-type'), image.src), /image\/avif/);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      assert.deepEqual(errors, []);
      await page.screenshot({path: `verification/photo-avif-${key.replace(':', '-')}-${width}-${live ? 'live' : 'local'}.png`});
      console.log(JSON.stringify({key, width, mode: live ? 'production' : 'local', avif_decoded: true, no_overflow: true, page_errors: errors.length}));
      await context.close();
    }
  }
} finally {
  await browser.close();
  if (server) await new Promise(resolve => server.close(resolve));
}
