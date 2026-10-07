// Real browser + real built pages, with an explicitly mocked Supabase service.
// Database constraints and permissions are tested separately by test_schema.mjs.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import http from 'node:http';
import { readFileSync, mkdirSync } from 'node:fs';
import { resolve, extname, sep } from 'node:path';

const root = resolve('site'), proof = resolve('verification');
mkdirSync(proof, { recursive: true });
const server = http.createServer((req, res) => {
  let name = decodeURIComponent(req.url.split('?')[0]);
  if (name.endsWith('/')) name += 'index.html';
  const file = resolve(root, '.' + name);
  if (!file.startsWith(root + sep)) { res.writeHead(403).end(); return; }
  try {
    const type = {'.html':'text/html','.js':'text/javascript','.json':'application/json','.css':'text/css','.webp':'image/webp','.svg':'image/svg+xml'}[extname(file)];
    res.writeHead(200, {'Content-Type': type || 'application/octet-stream'}).end(readFileSync(file));
  } catch { res.writeHead(404).end(); }
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const base = 'http://127.0.0.1:' + server.address().port;
const browser = await chromium.launch({headless:true,
  executablePath:process.env.BRAVE_PATH || (process.platform === 'win32' ? 'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe' : undefined)});
const context = await browser.newContext({viewport:{width:390,height:844}});
await context.addInitScript({content:readFileSync('supabase/admin_mock.js','utf8')});
const page = await context.newPage(), errors = [];
page.on('pageerror', e => errors.push(e.message));
try {
  await page.goto(base + '/admin/');
  await page.locator('#app').waitFor();
  await page.locator('[data-tab=catalogue]').click();
  let row = page.locator('#rows > .row').first();
  const key = (await page.evaluate(() => fetch('/admin/catalogue.json').then(r=>r.json()))).items[0].key;
  const originalPhotos = (await page.evaluate(() => fetch('/admin/catalogue.json').then(r=>r.json()))).items[0].images;
  assert.ok(originalPhotos.length > 1, 'fixture must exercise individual gallery removal');
  assert.equal(await row.locator('.thumbs-edit button').count(),originalPhotos.length);
  // Failed saves must retain photos and give a usable retry.
  await row.getByRole('textbox',{name:'Цена в евро',exact:true}).fill('123,45');
  await page.evaluate(()=>window.__failNextWrite=true);
  await row.getByRole('button',{name:'Изтрий снимка 1',exact:true}).click();
  await row.locator('.msg[data-state=err]').waitFor();
  assert.equal(await row.locator('.thumbs-edit button').count(),originalPhotos.length);
  assert.equal(await row.getByRole('button',{name:'Изтрий снимка 1',exact:true}).isEnabled(),true);
  assert.equal(await page.evaluate(()=>window.__calls.filter(c=>c.op==='remove').length),0,'original assets must never be deleted from storage');
  await row.getByRole('button',{name:'Изтрий снимка 1',exact:true}).click();
  await row.locator('.msg[data-state=ok]').waitFor();
  assert.equal(await row.getByRole('textbox',{name:'Цена в евро',exact:true}).inputValue(),'123,45','photo edit discarded unsaved price');
  assert.equal(await row.locator('.thumbs-edit button').count(),originalPhotos.length-1);
  assert.deepEqual(await page.evaluate(k=>window.__db.product_overrides.find(r=>r.product_key===k).excluded_images,key),[originalPhotos[0].id]);
  assert.equal(await row.locator(':scope > img').getAttribute('src'),originalPhotos[1].thumb);
  await page.reload();
  await page.locator('[data-tab=catalogue]').click();
  row = page.locator('#rows > .row').first();
  assert.equal(await row.locator('.thumbs-edit button').count(),originalPhotos.length-1,'deleted original returned after reload');
  while(await row.locator('.thumbs-edit button').count()) {
    await row.locator('.thumbs-edit button').first().click();
    await row.locator('.msg[data-state=ok]').waitFor();
  }
  assert.equal(await row.locator(':scope > img').getAttribute('src'),'/assets/no-photo.svg');
  assert.match(await row.locator('.thumbs-edit').textContent(),/Продуктът остава видим/);
  await page.reload();
  await page.locator('[data-tab=catalogue]').click();
  row = page.locator('#rows > .row').first();
  assert.equal(await row.locator('.thumbs-edit button').count(),0,'last original returned after reload');
  assert.ok(await page.locator('#rows > .row').nth(1).locator('.thumbs-edit button').count(),'another product lost its photos');
  await row.getByRole('button',{name:'Върни каталожните снимки',exact:true}).click();
  await row.locator('.msg[data-state=ok]').waitFor();
  assert.equal(await row.locator('.thumbs-edit button').count(),originalPhotos.length);
  assert.equal(await page.evaluate(()=>window.__calls.filter(c=>c.op==='remove').length),0);
  for(const width of [390,768,1440]) {
    await page.setViewportSize({width,height:1000});
    await row.locator('.thumbs-edit button').first().focus();
    await page.screenshot({path:resolve(proof,'admin-photo-delete-'+width+'.png'),fullPage:false});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'photo panel overflows at '+width);
    assert.equal(await row.locator('.thumbs-edit img').evaluateAll(imgs=>imgs.every(i=>i.complete&&i.naturalWidth>0)),true,'original thumbnail is broken');
  }
  await page.setViewportSize({width:390,height:844});
  await row.locator('.size-editor summary').click();
  while (await row.locator('.size-row').count()) await row.getByRole('button',{name:'Махни размера',exact:true}).first().click();
  for (const [size, price] of [['91 × 213','245,50'],['101 × 223','307,01'],['По размер на клиента','0']]) {
    await row.getByRole('button',{name:'+ Добави размер',exact:true}).click();
    const entry = row.locator('.size-row').last();
    await entry.getByRole('textbox',{name:'Размер',exact:true}).fill(size);
    await entry.getByRole('textbox',{name:'Цена за размера в евро',exact:true}).fill(price);
  }
  await row.getByRole('button',{name:'Запази',exact:true}).click();
  await row.locator('.msg[data-state=ok]').waitFor();
  assert.deepEqual(await page.evaluate(k=>window.__db.product_overrides.find(r=>r.product_key===k).size_prices,key),[
    {size:'91 × 213',price:245.50},{size:'101 × 223',price:307.01},{size:'По размер на клиента',price:0}]);
  await page.reload();
  await page.locator('[data-tab=catalogue]').click();
  row = page.locator('#rows > .row').first();
  await row.locator('.size-editor summary').click();
  assert.equal(await row.locator('.size-row').count(),3);
  assert.equal(await row.locator('.size-row').nth(1).getByRole('textbox',{name:'Цена за размера в евро',exact:true}).inputValue(),'307,01');
  const writes = await page.evaluate(()=>window.__calls.filter(c=>c.op==='upsert').length);
  await row.locator('.size-row').nth(1).getByRole('textbox',{name:'Размер',exact:true}).fill('91 × 213');
  await row.getByRole('button',{name:'Запази',exact:true}).click();
  await row.locator('.msg[data-state=err]').waitFor();
  assert.equal(await page.evaluate(()=>window.__calls.filter(c=>c.op==='upsert').length),writes);
  await row.locator('.size-row').nth(1).getByRole('textbox',{name:'Размер',exact:true}).fill('101 × 223');
  await row.locator('.size-row').first().getByRole('textbox',{name:'Размер',exact:true}).fill('93 × 214');
  const png = await page.evaluate(()=>{const c=document.createElement('canvas');c.width=80;c.height=120;c.getContext('2d').fillRect(0,0,80,120);return c.toDataURL('image/png').split(',')[1];});
  await row.locator('input[type=file]').setInputFiles({name:'test-photo.png',mimeType:'image/png',buffer:Buffer.from(png,'base64')});
  await page.waitForFunction(k=>window.__db.product_overrides.find(r=>r.product_key===k)?.images?.length===1,key);
  assert.equal(await row.locator('.thumbs-edit button').count(),1);
  assert.equal(await row.locator('.size-row').first().getByRole('textbox',{name:'Размер',exact:true}).inputValue(),'93 × 214','upload discarded unsaved size edits');
  await row.getByRole('button',{name:'Запази',exact:true}).click();
  await row.locator('.msg[data-state=ok]').waitFor();
  await page.screenshot({path:resolve(proof,'admin-sizes-390.png'),fullPage:false});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'mobile panel overflows');
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:resolve(proof,'admin-sizes-1440.png'),fullPage:false});
  await row.getByRole('button',{name:'Изтрий снимка 1',exact:true}).click();
  await row.locator('.msg[data-state=ok]').waitFor();
  assert.equal(await row.locator('.thumbs-edit button').count(),0,'deleting the last upload silently restored originals');
  assert.equal(await page.evaluate(k=>window.__db.product_overrides.find(r=>r.product_key===k).size_prices[0].size,key),'93 × 214','photo deletion lost saved sizes');
  assert.equal(await page.evaluate(()=>window.__calls.filter(c=>c.op==='remove').length),1,'uploaded copies were not removed');
  await row.getByRole('button',{name:'Върни каталожните снимки',exact:true}).click();
  await row.locator('.msg[data-state=ok]').waitFor();
  assert.equal(await row.locator('.thumbs-edit button').count(),originalPhotos.length);
  await page.locator('[data-tab=mine]').click();
  await page.locator('#add-product').click();
  await page.locator('#pform input[name=name]').fill('Тестова врата Тау');
  await page.locator('#pform select[name=category]').selectOption({index:1});
  await page.locator('#pform input[name=price]').fill('150');
  for (const [size,price] of [['82/205','150,01'],['92/215','187,99']]) {
    await page.locator('#psizes').getByRole('button',{name:'+ Добави размер',exact:true}).click();
    const entry=page.locator('#psizes .size-row').last();
    await entry.getByRole('textbox',{name:'Размер',exact:true}).fill(size);
    await entry.getByRole('textbox',{name:'Цена за размера в евро',exact:true}).fill(price);
  }
  await page.locator('#pfiles').setInputFiles({name:'test-photo.png',mimeType:'image/png',buffer:Buffer.from(png,'base64')});
  await page.locator('#pthumbs figure').waitFor();
  await page.locator('#pform').getByRole('button',{name:'Запази',exact:true}).click();
  await page.locator('#pform').waitFor({state:'hidden'});
  assert.deepEqual(await page.evaluate(()=>window.__db.products[0].size_prices),[{size:'82/205',price:150.01},{size:'92/215',price:187.99}]);
  await page.locator('#mine-rows').getByRole('button',{name:'Редактирай'}).first().click();
  assert.equal(await page.locator('#psizes .size-row').count(),2);
  await page.locator('#pcancel').click();
  await page.locator('[data-tab=settings]').click();
  await page.locator('#sform input[name=phone]').fill('+359 888 111 222');
  await page.locator('#sform button[type=submit]').click();
  await page.locator('#smsg[data-state=ok]').waitFor();
  await page.locator('#logout').click();
  await page.locator('#gate').waitFor();
  await page.locator('#login input[name=email]').fill('owner@example.com');
  await page.locator('#login input[name=password]').fill('incorrect-control');
  await page.locator('#login button[type=submit]').click();
  await page.locator('#gate-msg[data-state=err]').waitFor();
  assert.equal(await page.locator('#app').isVisible(),false);
  await page.locator('#login input[name=password]').fill('');
  await page.locator('#login button[type=submit]').click();
  await page.locator('#gate-msg[data-state=ok]').waitFor();
  assert.equal(await page.evaluate(()=>window.__calls.find(c=>c.op==='signInWithOtp').options.shouldCreateUser),false);
  await page.locator('#login input[name=password]').fill('test-password-only');
  await page.locator('#login button[type=submit]').click();
  await page.locator('#app').waitFor();

  // The actual built product, with custom prices from test_build_admin.py.
  const catalogue=JSON.parse(readFileSync('site/admin/catalogue.json','utf8'));
  const emptyProduct=catalogue.items.find(i=>{
    try { return readFileSync(resolve(root,'.'+i.url,'index.html'),'utf8').includes('src="/assets/no-photo.svg"'); }
    catch { return false; }
  });
  assert.ok(emptyProduct,'fixture must include a product whose last photograph was deleted');
  await page.goto(base + emptyProduct.url);
  const emptyImage=page.locator('.gallery-main img');
  assert.equal(await emptyImage.getAttribute('src'),'/assets/no-photo.svg');
  assert.equal(await emptyImage.evaluate(i=>i.complete&&i.naturalWidth>0),true);
  assert.ok(await page.locator('h1').isVisible(),'photo removal hid the product');
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:resolve(proof,'product-no-photo-390.png'),fullPage:false,animations:'disabled'});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'empty-photo product overflows');
  const product=catalogue.items.find(i=>i.key==='door:1635');
  await page.goto(base + product.url);
  const pills=page.locator('.size-pill'), amount=page.locator('.price-big');
  assert.equal(await pills.count(),3);
  assert.equal((await amount.textContent()).trim(),'По запитване');
  await pills.nth(0).click();
  assert.equal(await amount.locator('.eur').textContent(),'245,50 €');
  assert.equal(await amount.locator('.was').textContent(),'300,00 €');
  assert.match(decodeURIComponent(await page.locator('.product-cta a[href^="mailto:"]').getAttribute('href')),/91 × 213/);
  await pills.nth(1).click();
  assert.equal(await amount.locator('.eur').textContent(),'307,01 €');
  assert.equal(await amount.locator('.was').count(),0,'sale shown above old price');
  await pills.nth(1).focus(); await page.keyboard.press('ArrowRight');
  assert.equal((await amount.textContent()).trim(),'По запитване');
  await page.setViewportSize({width:390,height:844});
  await pills.nth(0).click();
  await page.screenshot({path:resolve(proof,'product-sizes-390.png'),fullPage:false});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'product overflows');
  assert.deepEqual(errors,[]);
  console.log('admin + public UI: PASS (individual originals, last photo, restore, failed save, upload deletion, reloads; mock service, real Brave browser)');
} finally { await browser.close(); server.close(); }
