/* NG Doors admin panel.
   Everything is saved straight to Supabase under her login; row-level security on
   the server decides what she may do, never this file. The public site changes only
   when she presses "Публикувай", which rebuilds it from what is saved here.
   Every value that came from the database goes into the page with textContent,
   never innerHTML. */
(function () {
  'use strict';

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return [].slice.call((r || document).querySelectorAll(s)); };

  // h('div.cls', {attr}, child, ...) -> element. Strings become text nodes.
  function h(tag, attrs) {
    var parts = tag.split('.'), el = document.createElement(parts[0]);
    if (parts.length > 1) el.className = parts.slice(1).join(' ');
    for (var k in (attrs || {})) {
      var v = attrs[k];
      if (v == null || v === false) continue;
      if (k.slice(0, 2) === 'on') el.addEventListener(k.slice(2), v);
      else if (k in el && k !== 'list' && typeof v !== 'string') el[k] = v;
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c == null || c === false) continue;
      [].concat(c).forEach(function (x) {
        if (x != null && x !== false) el.appendChild(typeof x === 'string' || typeof x === 'number' ? document.createTextNode(String(x)) : x);
      });
    }
    return el;
  }
  function say(el, state, text) { el.setAttribute('data-state', state || ''); el.textContent = text || ''; }
  // Ask before the first side effect, including uploads and unsaved destructive edits.
  // Browser confirmation blocks the action; Cancel/Escape leaves the current state intact.
  function confirmChange(action) { return window.confirm('Сигурни ли сте?\n\n' + action); }

  var CAT = null, sb = null, RATE = 1.95583;
  var state = { overrides: {}, products: [], photos: [], inbox: [], settings: {} };

  /* ---------------------------------------------------------------- money
     She types euro and her euro is stored exactly as typed. Converting to leva on
     save and back on load lost a cent (250,50 -> 489,94 лв -> 250,51). The catalogue
     file still carries leva, so only catalogue values go through toEur. */
  function toEur(bgn) { return bgn == null ? '' : (Math.round(bgn / RATE * 100) / 100).toFixed(2).replace('.', ','); }
  function eur(e) { return e == null ? '' : Number(e).toFixed(2).replace('.', ','); }
  function fmtE(e) { return e > 0 ? eur(e) + ' €' : 'По запитване'; }
  function parseEur(s) {
    s = String(s == null ? '' : s).trim().replace(/\s/g, '').replace(',', '.');
    if (s === '') return null;
    if (!/^\d{1,6}(\.\d{1,2})?$/.test(s)) return NaN;
    return parseFloat(s);
  }
  function fmtEur(bgn) { return bgn > 0 ? toEur(bgn) + ' €' : 'По запитване'; }

  // The same size editor serves catalogue doors and her own products.
  function sizeEditor(rows, inherit, defaults) {
    var inherited = inherit, list = h('div.size-rows'), add;
    var box = h('details.size-editor', null,
      h('summary', null, 'Размери и цени'),
      h('p.sub', null, 'Всеки размер има своя цена в евро. Сайтът показва цената на избрания размер. 0 = По запитване. До 30 размера.'), list);
    function draw(values) {
      list.replaceChildren();
      values.forEach(function (v) { append(v); });
      if (add) add.disabled = list.children.length >= 30;
    }
    function append(v) {
      var size = h('input', { value: v.size || '', maxlength: 80, 'aria-label': 'Размер', placeholder: '90 × 210 см' });
      var price = h('input', { value: v.price == null ? '' : eur(v.price), inputmode: 'decimal', 'aria-label': 'Цена за размера в евро', placeholder: '245,50' });
      var row = h('div.size-row', null,
        h('label.field', null, h('span', null, 'Размер'), size),
        h('label.field', null, h('span', null, 'Цена, €'), price),
        h('button.btn.btn-ghost.btn-sm', { type: 'button', 'aria-label': 'Махни размера', onclick: function () {
          if (!confirmChange('Да премахнем този размер от списъка? Промяната ще се запише с „Запази“.')) return;
          inherited = false; row.remove(); add.disabled = false;
        } }, '×'));
      [size, price].forEach(function (input) { input.addEventListener('input', function () { inherited = false; }); });
      list.appendChild(row);
    }
    add = h('button.btn.btn-ghost.btn-sm', { type: 'button', onclick: function () {
      if (list.children.length >= 30) return;
      if (!confirmChange('Да добавим нов размер към списъка?')) return;
      inherited = false; append({}); add.disabled = list.children.length >= 30;
      $('input', list.lastElementChild).focus();
    } }, '+ Добави размер');
    box.appendChild(h('div.actions', null, add, defaults ? h('button.btn.btn-ghost.btn-sm', { type: 'button', onclick: function () {
      if (!confirmChange('Да върнем каталожните размери? Въведените тук размери и цени ще бъдат заменени.')) return;
      inherited = true; draw(defaults());
    } }, 'Върни каталожните размери') : null));
    draw(rows || []);
    return { element: box, refresh: function (values) { if (inherited) draw(values); }, value: function () {
      if (inherited) return null;
      var seen = [], values = [];
      $$('.size-row', list).forEach(function (row) {
        var inputs = $$('input', row), size = inputs[0].value.trim(), amount = parseEur(inputs[1].value);
        if (!size || size.length > 80 || /[\x00-\x1f\x7f]/.test(size)) throw new Error('Напишете размер на всеки ред.');
        if (seen.indexOf(size.toLowerCase()) >= 0) throw new Error('Всеки размер трябва да е различен.');
        if (amount == null || Number.isNaN(amount)) throw new Error('Напишете цена за всеки размер, напр. 245,50.');
        seen.push(size.toLowerCase()); values.push({ size: size, price: amount });
      });
      return values;
    } };
  }

  /* ---------------------------------------------------------------- boot */
  fetch('/admin/catalogue.json', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (c) {
    CAT = c; RATE = c.bgn_per_eur || RATE;
    $('#boot').hidden = true;
    if (!c.supabase_url || !c.supabase_key || !window.supabase) {
      $('#gate').hidden = false;
      $('#login').hidden = true;
      say($('#gate-msg'), 'err', 'Панелът още не е свързан със сървъра.');
      return;
    }
    var recovering = location.hash.indexOf('type=recovery') >= 0;   // read before the library clears the hash
    sb = window.supabase.createClient(c.supabase_url, c.supabase_key, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true }
    });
    sb.auth.onAuthStateChange(function (ev, session) {
      if (ev === 'PASSWORD_RECOVERY') { showGate('newpass'); return; }
      if (ev === 'SIGNED_OUT') showGate('login');
    });
    sb.auth.getSession().then(function (r) {
      if (recovering) { showGate('newpass'); return; }   // email link: choose a password first
      if (r.data.session) enter(r.data.session); else showGate('login');
    });
  }).catch(function () {
    $('#boot').textContent = 'Панелът не можа да се зареди. Опреснете страницата.';
  });

  function showGate(which) {
    $('#app').hidden = true; $('#gate').hidden = false;
    $('#login').hidden = which !== 'login'; $('#newpass').hidden = which !== 'newpass';
  }

  // Password if she set one in Settings, else an email link. The link alone hit the 2-emails-an-hour cap.
  // shouldCreateUser:false so strangers get no account.
  $('#login').addEventListener('submit', function (e) {
    e.preventDefault();
    var f = e.target, btn = $('button[type=submit]', f), msg = $('#gate-msg');
    btn.disabled = true;
    if (f.password.value) {
      say(msg, '', 'Влизане…');
      sb.auth.signInWithPassword({ email: f.email.value.trim(), password: f.password.value }).then(function (r) {
        btn.disabled = false;
        if (r.error) { say(msg, 'err', 'Грешен имейл или парола. Нямате парола? Оставете полето празно.'); return; }
        say(msg, '', ''); enter(r.data.session);
      });
      return;
    }
    say(msg, '', 'Изпращане…');
    sb.auth.signInWithOtp({ email: f.email.value.trim(), options: { shouldCreateUser: false, emailRedirectTo: location.origin + '/admin/' } }).then(function (r) {
      btn.disabled = false;
      if (r.error && /signups not allowed|not found/i.test(r.error.message)) { say(msg, 'err', 'Този имейл няма достъп до панела.'); return; }
      if (r.error) { say(msg, 'err', 'Писмото не беше изпратено. Опитайте пак след минута.'); return; }
      say(msg, 'ok', 'Готово. Проверете пощата си и отворете връзката от писмото.');
    });
  });
  $('#newpass').addEventListener('submit', function (e) {
    e.preventDefault();
    if (!confirmChange('Да запазим новата парола за достъп до панела?')) return;
    var msg = $('#gate-msg');
    sb.auth.updateUser({ password: e.target.password.value }).then(function (r) {
      if (r.error) { say(msg, 'err', 'Паролата не беше сменена: ' + r.error.message); return; }
      history.replaceState(null, '', '/admin/');
      say(msg, 'ok', 'Паролата е сменена.');
      sb.auth.getSession().then(function (s) { enter(s.data.session); });
    });
  });
  $('#logout').addEventListener('click', function () {
    if (confirmChange('Да излезем от панела? Незапазените промени ще се загубят.')) sb.auth.signOut();
  });
  $('#myform').addEventListener('submit', function (e) {
    e.preventDefault();
    if (!confirmChange('Да сменим паролата за достъп до панела?')) return;
    var f = e.target, msg = $('#mymsg');
    say(msg, '', 'Запазване…');
    sb.auth.updateUser({ password: f.password.value }).then(function (r) {
      if (r.error) { say(msg, 'err', 'Паролата не е запазена: ' + r.error.message); return; }
      f.reset(); say(msg, 'ok', 'Паролата е запазена. Следващия път влезте с имейл и парола.');
    });
  });

  function enter(session) {
    // RLS lets a user read only their own admins row, so this is "am I an admin?".
    sb.from('admins').select('user_id').eq('user_id', session.user.id).maybeSingle().then(function (r) {
      if (r.error || !r.data) {
        showGate('login');
        say($('#gate-msg'), 'err', 'Този профил няма достъп до управлението.');
        sb.auth.signOut();
        return;
      }
      $('#gate').hidden = true; $('#app').hidden = false;
      loadAll();
    });
  }

  /* ---------------------------------------------------------------- tabs */
  $$('.tabs [role=tab]').forEach(function (t) {
    t.addEventListener('click', function () { openTab(t.getAttribute('data-tab')); });
  });
  function openTab(name) {
    $$('.tabs [role=tab]').forEach(function (t) { t.setAttribute('aria-selected', String(t.getAttribute('data-tab') === name)); });
    $$('[data-panel]').forEach(function (p) { p.hidden = p.getAttribute('data-panel') !== name; });
    window.scrollTo(0, 0);
  }

  /* ---------------------------------------------------------------- data */
  function all(q) { return q.then(function (r) { if (r.error) throw r.error; return r.data; }); }
  function loadAll() {
    return Promise.all([
      all(sb.from('product_overrides').select('*')),
      all(sb.from('products').select('*').order('created_at', { ascending: false })),
      all(sb.from('project_photos').select('*').order('created_at', { ascending: false })),
      all(sb.from('inquiries').select('*').order('created_at', { ascending: false }).limit(300)),
      all(sb.from('settings').select('key,value')),
      all(sb.from('publish_log').select('*').order('requested_at', { ascending: false }).limit(1))
    ]).then(function (d) {
      state.overrides = {}; d[0].forEach(function (o) { state.overrides[o.product_key] = o; });
      state.products = d[1]; state.photos = d[2]; state.inbox = d[3];
      state.settings = {}; d[4].forEach(function (s) { state.settings[s.key] = s.value; });
      state.lastPublish = d[5][0] || null;
      renderHome(); renderCatalogue(true); renderMine(); renderAlbums(); renderPhotos(); renderInbox(); renderSettings();
    }).catch(function (e) {
      say($('#publish-bar'), 'err', 'Данните не се заредиха: ' + (e.message || e) + '. Опреснете страницата.');
    });
  }

  /* ---------------------------------------------------------------- home */
  function renderHome() {
    var ov = Object.keys(state.overrides).map(function (k) { return state.overrides[k]; });
    var fresh = state.inbox.filter(function (i) { return i.status === 'new'; }).length;
    // Bulgarian counts: "1 ново запитване", "2 нови запитвания". "1 нови" is the tell of a template.
    var stat = function (n, one, many) { return h('div.stat', null, h('b', null, String(n)), h('span', null, n === 1 ? one : many)); };
    $('#stats').replaceChildren(
      stat(fresh, 'ново запитване', 'нови запитвания'),
      stat(ov.filter(function (o) { return o.price != null || o.size_prices != null; }).length, 'променена цена', 'променени цени'),
      stat(ov.filter(function (o) { return o.hidden; }).length, 'скрит модел', 'скрити модела'),
      stat(state.products.length, 'мой продукт', 'мои продукта'),
      stat(state.photos.length, 'снимка от обект', 'снимки от обекти'));
    var c = $('#inbox-count'); c.hidden = !fresh; c.textContent = String(fresh);
    if (state.lastPublish) {
      say($('#publish-bar'), '', 'Последно публикуване: ' + new Date(state.lastPublish.requested_at).toLocaleString('bg-BG'));
    }
  }

  /* ---------------------------------------------------------------- catalogue */
  var shown = 0, PAGE = 40, lastList = [];
  $('#q').addEventListener('input', function () { renderCatalogue(true); });
  $('#qf').addEventListener('change', function () { renderCatalogue(true); });
  $('#more').addEventListener('click', function () { renderCatalogue(false); });

  function norm(s) { return String(s || '').toLowerCase(); }
  function renderCatalogue(reset) {
    if (reset) {
      var q = norm($('#q').value).trim().split(/\s+/).filter(Boolean), f = $('#qf').value;
      lastList = CAT.items.filter(function (it) {
        var o = state.overrides[it.key];
        if (f === 'changed' && !o) return false;
        if (f === 'hidden' && !(o && o.hidden)) return false;
        if (f === 'draft' && !(it.draft && !(o && (o.price != null || o.size_prices != null)))) return false;
        var hay = norm(it.name + ' ' + it.where + ' ' + it.brand);
        return q.every(function (w) { return hay.indexOf(w) >= 0; });
      });
      shown = 0; $('#rows').replaceChildren();
    }
    var next = lastList.slice(shown, shown + PAGE);
    next.forEach(function (it) { $('#rows').appendChild(catRow(it)); });
    shown += next.length;
    $('#qcount').textContent = lastList.length + (lastList.length === 1 ? ' продукт' : ' продукта');
    $('#more').hidden = shown >= lastList.length;
  }

  function catRow(it) {
    var o = state.overrides[it.key] || {};
    var price = h('input', { inputmode: 'decimal', value: o.price != null ? eur(o.price) : '', placeholder: toEur(it.price) || 'По запитване', 'aria-label': 'Цена в евро' });
    var old = h('input', { inputmode: 'decimal', value: o.old_price != null ? eur(o.old_price) : '', 'aria-label': 'Стара цена в евро' });
    var badge = h('select', { 'aria-label': 'Етикет' },
      [['', 'Без етикет'], ['new', 'Ново'], ['sale', 'Промоция'], ['hit', 'Топ продукт']].map(function (b) {
        return h('option', { value: b[0], selected: (o.badge || '') === b[0] }, b[1]);
      }));
    var hide = h('input', { type: 'checkbox', checked: !!o.hidden });
    hide.addEventListener('change', function () {
      if (!confirmChange((hide.checked ? 'Да скрием' : 'Да покажем') + ' „' + it.name + '“? Потвърдете промяната и със „Запази“.')) hide.checked = !hide.checked;
    });
    var msg = h('span.msg', { role: 'status' });
    function defaults() {
      return (it.size_prices || []).map(function (s) {
        var p = parseEur(price.value);
        return { size: s.size, price: p == null || Number.isNaN(p) ? s.price : p + s.price - it.price / RATE };
      });
    }
    var sizes = it.key.indexOf('door:') === 0 ? sizeEditor(o.size_prices == null ? defaults() : o.size_prices, o.size_prices == null, defaults) : null;
    if (sizes) price.addEventListener('input', function () { sizes.refresh(defaults()); });
    var mine = o.images || [];
    var originals = it.images || [], excluded = o.excluded_images || [], photoBusy = false;
    function visibleOriginals() { return originals.filter(function (im) { return excluded.indexOf(im.id) < 0; }); }
    function coverSrc() { var visible = visibleOriginals(); return mine.length ? mediaUrl(mine[0].s) : visible.length ? visible[0].thumb : '/assets/no-photo.svg'; }
    var cover = h('img', { src: coverSrc(), alt: '', loading: 'lazy', width: 64, height: 64 });
    var photos = h('div.thumbs-edit');
    var restorePhotos = h('button.btn.btn-ghost.btn-sm', { type: 'button', onclick: function () {
      if (confirmChange('Да върнем всички каталожни снимки за „' + it.name + '“? Качените заместители ще бъдат изтрити.')) setPhotos([], []);
    } }, 'Върни каталожните снимки');
    var resetButton = h('button.btn.btn-ghost.btn-sm', { type: 'button', hidden: !o.product_key, onclick: reset }, 'Върни каталожните');
    var saveButton = h('button.btn.btn-primary.btn-sm', { type: 'button', onclick: save }, 'Запази');
    var files = h('input', { type: 'file', accept: 'image/*', multiple: true, onchange: swapPhotos });
    var row = h('div.row' + (o.hidden ? '.is-hidden' : '') + (o.product_key ? '.is-changed' : ''), null,
      cover,
      h('div', null,
        h('div.name', null, it.name),
        h('div.sub', null, it.where + ' · каталог: ' + fmtEur(it.price) + (it.draft ? ' (ориентировъчна)' : '')),
        h('a.sub', { href: it.url, target: '_blank', rel: 'noopener' }, 'Виж на сайта')),
      h('div.edit', null,
        h('label.field', null, h('span', null, 'Моята цена, €'), price),
        h('label.field', null, h('span', null, 'Стара цена, €'), old),
        h('label.field', null, h('span', null, 'Етикет'), badge),
        sizes ? sizes.element : null,
        h('div.actions', null,
          h('label.toggle', null, hide, 'Скрий от сайта'),
          saveButton,
          resetButton,
          msg),
        photos,
        h('div.actions', null,
          h('label.btn.btn-ghost.btn-sm.file-btn', null, '+ Добави снимки', files), restorePhotos)));
    function drawPhotos() {
      restorePhotos.hidden = !mine.length && !excluded.length;
      var uploaded = mine.length > 0, visible = uploaded ? mine : visibleOriginals();
      photos.replaceChildren.apply(photos, visible.length ? visible.map(function (im, i) {
        return h('figure', null, h('img', { src: uploaded ? mediaUrl(im.s) : im.thumb, alt: 'Снимка ' + (i + 1) }),
          h('button', { type: 'button', 'aria-label': 'Изтрий снимка ' + (i + 1), title: 'Изтрий снимката',
            onclick: function () {
              if (!confirmChange('Да изтрием снимка ' + (i + 1) + ' от „' + it.name + '“? Самият продукт ще остане.')) return;
              if (uploaded) {
                var next = mine.filter(function (x) { return x !== im; });
                setPhotos(next, next.length ? excluded : originals.map(function (x) { return x.id; }));
              } else setPhotos(mine, excluded.concat([im.id]));
            } }, '×'), h('figcaption.sub', null, uploaded ? 'качена' : 'от каталога'));
      }) : [h('p.sub', null, 'Няма снимки. Продуктът остава видим на сайта.')]);
    }
    drawPhotos();
    function busyPhotos(value) {
      photoBusy = value;
      files.disabled = restorePhotos.disabled = resetButton.disabled = saveButton.disabled = value;
      $$('button', photos).forEach(function (button) { button.disabled = value; });
    }
    // Original files may serve other products. Exclude them for this product only;
    // storage deletion is reserved for this product's uploaded copies.
    function setPhotos(next, nextExcluded) {
      if (photoBusy) return Promise.resolve();
      nextExcluded = nextExcluded || excluded;
      busyPhotos(true);
      say(msg, '', 'Запазване…');
      return all(sb.from('product_overrides').upsert({ product_key: it.key, images: next, excluded_images: nextExcluded }).select()).then(function (d) {
        removeFiles(mine.filter(function (x) { return next.indexOf(x) < 0; }));   // ponytail: an orphan file on failure is harmless
        state.overrides[it.key] = d[0];
        mine = d[0].images || [];
        excluded = d[0].excluded_images || [];
        resetButton.hidden = false;
        cover.src = coverSrc();
        drawPhotos(); row.classList.add('is-changed');
        say(msg, 'ok', 'Снимките са запазени. Натиснете „Публикувай промените“.');
        renderHome();
      }).catch(function (e) { removeFiles(next.filter(function (x) { return mine.indexOf(x) < 0; })); say(msg, 'err', 'Не е запазено: ' + e.message); })
        .finally(function () { busyPhotos(false); });
    }
    function swapPhotos() {
      if (photoBusy) return;
      var list = Array.prototype.slice.call(files.files, 0, 20 - mine.length);
      files.value = '';
      if (!list.length) { say(msg, 'err', 'До 20 снимки на продукт.'); return; }
      if (!confirmChange('Да качим избраните снимки за „' + it.name + '“? Те ще заменят каталожните снимки на сайта.')) return;
      busyPhotos(true);
      say(msg, '', 'Качване на ' + list.length + (list.length === 1 ? ' снимка…' : ' снимки…'));
      Promise.all(list.map(function (f) { return uploadPhoto(f, 'catalogue'); }))
        .then(function (up) { busyPhotos(false); return setPhotos(mine.concat(up)); })
        .catch(function (e) { busyPhotos(false); say(msg, 'err', 'Снимката не е качена: ' + e.message); });
    }
    function save() {
      if (photoBusy) return;
      var p = parseEur(price.value), op = parseEur(old.value);
      if (Number.isNaN(p) || Number.isNaN(op)) { say(msg, 'err', 'Цената трябва да е число, напр. 245,50'); return; }
      var sizePrices;
      try { sizePrices = sizes ? sizes.value() : null; }
      catch (e) { say(msg, 'err', e.message); return; }
      var eff = sizePrices && sizePrices.length ? Math.min.apply(null, sizePrices.map(function (s) { return s.price; })) : (p != null ? p : it.price / RATE);
      if (op != null && !(op > eff)) { say(msg, 'err', 'Старата цена трябва да е по-висока от новата.'); return; }
      var rec = { product_key: it.key, price: p, old_price: op, hidden: hide.checked, badge: badge.value || null };
      if (sizes) rec.size_prices = sizePrices;
      if (!confirmChange('Да запазим цените, размерите и останалите промени за „' + it.name + '“?' +
        (rec.hidden ? '\nПродуктът ще бъде скрит от сайта след публикуване.' : ''))) return;
      busyPhotos(true);
      say(msg, '', 'Запазване…');
      all(sb.from('product_overrides').upsert(rec).select()).then(function (d) {
        state.overrides[it.key] = d[0];
        resetButton.hidden = false;
        say(msg, 'ok', 'Запазено. Натиснете „Публикувай“.');
        row.classList.toggle('is-hidden', rec.hidden); row.classList.add('is-changed');
        renderHome();
      }).catch(function (e) { say(msg, 'err', 'Не е запазено: ' + e.message); })
        .finally(function () { busyPhotos(false); });
    }
    function reset() {
      if (photoBusy) return;
      if (!confirmChange('Да върнем всички каталожни данни за „' + it.name + '“? Вашите цени, размери и качени снимки ще бъдат премахнати.')) return;
      busyPhotos(true);
      all(sb.from('product_overrides').delete().eq('product_key', it.key)).then(function () {
        removeFiles(mine);
        delete state.overrides[it.key];
        row.replaceWith(catRow(it)); renderHome();
      }).catch(function (e) { say(msg, 'err', 'Грешка: ' + e.message); })
        .finally(function () { busyPhotos(false); });
    }
    return row;
  }

  /* ---------------------------------------------------------------- photos
     Resized in the browser to a 1200px and a 600px copy before upload: a phone
     photo is 4-8 MB, the site never shows more than 1200px, and her mobile data
     pays for every byte. */
  function loadBitmap(file) {
    if (window.createImageBitmap) {
      return createImageBitmap(file, { imageOrientation: 'from-image' }).catch(function () { return viaImg(file); });
    }
    return viaImg(file);
  }
  function viaImg(file) {
    return new Promise(function (ok, bad) {
      var img = new Image(), url = URL.createObjectURL(file);
      img.onload = function () { URL.revokeObjectURL(url); ok(img); };
      img.onerror = function () { URL.revokeObjectURL(url); bad(new Error('Файлът не е снимка, която браузърът може да отвори.')); };
      img.src = url;
    });
  }
  function scaled(src, width) {
    var w = src.width, hh = src.height, tw = Math.min(width, w), th = Math.round(hh * tw / w);
    var c = document.createElement('canvas'); c.width = tw; c.height = th;
    c.getContext('2d').drawImage(src, 0, 0, tw, th);
    return new Promise(function (ok) {
      c.toBlob(function (b) {
        if (b && b.type === 'image/webp') return ok(b);
        c.toBlob(ok, 'image/jpeg', 0.84);            // Safari cannot encode webp
      }, 'image/webp', 0.82);
    });
  }
  function uid() {
    return (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2));
  }
  function uploadPhoto(file, folder) {
    if (!/^image\//.test(file.type)) return Promise.reject(new Error(file.name + ' не е снимка.'));
    return loadBitmap(file).then(function (bmp) {
      return Promise.all([scaled(bmp, 600), scaled(bmp, 1200)]).then(function (b) {
        var id = folder + '/' + uid(), ext = function (x) { return x.type === 'image/webp' ? 'webp' : 'jpg'; };
        var s = id + '-600.' + ext(b[0]), l = id + '-1200.' + ext(b[1]);
        var put = function (path, blob) {
          return sb.storage.from('media').upload(path, blob, { contentType: blob.type, upsert: false }).then(function (r) { if (r.error) throw r.error; });
        };
        return put(s, b[0]).then(function () { return put(l, b[1]); }).then(function () {
          return { s: s, l: l, w: Math.min(1200, bmp.width), h: Math.round(bmp.height * Math.min(1200, bmp.width) / bmp.width) };
        });
      });
    });
  }
  function mediaUrl(path) { return sb.storage.from('media').getPublicUrl(path).data.publicUrl; }
  function removeFiles(photos) {
    var paths = []; photos.forEach(function (p) { paths.push(p.s, p.l); });
    return paths.length ? sb.storage.from('media').remove(paths) : Promise.resolve();
  }

  /* ---------------------------------------------------------------- her products */
  var editing = null, pImages = [], pSizes = null;
  var pf = $('#pform');
  CAT_READY();
  function CAT_READY() {
    if (!CAT) return setTimeout(CAT_READY, 50);
    pf.category.replaceChildren.apply(pf.category, [h('option', { value: '' }, 'Изберете категория…')]
      .concat(CAT.categories.map(function (c) { return h('option', { value: c.path }, c.label); })));
  }
  pf.section.addEventListener('change', function () { $('#pcat-wrap').hidden = pf.section.value !== 'door'; });
  $('#add-product').addEventListener('click', function () { openProduct(null); });
  $('#pcancel').addEventListener('click', function () {
    if (!confirmChange('Да затворим формата? Незапазените промени по продукта ще се загубят.')) return;
    pf.hidden = true; $('#add-product').hidden = false;
  });

  function openProduct(p) {
    if (!pf.hidden && !confirmChange('Да отворим продукта за редакция отново? Незапазените промени в текущата форма ще се загубят.')) return;
    editing = p; pImages = p ? (p.images || []).slice() : [];
    pf.reset();
    $('#pform-title').textContent = p ? 'Редакция: ' + p.name : 'Нов продукт';
    if (p) {
      pf.section.value = p.section; pf.category.value = p.category || '';
      pf.name.value = p.name; pf.brand.value = p.brand || '';
      pf.price.value = p.price ? eur(p.price) : '0'; pf.old_price.value = p.old_price ? eur(p.old_price) : '';
      pf.badge.value = p.badge || ''; pf.description.value = p.description || '';
    }
    var values = p ? (p.size_prices == null ? (p.sizes || []).map(function (s) { return { size: s, price: p.price || 0 }; }) : p.size_prices) : [];
    pSizes = sizeEditor(values, false);
    pSizes.element.open = true;
    $('#psizes').replaceChildren(pSizes.element);
    $('#pcat-wrap').hidden = pf.section.value !== 'door';
    $('#pdelete').hidden = !p;
    say($('#pmsg'), '', '');
    drawThumbs();
    pf.hidden = false; $('#add-product').hidden = true;
    pf.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  function drawThumbs() {
    $('#pthumbs').replaceChildren.apply($('#pthumbs'), pImages.map(function (im, i) {
      return h('figure', null, h('img', { src: mediaUrl(im.s), alt: 'Снимка ' + (i + 1) }),
        h('button', { type: 'button', 'aria-label': 'Премахни снимка ' + (i + 1), onclick: function () {
          if (!confirmChange('Да премахнем тази снимка от продукта? Промяната ще се запише с „Запази“.')) return;
          pImages.splice(i, 1); drawThumbs();
        } }, '×'));
    }));
  }
  $('#pfiles').addEventListener('change', function (e) {
    var files = [].slice.call(e.target.files), msg = $('#pmsg');
    e.target.value = '';
    if (pImages.length + files.length > 20) { say(msg, 'err', 'До 20 снимки на продукт.'); return; }
    if (!files.length || !confirmChange('Да качим избраните снимки за този продукт?')) return;
    var n = 0;
    say(msg, '', 'Качване 0/' + files.length + '…');
    files.reduce(function (p, f) {
      return p.then(function () { return uploadPhoto(f, 'products'); }).then(function (ph) {
        pImages.push(ph); drawThumbs(); say(msg, '', 'Качване ' + (++n) + '/' + files.length + '…');
      });
    }, Promise.resolve()).then(function () { say(msg, 'ok', 'Снимките са качени. Запазете продукта.'); })
      .catch(function (err) { say(msg, 'err', 'Снимка не се качи: ' + (err.message || err)); });
  });
  pf.addEventListener('submit', function (e) {
    e.preventDefault();
    var msg = $('#pmsg'), p = parseEur(pf.price.value), op = parseEur(pf.old_price.value);
    if (!pImages.length) { say(msg, 'err', 'Добавете поне една снимка.'); return; }
    if (pf.section.value === 'door' && !pf.category.value) { say(msg, 'err', 'Изберете категория за вратата.'); return; }
    if (Number.isNaN(p) || Number.isNaN(op)) { say(msg, 'err', 'Цената трябва да е число, напр. 245,50'); return; }
    var sizePrices;
    try { sizePrices = pSizes.value(); }
    catch (err) { say(msg, 'err', err.message); return; }
    var eff = sizePrices.length ? Math.min.apply(null, sizePrices.map(function (s) { return s.price; })) : (p || 0);
    if (op != null && !(op > eff)) { say(msg, 'err', 'Старата цена трябва да е по-висока от новата.'); return; }
    var rec = {
      section: pf.section.value, category: pf.section.value === 'door' ? pf.category.value : null,
      name: pf.name.value.trim(), brand: pf.brand.value.trim() || null,
      price: p == null ? 0 : p, old_price: op,
      sizes: sizePrices.map(function (s) { return s.size; }), size_prices: sizePrices,
      badge: pf.badge.value || null, description: pf.description.value.trim() || null, images: pImages
    };
    var dropped = editing ? (editing.images || []).filter(function (a) { return !pImages.some(function (b) { return b.s === a.s; }); }) : [];
    if (!confirmChange('Да запазим продукта „' + rec.name + '“ и неговите снимки, размери и цени?')) return;
    say(msg, '', 'Запазване…');
    var q = editing ? sb.from('products').update(rec).eq('id', editing.id).select() : sb.from('products').insert(rec).select();
    all(q).then(function (d) {
      removeFiles(dropped);
      if (editing) state.products = state.products.map(function (x) { return x.id === editing.id ? d[0] : x; });
      else state.products.unshift(d[0]);
      pf.hidden = true; $('#add-product').hidden = false;
      renderMine(); renderHome();
      say($('#publish-bar'), '', 'Продуктът е запазен. Натиснете „Публикувай промените“, за да излезе на сайта.');
    }).catch(function (err) { say(msg, 'err', 'Не е запазено: ' + err.message); });
  });
  $('#pdelete').addEventListener('click', function () {
    if (!editing) return;
    var p = editing, msg = $('#pmsg');
    if (!confirmChange('Да изтрием продукта „' + p.name + '“ и качените му снимки? Това действие не може да бъде отменено.')) return;
    all(sb.from('products').delete().eq('id', p.id)).then(function () {
      removeFiles(p.images || []);
      state.products = state.products.filter(function (x) { return x.id !== p.id; });
      pf.hidden = true; $('#add-product').hidden = false; renderMine(); renderHome();
    }).catch(function (err) { say(msg, 'err', 'Не е изтрит: ' + err.message); });
  });
  function renderMine() {
    var secName = { door: 'Врати', nastilki: 'Настилки', granitogres: 'Гранитогрес', parvazi: 'Первази' };
    var box = $('#mine-rows');
    if (!state.products.length) { box.replaceChildren(h('p.muted', null, 'Още няма добавени продукти.')); return; }
    box.replaceChildren.apply(box, state.products.map(function (p) {
      var hide = h('input', { type: 'checkbox', checked: !!p.hidden });
      hide.addEventListener('change', function () {
        if (!confirmChange((hide.checked ? 'Да скрием' : 'Да покажем') + ' „' + p.name + '“ на сайта?')) { hide.checked = !!p.hidden; return; }
        hide.disabled = true;
        all(sb.from('products').update({ hidden: hide.checked }).eq('id', p.id).select()).then(function (d) {
          p.hidden = d[0].hidden; row.classList.toggle('is-hidden', p.hidden);
        }).catch(function (err) {
          hide.checked = !!p.hidden; say($('#publish-bar'), 'err', 'Не е запазено: ' + err.message);
        }).finally(function () { hide.disabled = false; });
      });
      var row = h('div.row' + (p.hidden ? '.is-hidden' : ''), null,
        p.images && p.images[0] ? h('img', { src: mediaUrl(p.images[0].s), alt: '', width: 64, height: 64 }) : h('div'),
        h('div', null, h('div.name', null, p.name),
          h('div.sub', null, secName[p.section] + ' · ' + fmtE(p.price) + (p.old_price ? ' (беше ' + eur(p.old_price) + ' €)' : ''))),
        h('div.edit', null, h('div.actions', null,
          h('label.toggle', null, hide, 'Скрий от сайта'),
          h('button.btn.btn-ghost.btn-sm', { type: 'button', onclick: function () { openProduct(p); } }, 'Редактирай'))));
      return row;
    }));
  }

  /* ---------------------------------------------------------------- projects */
  function renderAlbums() {
    var names = CAT.albums.slice();
    state.photos.forEach(function (p) { if (names.indexOf(p.album) < 0) names.push(p.album); });
    var sel = $('#album'), cur = sel.value;
    sel.replaceChildren.apply(sel, names.map(function (n) { return h('option', { value: n }, n); })
      .concat([h('option', { value: '__new' }, 'Нов албум…')]));
    if (cur) sel.value = cur;
  }
  $('#album').addEventListener('change', function () { $('#newalbum-wrap').hidden = $('#album').value !== '__new'; });
  $('#upfiles').addEventListener('change', function (e) {
    var files = [].slice.call(e.target.files), msg = $('#upmsg');
    e.target.value = '';
    var album = $('#album').value === '__new' ? $('#newalbum').value.trim().replace(/\s+/g, ' ') : $('#album').value;
    if (!album || album.length < 2) { say(msg, 'err', 'Напишете име на албума.'); return; }
    if (!files.length || !confirmChange('Да качим избраните снимки в албум „' + album + '“?')) return;
    var n = 0;
    say(msg, '', 'Качване 0/' + files.length + '…');
    files.reduce(function (p, f) {
      return p.then(function () { return uploadPhoto(f, 'projects'); }).then(function (ph) {
        return all(sb.from('project_photos').insert({ album: album, photo: ph }).select());
      }).then(function (d) {
        state.photos.unshift(d[0]); say(msg, '', 'Качване ' + (++n) + '/' + files.length + '…');
      });
    }, Promise.resolve()).then(function () {
      say(msg, 'ok', (n === 1 ? '1 снимка е качена' : n + ' снимки са качени') + ' в „' + album + '“. Натиснете „Публикувай промените“.');
      renderAlbums(); $('#album').value = album; $('#newalbum-wrap').hidden = true;
      renderPhotos(); renderHome();
    }).catch(function (err) {
      renderPhotos();
      say(msg, 'err', 'Спря на снимка ' + (n + 1) + ': ' + (err.message || err));
    });
  });
  function renderPhotos() {
    var box = $('#photos');
    if (!state.photos.length) { box.replaceChildren(h('p.muted', null, 'Още няма качени снимки от обекти.')); return; }
    box.replaceChildren.apply(box, state.photos.map(function (p) {
      var del = h('button.btn.btn-danger.btn-sm', { type: 'button' }, 'Изтрий');
      del.addEventListener('click', function () {
        if (!confirmChange('Да изтрием тази снимка от албум „' + p.album + '“? Това действие не може да бъде отменено.')) return;
        all(sb.from('project_photos').delete().eq('id', p.id)).then(function () {
          removeFiles([p.photo]);
          state.photos = state.photos.filter(function (x) { return x.id !== p.id; });
          renderPhotos(); renderHome();
        });
      });
      return h('figure', null, h('img', { src: mediaUrl(p.photo.s), alt: p.album, loading: 'lazy' }),
        h('figcaption', null, h('span', null, p.album), del));
    }));
  }

  /* ---------------------------------------------------------------- inbox */
  function renderInbox() {
    var box = $('#inbox');
    if (!state.inbox.length) { box.replaceChildren(h('p.muted', null, 'Няма запитвания.')); return; }
    box.replaceChildren.apply(box, state.inbox.map(function (q) {
      var tel = /^[+\d][\d\s()-]{5,}$/.test(q.contact.trim()) ? q.contact.replace(/[^\d+]/g, '') : null;
      var mail = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(q.contact.trim()) ? q.contact.trim() : null;
      var done = h('button.btn.btn-ghost.btn-sm', { type: 'button' }, q.status === 'new' ? 'Готово' : 'Върни като ново');
      done.addEventListener('click', function () {
        var st = q.status === 'new' ? 'done' : 'new';
        if (!confirmChange('Да отбележим запитването от „' + q.name + '“ като ' + (st === 'done' ? 'обработено' : 'ново') + '?')) return;
        all(sb.from('inquiries').update({ status: st }).eq('id', q.id).select()).then(function (d) {
          q.status = d[0].status; renderInbox(); renderHome();
        });
      });
      var del = h('button.btn.btn-danger.btn-sm', { type: 'button' }, 'Изтрий');
      del.addEventListener('click', function () {
        if (!confirmChange('Да изтрием запитването от „' + q.name + '“? Това действие не може да бъде отменено.')) return;
        all(sb.from('inquiries').delete().eq('id', q.id)).then(function () {
          state.inbox = state.inbox.filter(function (x) { return x.id !== q.id; }); renderInbox(); renderHome();
        });
      });
      return h('article.inq' + (q.status === 'done' ? '.done' : ''), null,
        h('div.meta', null, new Date(q.created_at).toLocaleString('bg-BG') + (q.topic ? ' · ' + q.topic : '') + (q.page ? ' · от ' + q.page : '')),
        h('div.name', null, q.name + ' — ' + q.contact),
        q.message ? h('div.text', null, q.message) : null,
        h('div.actions', null,
          tel ? h('a.btn.btn-primary.btn-sm', { href: 'tel:' + tel }, 'Обади се') : null,
          tel ? h('a.btn.btn-ghost.btn-sm', { href: 'viber://chat?number=' + encodeURIComponent(tel) }, 'Viber') : null,
          mail ? h('a.btn.btn-primary.btn-sm', { href: 'mailto:' + mail + '?subject=' + encodeURIComponent('Вашето запитване към NG Doors') }, 'Отговори') : null,
          done, del));
    }));
  }

  /* ---------------------------------------------------------------- settings */
  function renderSettings() {
    var f = $('#sform');
    ['phone', 'email', 'hours', 'address', 'announcement'].forEach(function (k) { f[k].value = state.settings[k] || ''; });
  }
  $('#sform').addEventListener('submit', function (e) {
    e.preventDefault();
    var f = e.target, msg = $('#smsg'), up = [], del = [];
    if (f.phone.value.trim() && !/^\+?[\d ()-]{6,24}$/.test(f.phone.value.trim())) { say(msg, 'err', 'Телефонът може да съдържа само цифри, интервали и +.'); return; }
    ['phone', 'email', 'hours', 'address', 'announcement'].forEach(function (k) {
      var v = f[k].value.trim();
      if (v) up.push({ key: k, value: v }); else del.push(k);
    });
    if (!confirmChange('Да запазим настройките за телефон, имейл, адрес, работно време и съобщение на сайта?')) return;
    say(msg, '', 'Запазване…');
    Promise.all([
      up.length ? all(sb.from('settings').upsert(up)) : null,
      del.length ? all(sb.from('settings').delete().in('key', del)) : null
    ]).then(function () {
      state.settings = {}; up.forEach(function (s) { state.settings[s.key] = s.value; });
      say(msg, 'ok', 'Запазено. Натиснете „Публикувай промените“.');
    }).catch(function (err) { say(msg, 'err', 'Не е запазено: ' + err.message); });
  });

  /* ---------------------------------------------------------------- publish */
  $('#publish').addEventListener('click', function () {
    var btn = $('#publish'), bar = $('#publish-bar');
    if (!confirmChange('Да публикуваме всички запазени промени? Те ще станат видими за посетителите на сайта.')) return;
    btn.disabled = true; say(bar, '', 'Изпращане…');
    sb.functions.invoke('publish', { body: {} }).then(function (r) {
      if (r.error) {
        var ctx = r.error.context;
        return (ctx && ctx.json ? ctx.json() : Promise.resolve({})).then(function (j) {
          throw new Error((j && j.error) || r.error.message);
        });
      }
      say(bar, 'ok', 'Сайтът се обновява. След около 3 минути промените са видими.');
    }).catch(function (e) {
      say(bar, 'err', 'Публикуването не тръгна: ' + (e.message || e));
    }).then(function () { setTimeout(function () { btn.disabled = false; }, 20000); });
  });
})();
