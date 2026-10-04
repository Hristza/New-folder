// Actual owner Publish button acceptance. Credentials arrive only through stdin.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
let input = '';
for await (const chunk of process.stdin) input += chunk;
const credentials = JSON.parse(input);
const browser = await chromium.launch({headless: true,
  executablePath: 'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe'});
try {
  const page = await browser.newPage({viewport: {width: 1440, height: 980}});
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('https://ngdoors.pages.dev/admin/', {waitUntil: 'networkidle'});
  await page.locator('#login input[name=email]').fill(credentials.email);
  await page.locator('#login input[name=password]').fill(credentials.password);
  await page.locator('#login button[type=submit]').click();
  await page.locator('#app').waitFor({state: 'visible', timeout: 30000});
  const response = page.waitForResponse(r => r.url().includes('/functions/v1/publish') && r.request().method() === 'POST');
  await page.locator('#publish').click();
  const result = await response;
  assert.equal(result.status(), 200);
  assert.equal((await result.json()).ok, true);
  await page.waitForFunction(() => document.querySelector('#publish-bar')?.getAttribute('data-state') === 'ok');
  assert.deepEqual(errors, []);
  await page.screenshot({path: 'verification/live-publish-request.png'});
  console.log('LIVE OWNER PUBLISH: real password login, real button, HTTP 200, build hook accepted; deployment completion must be checked separately.');
} finally {
  await browser.close();
}
