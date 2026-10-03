// Live acceptance test in isolated headless Brave. No mocks, no persistent profile.
// Credentials arrive through stdin; the hidden test product and its uploads are removed.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { resolve } from 'node:path';
let input = '';
for await (const chunk of process.stdin) input += chunk;
const credentials = JSON.parse(input);
const base = 'https://ngdoors.pages.dev', api = 'https://glrijbqwbykcinhgjeys.supabase.co';
const id = randomUUID(), name = 'Codex hidden verification ' + id;
const headers = {apikey:credentials.public_key, Authorization:'Bearer '+credentials.access_token, 'Content-Type':'application/json', Prefer:'return=representation'};
async function request(method, path, body) {
  const response = await fetch(api + path, {method, headers, body:body===undefined?undefined:JSON.stringify(body)});
  const text = await response.text();
  assert.ok(response.ok, method+' '+path.split('?')[0]+' HTTP '+response.status);
  return text ? JSON.parse(text) : null;
}
const browser = await chromium.launch({headless:true, executablePath:'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe'});
const context = await browser.newContext({viewport:{width:390,height:844}});
const page = await context.newPage(), errors = [], uploads = new Set();
page.on('pageerror', error => errors.push(error.message));
page.on('response', response => {
  const url = new URL(response.url()), prefix = '/storage/v1/object/media/';
  if (response.request().method()==='POST' && response.ok() && url.pathname.startsWith(prefix)) uploads.add(decodeURIComponent(url.pathname.slice(prefix.length)));
});
try {
  const catalogue = await (await fetch(base+'/admin/catalogue.json')).json();
  await request('POST','/rest/v1/products',{id,name,section:'door',category:catalogue.categories[0].path,hidden:true,price:0,images:[],size_prices:[]});
  await page.goto(base+'/admin/');
  await page.locator('#login input[name=email]').fill(credentials.email);
  await page.locator('#login input[name=password]').fill(credentials.password);
  await page.locator('#login button[type=submit]').click();
  await page.locator('#app').waitFor({state:'visible',timeout:30000});
  await page.locator('[data-tab=catalogue]').click();
  const row = page.locator('#rows > .row').first();
  await row.locator('.size-editor summary').click();
  assert.ok(await row.locator('.size-row').count()>0);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:resolve('verification/live-admin-sizes-390.png')});
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:resolve('verification/live-admin-sizes-1440.png')});
  await page.locator('[data-tab=mine]').click();
  const own = page.locator('#mine-rows .row').filter({hasText:name});
  await own.getByRole('button',{name:'Редактирай',exact:true}).click();
  for (const [size,price] of [['91 × 213','245,50'],['101 × 223','307,01']]) {
    await page.locator('#psizes').getByRole('button',{name:'+ Добави размер',exact:true}).click();
    const entry=page.locator('#psizes .size-row').last();
    await entry.getByRole('textbox',{name:'Размер',exact:true}).fill(size);
    await entry.getByRole('textbox',{name:'Цена за размера в евро',exact:true}).fill(price);
  }
  const png = await page.evaluate(()=>{const c=document.createElement('canvas');c.width=80;c.height=120;c.getContext('2d').fillRect(0,0,80,120);return c.toDataURL('image/png').split(',')[1];});
  await page.locator('#pfiles').setInputFiles({name:'hidden-verification.png',mimeType:'image/png',buffer:Buffer.from(png,'base64')});
  await page.locator('#pthumbs figure').waitFor({timeout:30000});
  await page.locator('#pform').getByRole('button',{name:'Запази',exact:true}).click();
  await page.locator('#pform').waitFor({state:'hidden',timeout:30000});
  const saved = (await request('GET','/rest/v1/products?id=eq.'+id+'&select=*'))[0];
  assert.equal(saved.hidden,true);
  assert.deepEqual(saved.size_prices,[{size:'91 × 213',price:245.50},{size:'101 × 223',price:307.01}]);
  assert.ok(saved.images.length===1);
  saved.images.forEach(photo=>{uploads.add(photo.s);uploads.add(photo.l);});
  await page.reload();
  await page.locator('[data-tab=mine]').click();
  await page.locator('#mine-rows .row').filter({hasText:name}).getByRole('button',{name:'Редактирай',exact:true}).click();
  assert.equal(await page.locator('#psizes .size-row').count(),2);
  assert.equal(await page.locator('#psizes .size-row').nth(1).getByRole('textbox',{name:'Цена за размера в евро',exact:true}).inputValue(),'307,01');
  assert.deepEqual(errors,[]);
  console.log('LIVE BRAVE PASS: owner password login, mobile/desktop render, photo upload, per-size save and reload');
} finally {
  await request('DELETE','/rest/v1/products?id=eq.'+id);
  if(uploads.size) await request('DELETE','/storage/v1/object/media',{prefixes:[...uploads]});
  assert.deepEqual(await request('GET','/rest/v1/products?id=eq.'+id+'&select=id'),[]);
  await browser.close();
  console.log('CLEANUP PASS: hidden test product and uploaded files removed');
}
