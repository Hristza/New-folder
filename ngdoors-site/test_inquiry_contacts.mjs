// Browser UI and wire payload checks. All business-data requests are mocked.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import http from 'node:http';
import { readFileSync } from 'node:fs';
import { resolve, extname, sep } from 'node:path';

const root = resolve('site');
const server = http.createServer((req, res) => {
  let path = decodeURIComponent(req.url.split('?')[0]);
  if (path.endsWith('/')) path += 'index.html';
  const file = resolve(root, '.' + path);
  if (!file.startsWith(root + sep)) return res.writeHead(403).end();
  try {
    res.writeHead(200, {'Content-Type':{'.html':'text/html','.js':'text/javascript','.json':'application/json','.css':'text/css','.svg':'image/svg+xml'}[extname(file)] || 'application/octet-stream'}).end(readFileSync(file));
  } catch { res.writeHead(404).end(); }
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const base = process.env.VERIFY_BASE || 'http://127.0.0.1:' + server.address().port;
const browser = await chromium.launch({headless:true, executablePath:process.platform === 'win32' ? 'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe' : undefined});
const context = await browser.newContext({viewport:{width:390,height:844}});
let payload, posts = 0, reject = false;
const errors = [];
await context.route(/https:\/\/[^/]+\.supabase\.co\//, async route => {
  if (route.request().method() === 'POST' && route.request().url().includes('/rest/v1/inquiries')) {
    posts++; payload = route.request().postDataJSON();
    return route.fulfill({status:reject ? 503 : 201, contentType:'application/json', body:''});
  }
  await route.abort();
});
// Capture the external mail-app navigation, preserving the actual fallback builder.
await context.route('**/site.js', async route => {
  const response = await route.fetch();
  await route.fulfill({response, body:(await response.text()).replace('window.location.href =', 'window.__fallback =')});
});
const page = await context.newPage();
page.on('pageerror', e => errors.push(e.message));
try {
  await page.goto(base + '/kontakti/');
  const form = page.locator('#enquiry-form');
  const send = form.locator('button[type=submit]');
  await form.locator('[name=name]').fill('Тестов посетител');
  await send.click();
  assert.equal(posts, 0, 'empty contacts must not submit');
  await form.locator('[name=email]').fill('not-an-email');
  await form.locator('[name=phone]').fill('+359 888 123 456');
  await send.click();
  assert.equal(posts, 0, 'invalid email must not submit');
  await form.locator('[name=email]').fill('visitor@example.com');
  await form.locator('[name=phone]').fill('abcdefghi');
  await send.click();
  assert.equal(posts, 0, 'invalid telephone must not submit');
  await form.locator('[name=phone]').fill('+359 (888) 123-456');
  await form.locator('[name=message]').fill('Искам информация за врата.');
  for (const width of [390,1440]) {
    await page.setViewportSize({width,height:900});
    await form.scrollIntoViewIfNeeded();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'public form overflows');
    await form.screenshot({path:`verification/inquiry-form-${width}.png`});
  }
  await send.click();
  await page.locator('#form-note[data-state=ok]').waitFor();
  assert.equal(posts, 1);
  assert.equal(payload.email, 'visitor@example.com');
  assert.equal(payload.phone, '+359 (888) 123-456');
  assert.ok(payload.contact.includes(payload.email) && payload.contact.includes(payload.phone));
  assert.equal(await form.locator('[name=email]').inputValue(), '');
  const saved = {...payload,id:'both',status:'new',created_at:new Date().toISOString()};

  reject = true;
  await form.locator('[name=name]').fill('Fallback');
  await form.locator('[name=email]').fill('fallback@example.com');
  await form.locator('[name=phone]').fill('0888123456');
  await send.click();
  await page.waitForFunction(() => !!window.__fallback);
  const fallback = new URL(await page.evaluate(() => window.__fallback)).searchParams.get('body');
  assert.ok(fallback.includes('Имейл: fallback@example.com') && fallback.includes('Телефон: 0888123456'));
  assert.equal(await form.locator('[name=email]').inputValue(), 'fallback@example.com');
  await context.addInitScript({content:readFileSync('supabase/admin_mock.js','utf8')});
  await page.goto(base + '/admin/');
  await page.locator('#app').waitFor();
  await page.evaluate(saved => {
    window.__db.inquiries.unshift(saved);
    sessionStorage.setItem('ngdoors-test-db', JSON.stringify(window.__db));
  }, saved);
  await page.reload();
  await page.locator('[data-tab=inbox]').click();
  const inbox = page.locator('#inbox');
  const inquiry = inbox.locator('article').filter({hasText:'Тестов посетител'});
  assert.ok((await inquiry.innerText()).includes('Имейл: visitor@example.com'));
  assert.ok((await inquiry.innerText()).includes('Телефон: +359 (888) 123-456'));
  assert.equal(await inquiry.getByRole('link',{name:'Обади се',exact:true}).getAttribute('href'), 'tel:+359888123456');
  assert.ok((await inquiry.getByRole('link',{name:'Отговори',exact:true}).getAttribute('href')).startsWith('mailto:visitor@example.com?'));
  assert.equal(await inbox.locator('a[href="tel:+359888123456"]').count(), 2, 'legacy phone inquiry retains call link');
  assert.equal(await inbox.locator('a[href^="mailto:petar@example.com"]').count(), 1, 'legacy email inquiry retains reply link');
  assert.equal(await inbox.locator('script,img').count(), 0, 'legacy text is not rendered as markup');
  for (const width of [390,1440]) {
    await page.setViewportSize({width,height:900});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'inbox overflows');
    await inbox.screenshot({path:`verification/inquiry-inbox-${width}.png`});
  }
  assert.deepEqual(errors, []);
  console.log('PASS: separate contacts, required/invalid values, saved payload, fallback, both admin actions, legacy inquiries, 390/1440px; backend mocked; ' + base);
} finally {
  await browser.close();
  await new Promise(r => server.close(r));
}
