// Exercise native confirmation dialogs, with a mocked backend and real page scripts.
// Every denied action must leave database, storage, authentication and publishing untouched.
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
    const type = {'.html':'text/html','.js':'text/javascript','.json':'application/json','.css':'text/css','.svg':'image/svg+xml','.avif':'image/avif','.webp':'image/webp'}[extname(file)];
    res.writeHead(200, {'Content-Type':type || 'application/octet-stream'}).end(readFileSync(file));
  } catch { res.writeHead(404).end(); }
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const base = process.env.VERIFY_BASE || 'http://127.0.0.1:' + server.address().port;
const browser = await chromium.launch({headless:true,
  executablePath:process.env.BRAVE_PATH || (process.platform==='win32' ? 'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe' : undefined)});
const context = await browser.newContext({viewport:{width:390,height:844}});
await context.addInitScript({content:readFileSync('supabase/admin_mock.js','utf8')});
// Live-asset verification still uses a mocked backend. Never send test writes to Supabase.
await context.route(/https:\/\/[^/]+\.supabase\.co\//, route => route.abort());
const page = await context.newPage(), errors = [], checked = [];
page.on('pageerror', e => errors.push(e.message));
const mutations = () => page.evaluate(() => JSON.stringify({db:window.__db,calls:window.__calls.filter(c=>c.op!=='select')}));
async function deny(name, action) {
  const before = await mutations();
  let count = 0;
  const listener = async dialog => {
    count++;
    assert.equal(dialog.type(),'confirm');
    assert.ok(dialog.message().startsWith('Сигурни ли сте?'), name + ': missing clear question');
    await dialog.dismiss();
  };
  page.on('dialog',listener);
  try { await action(); } finally { page.off('dialog',listener); }
  assert.equal(count,1,name + ': expected one confirmation before acting');
  assert.equal(await mutations(),before,name + ': cancellation wrote data or called a service');
  checked.push(name);
}
async function approve(action) {
  let count = 0;
  const listener = async dialog => { count++; await dialog.accept(); };
  page.on('dialog',listener);
  try { await action(); } finally { page.off('dialog',listener); }
  assert.equal(count,1,'accepted action must ask exactly once');
}
const row = () => page.locator('#rows > .row').first();
const success = () => row().locator('.msg[data-state=ok]').waitFor();
try {
  await page.goto(base+'/admin/');
  await page.locator('#app').waitFor();
  const catalogue = await page.evaluate(()=>fetch('/admin/catalogue.json').then(r=>r.json()));
  const key = catalogue.items[0].key;
  await page.evaluate(({key,album})=>{
    const photo={s:'products/test-600.webp',l:'products/test-1200.webp',w:1200,h:800};
    window.__db.product_overrides=[{product_key:key,price:123,images:[],excluded_images:[]}];
    window.__db.products=[{id:'test-product',section:'door',category:'test',name:'Тестова врата',price:150,images:[photo],sizes:[],hidden:false}];
    window.__db.project_photos=[{id:'test-photo',album,photo}];
    sessionStorage.setItem('ngdoors-test-db',JSON.stringify(window.__db));
  },{key,album:catalogue.albums[0]});
  await page.reload();
  await page.locator('[data-tab=catalogue]').click();
  const firstPhoto = () => row().getByRole('button',{name:'Изтрий снимка 1',exact:true});
  const count = await row().locator('.thumbs-edit img').count();
  await deny('delete original photograph',()=>firstPhoto().click());
  assert.equal(await row().locator('.thumbs-edit img').count(),count);
  await approve(()=>firstPhoto().click()); await success();
  assert.equal(await row().locator('.thumbs-edit img').count(),count-1);
  const restore=()=>row().getByRole('button',{name:'Върни каталожните снимки',exact:true});
  await deny('restore photographs',()=>restore().click());
  assert.equal(await row().locator('.thumbs-edit img').count(),count-1);
  await approve(()=>restore().click()); await success();
  await deny('reset all catalogue edits',()=>row().getByRole('button',{name:'Върни каталожните',exact:true}).click());
  await row().getByRole('textbox',{name:'Цена в евро',exact:true}).fill('222');
  await deny('toggle catalogue visibility',()=>row().locator('input[type=checkbox]').click());
  assert.equal(await row().locator('input[type=checkbox]').isChecked(),false);
  await approve(()=>row().locator('input[type=checkbox]').check());
  await deny('save catalogue price and hide flag',()=>row().getByRole('button',{name:'Запази',exact:true}).click());
  assert.equal(await row().getByRole('textbox',{name:'Цена в евро',exact:true}).inputValue(),'222');
  await row().locator('.size-editor summary').click();
  const sizes = await row().locator('.size-row').count();
  await deny('add draft size',()=>row().getByRole('button',{name:'+ Добави размер',exact:true}).click());
  assert.equal(await row().locator('.size-row').count(),sizes);
  await approve(()=>row().getByRole('button',{name:'+ Добави размер',exact:true}).click());
  await deny('remove draft size',()=>row().getByRole('button',{name:'Махни размера',exact:true}).last().click());
  assert.equal(await row().locator('.size-row').count(),sizes+1);
  await deny('restore catalogue sizes',()=>row().getByRole('button',{name:'Върни каталожните размери',exact:true}).click());
  assert.equal(await row().locator('.size-row').count(),sizes+1);
  const png=await page.evaluate(()=>{const c=document.createElement('canvas');c.width=32;c.height=48;return c.toDataURL('image/png').split(',')[1];});
  const file={name:'test.png',mimeType:'image/png',buffer:Buffer.from(png,'base64')};
  await deny('upload catalogue photograph',()=>row().locator('input[type=file]').setInputFiles(file));

  await page.locator('[data-tab=mine]').click();
  const hidden=page.locator('#mine-rows input[type=checkbox]').first();
  // click rather than check: Playwright check expects the checkbox to stay checked.
  await deny('hide own product',()=>hidden.click());
  assert.equal(await hidden.isChecked(),false);
  await approve(()=>hidden.click());
  await page.waitForFunction(()=>window.__db.products[0].hidden===true);
  await deny('show own product',()=>hidden.click());
  assert.equal(await hidden.isChecked(),true);
  await page.evaluate(()=>window.__failNextWrite=true);
  await approve(()=>hidden.click());
  await page.locator('#publish-bar[data-state=err]').waitFor();
  assert.equal(await hidden.isChecked(),true,'failed visibility save did not restore checkbox');
  assert.equal(await hidden.isEnabled(),true,'failed visibility save prevented retry');
  await page.locator('#mine-rows').getByRole('button',{name:'Редактирай'}).click();
  await page.locator('#pform input[name=name]').fill('Незапазено име');
  await deny('replace an open product form',()=>page.locator('#mine-rows').getByRole('button',{name:'Редактирай'}).click());
  assert.equal(await page.locator('#pform input[name=name]').inputValue(),'Незапазено име');
  await page.locator('#pform select[name=category]').selectOption({index:1});
  await deny('remove own product photograph',()=>page.locator('#pthumbs button').first().click());
  assert.equal(await page.locator('#pthumbs img').count(),1);
  await deny('upload own product photograph',()=>page.locator('#pfiles').setInputFiles(file));
  await deny('save own product',()=>page.locator('#pform button[type=submit]').click());
  await deny('discard own product edits',()=>page.locator('#pcancel').click());
  assert.equal(await page.locator('#pform').isVisible(),true);
  await deny('delete own product',()=>page.locator('#pdelete').click());
  await approve(()=>page.locator('#pcancel').click());
  await page.locator('#add-product').click();
  await page.locator('#pform input[name=name]').fill('Нова тестова врата');
  await page.locator('#pform select[name=category]').selectOption({index:1});
  await approve(()=>page.locator('#pfiles').setInputFiles(file));
  await page.locator('#pthumbs img').waitFor();
  await deny('create own product',()=>page.locator('#pform button[type=submit]').click());
  await approve(()=>page.locator('#pcancel').click());

  await page.locator('[data-tab=projects]').click();
  await deny('upload project photograph',()=>page.locator('#upfiles').setInputFiles(file));
  await deny('delete project photograph',()=>page.locator('#photos').getByRole('button',{name:'Изтрий',exact:true}).first().click());
  await approve(()=>page.locator('#photos').getByRole('button',{name:'Изтрий',exact:true}).first().click());
  await page.waitForFunction(()=>window.__db.project_photos.length===0);

  await page.locator('[data-tab=inbox]').click();
  await deny('mark inquiry done',()=>page.locator('#inbox').getByRole('button',{name:'Готово',exact:true}).first().click());
  await approve(()=>page.locator('#inbox').getByRole('button',{name:'Готово',exact:true}).first().click());
  await page.waitForFunction(()=>window.__db.inquiries[0].status==='done');
  await deny('reopen inquiry',()=>page.locator('#inbox').getByRole('button',{name:'Върни като ново',exact:true}).first().click());
  await deny('delete inquiry',()=>page.locator('#inbox').getByRole('button',{name:'Изтрий',exact:true}).first().click());
  await page.locator('[data-tab=settings]').click();
  await page.locator('#sform input[name=phone]').fill('+359888111222');
  await deny('save site settings',()=>page.locator('#sform button[type=submit]').click());
  await page.locator('#myform input[name=password]').fill('test-password-only');
  await deny('change account password',()=>page.locator('#myform button[type=submit]').click());
  await deny('publish website',()=>page.locator('#publish').click());
  assert.equal(await page.locator('#publish').isEnabled(),true);
  await approve(()=>page.locator('#publish').click());
  await page.waitForFunction(()=>window.__calls.some(c=>c.op==='invoke'&&c.name==='publish'));
  await deny('sign out',()=>page.locator('#logout').click());
  assert.equal(await page.locator('#app').isVisible(),true);
  await page.goto(base+'/admin/#type=recovery');
  await page.reload(); // A hash-only navigation does not rerun the recovery boot handler.
  await page.locator('#newpass input[name=password]').fill('test-password-only');
  await deny('save recovery password',()=>page.locator('#newpass button[type=submit]').click());
  assert.deepEqual(errors,[]);
  console.log('confirmation cancellation: PASS ('+checked.length+' actions; native dialogs; zero backend side effects on Cancel)');
  console.log(checked.join('\n'));
} finally {await browser.close(); server.close();}
