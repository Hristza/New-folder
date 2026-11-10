/* Test harness only, never deployed: a fake ngdoors-api (worker.js) so the admin panel
   can be driven in a real browser without touching the live database. Inject it as a
   pre-load script (Playwright addInitScript). Every write lands in window.__db and
   every call is logged in window.__calls, so a test can assert what the panel sent.
   The real Worker's rules are tested by api/test_api.mjs. */
(function () {
  var API = 'https://mock.api';
  var db = window.__db = {
    product_overrides: [], products: [], project_photos: [], settings: [], publish_log: [],
    inquiries: [
      { id: 'q1', name: 'Мария', contact: '+359 888 123 456', topic: 'Входна врата', message: 'Трябва ми врата 90/200.\nКога може замерване?', page: '/kontakti/', status: 'new', created_at: '2026-09-29T08:00:00Z' },
      { id: 'q2', name: 'Петър <script>alert(1)</script>', contact: 'petar@example.com', topic: 'Друго', message: '<img src=x onerror=alert(2)>', page: '/', status: 'done', created_at: '2026-09-28T08:00:00Z' }
    ]
  };
  var saved = sessionStorage.getItem('ngdoors-test-db');
  if (saved) Object.assign(db, JSON.parse(saved));
  var calls = window.__calls = [], n = 0;
  try { localStorage.setItem('ngdoors-admin-token', 'mock-session'); } catch (e) {}

  function json(status, body) {
    return Promise.resolve(new Response(JSON.stringify(body), { status: status, headers: { 'Content-Type': 'application/json' } }));
  }
  function persist() { sessionStorage.setItem('ngdoors-test-db', JSON.stringify(db)); }
  function find(t, k, v) { return db[t].find(function (r) { return r[k] === v; }); }
  function write(t, op, payload, fn) {
    calls.push({ table: t, op: op, payload: payload });
    if (window.__failNextWrite) { window.__failNextWrite = false; return json(400, { error: 'Test save rejected' }); }
    var out = fn(); persist(); return json(200, out);
  }

  function handle(path, method, body, headers) {
    var seg = path.split('/').filter(Boolean).map(decodeURIComponent), id = seg[2];
    if (path === '/auth/login') {
      if (body.password !== 'test-password-only') return json(401, { error: 'Грешен имейл или парола.' });
      window.__signedOut = false; return json(200, { token: 'mock-session', email: body.email });
    }
    if (path === '/auth/reset') { calls.push({ op: 'reset', email: body.email }); return json(200, { ok: true }); }
    if (path === '/auth/password') { calls.push({ op: 'updateUser', reset: !!body.token }); return json(200, body.token ? { token: 'mock-session', email: 'owner@example.com' } : { ok: true }); }
    if (path === '/auth/logout') { calls.push({ op: 'signOut' }); window.__signedOut = true; return json(200, { ok: true }); }
    if (seg[0] !== 'admin') return json(404, { error: 'not found' });
    if (window.__signedOut) return json(401, { error: 'Влезте отново.' });
    var what = seg[1];
    if (what === 'me') return json(200, { email: 'owner@example.com' });
    if (what === 'data') {
      return json(200, { overrides: db.product_overrides, products: db.products, photos: db.project_photos,
        inquiries: db.inquiries, settings: db.settings, lastPublish: db.publish_log[db.publish_log.length - 1] || null });
    }
    if (what === 'overrides') {
      if (method === 'DELETE') return write('product_overrides', 'delete', { product_key: id }, function () {
        db.product_overrides = db.product_overrides.filter(function (r) { return r.product_key !== id; }); return { ok: true };
      });
      return write('product_overrides', 'upsert', Object.assign({ product_key: id }, body), function () {
        var row = find('product_overrides', 'product_key', id);
        if (!row) { row = { product_key: id, images: [], excluded_images: [], hidden: false }; db.product_overrides.push(row); }
        return Object.assign(row, body);
      });
    }
    if (what === 'products') {
      if (method === 'POST') return write('products', 'insert', body, function () {
        var row = Object.assign({ id: 'id' + (++n), created_at: new Date().toISOString(), hidden: false }, body);
        db.products.unshift(row); return row;
      });
      if (method === 'PATCH') return write('products', 'update', body, function () { return Object.assign(find('products', 'id', id), body); });
      return write('products', 'delete', { id: id }, function () { db.products = db.products.filter(function (r) { return r.id !== id; }); return { ok: true }; });
    }
    if (what === 'photos') {
      if (method === 'POST') return write('project_photos', 'insert', body, function () {
        var row = Object.assign({ id: 'id' + (++n), created_at: new Date().toISOString() }, body);
        db.project_photos.unshift(row); return row;
      });
      return write('project_photos', 'delete', { id: id }, function () { db.project_photos = db.project_photos.filter(function (r) { return r.id !== id; }); return { ok: true }; });
    }
    if (what === 'inquiries') {
      if (method === 'PATCH') return write('inquiries', 'update', body, function () { return Object.assign(find('inquiries', 'id', id), body); });
      return write('inquiries', 'delete', { id: id }, function () { db.inquiries = db.inquiries.filter(function (r) { return r.id !== id; }); return { ok: true }; });
    }
    if (what === 'settings') return write('settings', 'upsert', body, function () {
      db.settings = db.settings.filter(function (s) { return !(s.key in body.set) && body.del.indexOf(s.key) < 0; })
        .concat(Object.keys(body.set).map(function (k) { return { key: k, value: body.set[k] }; }));
      return { ok: true };
    });
    if (what === 'media' && method === 'PUT') {
      calls.push({ op: 'upload', path: seg.slice(2).join('/'), type: headers['Content-Type'], size: body.size });
      return json(200, { ok: true });
    }
    if (what === 'media') { calls.push({ op: 'remove', paths: body.paths }); return json(200, { ok: true }); }
    if (what === 'publish') {
      calls.push({ op: 'invoke', name: 'publish' });
      db.publish_log.push({ requested_at: new Date().toISOString(), ok: true }); persist();
      return json(200, { ok: true });
    }
    return json(404, { error: 'not found' });
  }

  var realFetch = window.fetch;
  window.fetch = function (u, o) {
    o = o || {};
    var url = String(u);
    if (url.indexOf(API) === 0) {
      var body = o.body;
      if (typeof body === 'string') body = JSON.parse(body);
      return handle(url.slice(API.length), o.method || 'GET', body || {}, o.headers || {});
    }
    return realFetch(u, o).then(function (r) {
      if (url.indexOf('/admin/catalogue.json') < 0) return r;
      return r.json().then(function (j) {
        j.api_url = API;
        return new Response(JSON.stringify(j), { headers: { 'Content-Type': 'application/json' } });
      });
    });
  };
})();
