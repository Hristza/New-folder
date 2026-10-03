/* Test harness only, never deployed: a fake Supabase client so the admin panel can
   be driven in a real browser before the real project exists. Inject it as a
   pre-load script (chrome-devtools initScript). Every write lands in window.__db
   and every call is logged in window.__calls, so a test can assert what the panel
   actually sent. */
(function () {
  var db = window.__db = {
    admins: [{ user_id: 'u1' }],
    product_overrides: [], products: [], project_photos: [], settings: [], publish_log: [],
    inquiries: [
      { id: 'q1', name: 'Мария', contact: '+359 888 123 456', topic: 'Входна врата', message: 'Трябва ми врата 90/200.\nКога може замерване?', page: '/kontakti/', status: 'new', created_at: '2026-09-29T08:00:00Z' },
      { id: 'q2', name: 'Петър <script>alert(1)</script>', contact: 'petar@example.com', topic: 'Друго', message: '<img src=x onerror=alert(2)>', page: '/', status: 'done', created_at: '2026-09-28T08:00:00Z' }
    ]
  };
  var saved = sessionStorage.getItem('ngdoors-test-db');
  if (saved) Object.assign(db, JSON.parse(saved));
  var calls = window.__calls = [], authChanged;
  var n = 0;
  function Q(table) { this.t = table; this.op = 'select'; this.f = []; this.payload = null; this.single = false; }
  Q.prototype.select = function () { return this; };
  Q.prototype.eq = function (k, v) { this.f.push(function (r) { return r[k] === v; }); return this; };
  Q.prototype.in = function (k, vs) { this.f.push(function (r) { return vs.indexOf(r[k]) >= 0; }); return this; };
  Q.prototype.order = function () { return this; };
  Q.prototype.limit = function () { return this; };
  Q.prototype.maybeSingle = function () { this.single = true; return this; };
  ['insert', 'upsert', 'update', 'delete'].forEach(function (op) {
    Q.prototype[op] = function (p) { this.op = op; this.payload = p; return this; };
  });
  Q.prototype.then = function (ok, bad) {
    var t = this.t, rows = db[t], f = this.f, match = function (r) { return f.every(function (fn) { return fn(r); }); };
    calls.push({ table: t, op: this.op, payload: this.payload });
    var out;
    if (this.op === 'select') out = rows.filter(match);
    else if (this.op === 'insert' || this.op === 'upsert') {
      out = [].concat(this.payload).map(function (p) {
        var key = t === 'product_overrides' ? 'product_key' : t === 'settings' ? 'key' : 'id';
        var row = Object.assign({ id: 'id' + (++n), created_at: new Date().toISOString() }, p);
        var i = rows.findIndex(function (r) { return r[key] === row[key]; });
        if (i >= 0) rows[i] = Object.assign(rows[i], p); else rows.push(row);
        return i >= 0 ? rows[i] : row;
      });
    } else if (this.op === 'update') {
      out = rows.filter(match); var p = this.payload; out.forEach(function (r) { Object.assign(r, p); });
    } else { out = rows.filter(match); db[t] = rows.filter(function (r) { return !match(r); }); }
    sessionStorage.setItem('ngdoors-test-db', JSON.stringify(db));
    return Promise.resolve({ data: this.single ? (out[0] || null) : out, error: null }).then(ok, bad);
  };
  var client = {
    auth: {
      onAuthStateChange: function (fn) { authChanged = fn; },
      getSession: function () { return Promise.resolve({ data: { session: window.__signedOut ? null : { user: { id: 'u1' } } } }); },
      signOut: function () { calls.push({ op: 'signOut' }); window.__signedOut = true; if (authChanged) authChanged('SIGNED_OUT'); return Promise.resolve({}); },
      signInWithOtp: function (p) { calls.push({ op: 'signInWithOtp', options: p.options }); return Promise.resolve({ error: null }); },
      updateUser: function () { calls.push({ op: 'updateUser' }); return Promise.resolve({ error: null }); },
      signInWithPassword: function (p) {
        if (p.password !== 'test-password-only') return Promise.resolve({ error: { message: 'wrong password' } });
        window.__signedOut = false;
        return Promise.resolve({ data: { session: { user: { id: 'u1' } } } });
      }
    },
    from: function (t) { return new Q(t); },
    storage: { from: function () { return {
      getPublicUrl: function (p) { return { data: { publicUrl: '/assets/photos/mostri-640.webp#' + p } }; },
      upload: function (p, blob) { calls.push({ op: 'upload', path: p, type: blob.type, size: blob.size }); return Promise.resolve({ error: null }); },
      remove: function (ps) { calls.push({ op: 'remove', paths: ps }); return Promise.resolve({}); }
    }; } },
    functions: { invoke: function (name) { calls.push({ op: 'invoke', name: name }); return Promise.resolve({ data: { ok: true }, error: null }); } }
  };
  Object.defineProperty(window, 'supabase', { configurable: false, get: function () { return { createClient: function () { return client; } }; }, set: function () {} });
  var realFetch = window.fetch;
  window.fetch = function (u, o) {
    return realFetch(u, o).then(function (r) {
      if (String(u).indexOf('/admin/catalogue.json') < 0) return r;
      return r.json().then(function (j) {
        j.supabase_url = 'https://mock.supabase.co'; j.supabase_key = 'mock';
        return new Response(JSON.stringify(j), { headers: { 'Content-Type': 'application/json' } });
      });
    });
  };
})();
