// NG Doors backend: the admin panel's data, her photos, her login, the contact form and
// the "Публикувай" button. One Cloudflare Worker with D1 (database), R2 (photos) and
// Email Routing (mail). It replaced Supabase on 2026-11-11, because the free Supabase
// plan paused the project after a week without visits and the panel stopped working.
//
// D1 has no row-level security, so every rule Supabase enforced in SQL lives here:
// a route under /admin/ refuses without a valid session, and every write is validated
// before it touches the database. The browser is never trusted.
//
// Bindings (wrangler.toml): DB (D1), MEDIA (R2), MAIL (send_email).
// Vars: FROM, TO, SITE_ORIGINS, ADMIN_URL. Secret: DEPLOY_HOOK (Pages deploy hook URL).
import { EmailMessage } from "cloudflare:email";

const DAY = 86400000;
// A session lives as long as it is used: each visit pushes the end 7 days out. Seven
// days without opening the panel and she signs in again (user's request, 2026-11-11).
const IDLE_MS = 7 * DAY;
const RESET_MS = 3600000;
const PBKDF2_ITER = 100000;          // the Workers runtime caps PBKDF2 at 100k iterations
const MEDIA_PATH = /^(catalogue|products|projects)\/[A-Za-z0-9-]{8,64}-(600|1200)\.(webp|jpg)$/;
const MEDIA_TYPES = { "image/webp": "webp", "image/jpeg": "jpg", "image/png": "png" };
const MAX_UPLOAD = 10485760;
const SETTING_KEYS = ["phone", "email", "hours", "address", "announcement", "series_prices"];
const SECTIONS = ["door", "nastilki", "granitogres", "parvazi"];
const BADGES = [null, "new", "sale", "hit"];

class Bad extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
const bad = (m) => new Bad(400, m);

/* ------------------------------------------------------------------ http */
function cors(req, env) {
  const allowed = (env.SITE_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  const o = req.headers.get("Origin") || "";
  return {
    "Access-Control-Allow-Origin": allowed.includes(o) ? o : allowed[0] || "",
    "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "authorization, content-type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}
const reply = (req, env, status, body) => new Response(JSON.stringify(body), {
  status, headers: { ...cors(req, env), "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
});
async function body(req) {
  try { const b = await req.json(); if (b && typeof b === "object") return b; } catch (_) {}
  throw bad("Невалидна заявка.");
}

/* ------------------------------------------------------------------ crypto */
const enc = new TextEncoder();
const b64url = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64url = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
const token = () => b64url(crypto.getRandomValues(new Uint8Array(32)));
async function sha256(s) { return b64url(await crypto.subtle.digest("SHA-256", enc.encode(s))); }
async function pbkdf2(password, salt, iter) {
  const key = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt, iterations: iter }, key, 256));
}
async function hashPassword(password) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  return `pbkdf2$${PBKDF2_ITER}$${b64url(salt)}$${b64url(await pbkdf2(password, salt, PBKDF2_ITER))}`;
}
async function checkPassword(password, stored) {
  const [kind, iter, salt, want] = String(stored || "").split("$");
  if (kind !== "pbkdf2") { await pbkdf2(password, new Uint8Array(16), PBKDF2_ITER); return false; }  // same time either way
  const got = await pbkdf2(password, unb64url(salt), Number(iter)), exp = unb64url(want);
  let diff = got.length ^ exp.length;
  for (let i = 0; i < got.length; i++) diff |= got[i] ^ (exp[i] || 0);
  return diff === 0;
}
function validPassword(p) {
  if (typeof p !== "string" || p.length < 10 || p.length > 200) throw bad("Паролата трябва да е поне 10 знака.");
  return p;
}
const normEmail = (e) => String(e || "").trim().toLowerCase().slice(0, 254);

/* ------------------------------------------------------------------ rows */
const JSON_COLS = ["images", "size_prices", "excluded_images", "sizes", "photo"];
const BOOL_COLS = ["hidden", "ok"];
function row(r) {
  if (!r) return r;
  const o = { ...r };
  for (const k of JSON_COLS) if (k in o && o[k] != null) o[k] = JSON.parse(o[k]);
  for (const k of BOOL_COLS) if (k in o && o[k] != null) o[k] = !!o[k];
  return o;
}
const rows = (res) => (res.results || []).map(row);
const now = () => new Date().toISOString();

/* ------------------------------------------------------------------ validation
   Ported one for one from the Supabase CHECK constraints (supabase/schema.sql). */
const str = (v, min, max, what) => {
  if (typeof v !== "string" || v.trim().length < min || v.length > max) throw bad("Невалидно поле: " + what + ".");
  return v;
};
const optStr = (v, max, what) => (v == null || v === "" ? null : str(v, 0, max, what));
const cents = (n) => Math.abs(Math.round(n * 100) - n * 100) < 1e-6;
function money(v, what, { nullable = true, positive = false } = {}) {
  if (v == null) { if (nullable) return null; throw bad("Липсва " + what + "."); }
  if (typeof v !== "number" || !Number.isFinite(v) || v >= 1e6 || (positive ? v <= 0 : v < 0) || !cents(v))
    throw bad("Невалидна " + what + ".");
  return v;
}
function photo(p) {
  if (!p || typeof p !== "object" || Array.isArray(p) || !MEDIA_PATH.test(p.s) || !MEDIA_PATH.test(p.l)
      || typeof p.w !== "number" || typeof p.h !== "number" || p.w < 1 || p.w > 20000 || p.h < 1 || p.h > 20000)
    throw bad("Невалидна снимка.");
  return { s: p.s, l: p.l, w: p.w, h: p.h };
}
function photos(a) {
  if (!Array.isArray(a) || a.length > 20) throw bad("До 20 снимки на продукт.");
  return a.map(photo);
}
function sizePrices(a) {
  if (a == null) return null;
  if (!Array.isArray(a) || a.length > 30) throw bad("До 30 размера.");
  const seen = new Set();
  return a.map((e) => {
    const size = e && e.size, price = e && e.price;
    if (typeof size !== "string" || size.length < 1 || size.length > 80 || size !== size.trim()
        || /[\x00-\x1f\x7f]/.test(size) || seen.has(size.toLowerCase())) throw bad("Невалиден размер.");
    seen.add(size.toLowerCase());
    return { size, price: money(price, "цена на размер", { nullable: false }) };
  });
}
function excluded(a) {
  if (!Array.isArray(a) || a.length > 100 || a.some((x) => typeof x !== "string" || x.length < 1 || x.length > 2048))
    throw bad("Невалиден списък със скрити снимки.");
  return a;
}
function badge(b) {
  if (!BADGES.includes(b == null ? null : b)) throw bad("Невалиден етикет.");
  return b == null ? null : b;
}
function override(o) {
  if (!/^(door|floor):[A-Za-z0-9_-]{1,80}$/.test(o.product_key || "")) throw bad("Невалиден продукт.");
  return {
    product_key: o.product_key, price: money(o.price, "цена"), old_price: money(o.old_price, "стара цена", { positive: true }),
    hidden: !!o.hidden, badge: badge(o.badge), images: photos(o.images || []),
    size_prices: sizePrices(o.size_prices), excluded_images: excluded(o.excluded_images || []),
  };
}
function product(p) {
  if (!SECTIONS.includes(p.section)) throw bad("Невалиден раздел.");
  const sizes = p.sizes || [];
  if (!Array.isArray(sizes) || sizes.length > 30 || sizes.some((s) => typeof s !== "string")) throw bad("Невалидни размери.");
  return {
    section: p.section, category: optStr(p.category, 120, "категория"), name: str(p.name, 2, 160, "име").trim(),
    brand: optStr(p.brand, 80, "марка"), description: optStr(p.description, 4000, "описание"),
    price: money(p.price == null ? 0 : p.price, "цена", { nullable: false }),
    old_price: money(p.old_price, "стара цена", { positive: true }), sizes,
    size_prices: sizePrices(p.size_prices), images: photos(p.images || []), badge: badge(p.badge), hidden: !!p.hidden,
  };
}
const j = (v) => (v == null ? null : JSON.stringify(v));

/* ------------------------------------------------------------------ mail */
const word = (s) => "=?UTF-8?B?" + b64(s) + "?=";
const b64 = (s) => btoa(String.fromCharCode(...enc.encode(s)));
export function mime(from, to, subject, text) {
  return [
    "From: " + word("NG Doors сайт") + " <" + from + ">",
    "To: " + to,
    "Subject: " + word(subject),
    "Date: " + new Date().toUTCString(),
    "Message-ID: <" + crypto.randomUUID() + "@" + from.split("@")[1] + ">",
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=UTF-8",
    "Content-Transfer-Encoding: base64",
    "",
    b64(text).replace(/.{76}/g, "$&\r\n"),
  ].join("\r\n");
}
async function mail(env, to, subject, text) {
  const sent = [], failed = [];
  for (const addr of to) {
    // ponytail: an unverified destination throws; skip it so the others still get the mail
    try { await env.MAIL.send(new EmailMessage(env.FROM, addr, mime(env.FROM, addr, subject, text))); sent.push(addr); }
    catch (e) { failed.push(addr + ": " + String(e).slice(0, 120)); }
  }
  console.log("mail", JSON.stringify({ subject, sent, failed }));   // the only record of delivery
  return sent.length > 0;
}

/* ------------------------------------------------------------------ auth */
async function session(req, env) {
  const h = req.headers.get("Authorization") || "";
  if (!h.startsWith("Bearer ")) throw new Bad(401, "Влезте отново.");
  const th = await sha256(h.slice(7)), t = Date.now();
  const s = await env.DB.prepare("select email, expires_at from sessions where token_hash = ? and expires_at > ?")
    .bind(th, t).first();
  if (!s) throw new Bad(401, "Не сте влизали няколко дни. Влезте отново с паролата си.");
  // ponytail: one write per hour at most, not one per request
  if (s.expires_at < t + IDLE_MS - 3600000)
    await env.DB.prepare("update sessions set expires_at = ? where token_hash = ?").bind(t + IDLE_MS, th).run();
  return s.email;
}
async function newSession(env, email) {
  const t = token();
  await env.DB.prepare("insert into sessions (token_hash, email, expires_at) values (?, ?, ?)")
    .bind(await sha256(t), email, Date.now() + IDLE_MS).run();
  return t;
}

async function login(req, env) {
  const b = await body(req), email = normEmail(b.email), t = Date.now();
  const since = t - 15 * 60000;
  const fails = await env.DB.prepare("select sum(email = ?) mine, count(*) total from login_fails where at > ?").bind(email, since).first();
  if ((fails.mine || 0) >= 5 || (fails.total || 0) >= 100) throw new Bad(429, "Твърде много опити. Изчакайте 15 минути.");
  const a = await env.DB.prepare("select pass_hash from admins where email = ?").bind(email).first();
  const ok = await checkPassword(String(b.password || ""), a && a.pass_hash);
  if (!ok) {
    await env.DB.batch([
      env.DB.prepare("insert into login_fails (email, at) values (?, ?)").bind(email, t),
      env.DB.prepare("delete from login_fails where at < ?").bind(t - DAY),
    ]);
    throw new Bad(401, "Грешен имейл или парола.");
  }
  await env.DB.prepare("delete from sessions where expires_at < ?").bind(t).run();
  return { token: await newSession(env, email), email };
}

// "Забравена парола" and the first login: an emailed one-hour link. The reply is the
// same whether or not the address has access, so the form cannot be used to find out.
async function requestReset(req, env, ctx) {
  const email = normEmail((await body(req)).email);
  const a = await env.DB.prepare("select email from admins where email = ?").bind(email).first();
  if (!a) return { ok: true };
  const recent = await env.DB.prepare("select 1 from resets where email = ? and expires_at > ?")
    .bind(email, Date.now() + RESET_MS - 120000).first();
  if (recent) return { ok: true };                                   // one email per two minutes
  const t = token();
  await env.DB.batch([
    env.DB.prepare("delete from resets where email = ? or expires_at < ?").bind(email, Date.now()),
    env.DB.prepare("insert into resets (token_hash, email, expires_at) values (?, ?, ?)").bind(await sha256(t), email, Date.now() + RESET_MS),
  ]);
  ctx.waitUntil(mail(env, [email], "Вход в управлението на сайта",
    "Здравейте,\r\n\r\nОтворете тази връзка, за да изберете парола за управлението на сайта NG Doors:\r\n\r\n"
    + env.ADMIN_URL + "#reset=" + t + "\r\n\r\nВръзката важи един час. Ако не сте я поискали, не правете нищо."));
  return { ok: true };
}

async function setPassword(req, env) {
  const b = await body(req), password = validPassword(b.password);
  if (b.token) {
    const r = await env.DB.prepare("select email from resets where token_hash = ? and expires_at > ?")
      .bind(await sha256(String(b.token)), Date.now()).first();
    if (!r) throw new Bad(400, "Връзката е изтекла или вече е използвана. Поискайте нова.");
    await env.DB.batch([
      env.DB.prepare("update admins set pass_hash = ? where email = ?").bind(await hashPassword(password), r.email),
      env.DB.prepare("delete from resets where email = ?").bind(r.email),
      env.DB.prepare("delete from sessions where email = ?").bind(r.email),
    ]);
    return { token: await newSession(env, r.email), email: r.email };
  }
  // Changing it from inside the panel needs the current one, so an unattended open
  // panel cannot be used to lock her out.
  const email = await session(req, env);
  const a = await env.DB.prepare("select pass_hash from admins where email = ?").bind(email).first();
  if (!(await checkPassword(String(b.current || ""), a && a.pass_hash))) throw bad("Сегашната парола е грешна.");
  await env.DB.prepare("update admins set pass_hash = ? where email = ?").bind(await hashPassword(password), email).run();
  return { ok: true };
}

/* ------------------------------------------------------------------ public */
async function publicData(env) {
  const [ov, pr, ph, st] = await env.DB.batch([
    env.DB.prepare("select * from product_overrides order by product_key"),
    env.DB.prepare("select * from products where hidden = 0 order by created_at, id"),
    env.DB.prepare("select * from project_photos where hidden = 0 order by created_at, id"),
    env.DB.prepare("select key, value from settings order by key"),
  ]);
  return { overrides: rows(ov), products: rows(pr), photos: rows(ph), settings: rows(st) };
}

async function inquiry(req, env, ctx) {
  const b = await body(req);
  const r = {
    id: crypto.randomUUID(), name: str(b.name, 1, 120, "име").trim(), contact: str(b.contact, 3, 160, "контакт").trim(),
    topic: optStr(b.topic, 80, "тема"), message: optStr(b.message, 4000, "съобщение"), page: optStr(b.page, 300, "страница"),
    email: String(b.email || "").trim().slice(0, 254), phone: String(b.phone || "").trim().slice(0, 32),
  };
  // Table-fill guard, not per-visitor protection: caps the table at 30 inquiries in ten minutes.
  const n = await env.DB.prepare("select count(*) n from inquiries where created_at > strftime('%Y-%m-%dT%H:%M:%fZ', 'now', '-10 minutes')").first();
  if (n.n >= 30) throw new Bad(429, "Твърде много запитвания. Опитайте след малко.");
  await env.DB.prepare("insert into inquiries (id, name, contact, topic, message, page, email, phone) values (?, ?, ?, ?, ?, ?, ?, ?)")
    .bind(r.id, r.name, r.contact, r.topic, r.message, r.page, r.email, r.phone).run();
  const to = (env.TO || "").split(",").map((s) => s.trim()).filter(Boolean);
  ctx.waitUntil(mail(env, to, "Ново запитване: " + r.name.slice(0, 60), [
    "Ново запитване от сайта ngdoors", "", "Име: " + r.name,
    r.email ? "Имейл: " + r.email : null, r.phone ? "Телефон: " + r.phone : null,
    !r.email && !r.phone ? "Контакт: " + r.contact : null,
    r.topic ? "Тема: " + r.topic : null, r.page ? "Страница: " + r.page : null,
    "", r.message || "(без съобщение)", "", "Всички запитвания: " + env.ADMIN_URL,
  ].filter((l) => l !== null).join("\r\n")));
  return { ok: true };
}

async function media(req, env, path) {
  if (!MEDIA_PATH.test(path)) return new Response("not found", { status: 404 });
  const o = await env.MEDIA.get(path);
  if (!o) return new Response("not found", { status: 404 });
  return new Response(o.body, { headers: {
    "Content-Type": o.httpMetadata && o.httpMetadata.contentType || "application/octet-stream",
    "Cache-Control": "public, max-age=31536000, immutable", "ETag": o.httpEtag, "Access-Control-Allow-Origin": "*",
  } });
}

/* ------------------------------------------------------------------ admin */
async function adminData(env) {
  const [ov, pr, ph, inq, st, pub] = await env.DB.batch([
    env.DB.prepare("select * from product_overrides"),
    env.DB.prepare("select * from products order by created_at desc"),
    env.DB.prepare("select * from project_photos order by created_at desc"),
    env.DB.prepare("select * from inquiries order by created_at desc limit 300"),
    env.DB.prepare("select key, value from settings"),
    env.DB.prepare("select * from publish_log order by id desc limit 1"),
  ]);
  return { overrides: rows(ov), products: rows(pr), photos: rows(ph), inquiries: rows(inq), settings: rows(st), lastPublish: rows(pub)[0] || null };
}

// Supabase upsert semantics: columns she did not send keep their stored value.
async function putOverride(env, key, b) {
  const old = row(await env.DB.prepare("select * from product_overrides where product_key = ?").bind(key).first()) || {};
  const o = override({ ...old, ...b, product_key: key });
  await env.DB.prepare(`insert or replace into product_overrides
      (product_key, price, old_price, hidden, badge, images, size_prices, excluded_images, updated_at)
      values (?, ?, ?, ?, ?, ?, ?, ?, ?)`)
    .bind(o.product_key, o.price, o.old_price, o.hidden ? 1 : 0, o.badge, j(o.images), j(o.size_prices), j(o.excluded_images), now()).run();
  return row(await env.DB.prepare("select * from product_overrides where product_key = ?").bind(key).first());
}

async function saveProduct(env, id, b) {
  let p;
  if (id) {
    const old = row(await env.DB.prepare("select * from products where id = ?").bind(id).first());
    if (!old) throw new Bad(404, "Продуктът не съществува.");
    p = product({ ...old, ...b });
    await env.DB.prepare(`update products set section = ?, category = ?, name = ?, brand = ?, description = ?, price = ?,
        old_price = ?, sizes = ?, size_prices = ?, images = ?, badge = ?, hidden = ?, updated_at = ? where id = ?`)
      .bind(p.section, p.category, p.name, p.brand, p.description, p.price, p.old_price, j(p.sizes), j(p.size_prices),
            j(p.images), p.badge, p.hidden ? 1 : 0, now(), id).run();
  } else {
    p = product(b); id = crypto.randomUUID();
    await env.DB.prepare(`insert into products (id, section, category, name, brand, description, price, old_price, sizes,
        size_prices, images, badge, hidden) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .bind(id, p.section, p.category, p.name, p.brand, p.description, p.price, p.old_price, j(p.sizes), j(p.size_prices),
            j(p.images), p.badge, p.hidden ? 1 : 0).run();
  }
  return row(await env.DB.prepare("select * from products where id = ?").bind(id).first());
}

async function addPhoto(env, b) {
  const id = crypto.randomUUID(), album = str(b.album, 2, 60, "албум").trim().replace(/\s+/g, " ");
  await env.DB.prepare("insert into project_photos (id, album, photo, caption) values (?, ?, ?, ?)")
    .bind(id, album, j(photo(b.photo)), optStr(b.caption, 200, "надпис")).run();
  return row(await env.DB.prepare("select * from project_photos where id = ?").bind(id).first());
}

async function setInquiry(env, id, b) {
  if (!["new", "done"].includes(b.status)) throw bad("Невалидно състояние.");
  await env.DB.prepare("update inquiries set status = ? where id = ?").bind(b.status, id).run();
  const r = row(await env.DB.prepare("select * from inquiries where id = ?").bind(id).first());
  if (!r) throw new Bad(404, "Запитването не съществува.");
  return r;
}

// One price for a whole door series, or a % change on it. Stored as one JSON setting:
// {"<series path>": {"price": 450} | {"pct": -10}}. build.py applies it; a price she set
// on a single door still wins over its series.
function seriesPrices(v) {
  let o;
  try { o = JSON.parse(String(v)); } catch (_) { throw bad("Невалидни цени на серии."); }
  if (!o || typeof o !== "object" || Array.isArray(o) || Object.keys(o).length > 200) throw bad("Невалидни цени на серии.");
  const out = {};
  for (const [k, r] of Object.entries(o)) {
    if (k.length < 1 || k.length > 200 || /[\x00-\x1f\x7f]/.test(k) || !r || typeof r !== "object" || Object.keys(r).length !== 1)
      throw bad("Невалидна серия.");
    if ("price" in r) out[k] = { price: money(r.price, "цена на серия", { nullable: false, positive: true }) };
    else if (typeof r.pct === "number" && Number.isFinite(r.pct) && r.pct >= -90 && r.pct <= 300 && r.pct !== 0 && cents(r.pct))
      out[k] = { pct: r.pct };
    else throw bad("Процентът трябва да е между -90 и 300.");
  }
  return JSON.stringify(out);
}

async function putSettings(env, b) {
  const set = b.set || {}, del = b.del || [];
  const stmts = [];
  for (const k of Object.keys(set)) {
    if (!SETTING_KEYS.includes(k)) throw bad("Невалидна настройка.");
    const v = k === "series_prices" ? seriesPrices(set[k]) : str(set[k], 1, 300, k).trim();
    stmts.push(env.DB.prepare("insert or replace into settings (key, value, updated_at) values (?, ?, ?)").bind(k, v, now()));
  }
  for (const k of del) {
    if (!SETTING_KEYS.includes(k)) throw bad("Невалидна настройка.");
    stmts.push(env.DB.prepare("delete from settings where key = ?").bind(k));
  }
  if (stmts.length) await env.DB.batch(stmts);
  return { ok: true };
}

async function upload(req, env, path) {
  const type = (req.headers.get("Content-Type") || "").split(";")[0].trim();
  if (!MEDIA_PATH.test(path) || !MEDIA_TYPES[type] || !path.endsWith("." + MEDIA_TYPES[type])) throw bad("Невалидна снимка.");
  const buf = await req.arrayBuffer();
  if (!buf.byteLength || buf.byteLength > MAX_UPLOAD) throw bad("Снимката е по-голяма от 10 MB.");
  if (await env.MEDIA.head(path)) throw new Bad(409, "Такава снимка вече има.");
  await env.MEDIA.put(path, buf, { httpMetadata: { contentType: type } });
  return { ok: true, path };
}

async function removeMedia(env, b) {
  const paths = Array.isArray(b.paths) ? b.paths : [];
  if (paths.length > 200 || paths.some((p) => !MEDIA_PATH.test(p))) throw bad("Невалиден списък със снимки.");
  if (paths.length) await env.MEDIA.delete(paths);
  return { ok: true };
}

async function publish(env, email) {
  const last = await env.DB.prepare("select requested_at from publish_log order by id desc limit 1").first();
  if (last && Date.now() - Date.parse(last.requested_at) < 60000) throw new Bad(429, "Току-що публикувахте. Изчакайте минута.");
  if (!env.DEPLOY_HOOK) throw new Bad(500, "Публикуването не е настроено (DEPLOY_HOOK).");
  let ok = false, detail = "";
  try {
    const r = await fetch(env.DEPLOY_HOOK, { method: "POST" });
    ok = r.ok;
    detail = ok ? "started" : `deploy hook ${r.status}: ${(await r.text()).slice(0, 300)}`;
  } catch (e) { detail = "deploy hook unreachable: " + String(e).slice(0, 300); }
  await env.DB.prepare("insert into publish_log (requested_by, ok, detail, requested_at) values (?, ?, ?, ?)").bind(email, ok ? 1 : 0, detail, now()).run();
  if (!ok) throw new Bad(502, "Сървърът за публикуване не отговори. Опитайте след малко.");
  return { ok: true };
}

/* ------------------------------------------------------------------ router */
async function route(req, env, ctx) {
  const url = new URL(req.url), p = url.pathname, m = req.method;
  const seg = p.split("/").filter(Boolean).map(decodeURIComponent);

  if (m === "GET" && seg[0] === "media") return media(req, env, seg.slice(1).join("/"));
  if (m === "GET" && p === "/public-data") return publicData(env);
  if (m === "POST" && p === "/inquiry") return inquiry(req, env, ctx);
  if (m === "POST" && p === "/auth/login") return login(req, env);
  if (m === "POST" && p === "/auth/reset") return requestReset(req, env, ctx);
  if (m === "POST" && p === "/auth/password") return setPassword(req, env);
  if (m === "POST" && p === "/auth/logout") {
    const h = req.headers.get("Authorization") || "";
    if (h.startsWith("Bearer ")) await env.DB.prepare("delete from sessions where token_hash = ?").bind(await sha256(h.slice(7))).run();
    return { ok: true };
  }
  if (seg[0] !== "admin") throw new Bad(404, "Няма такъв адрес.");

  const email = await session(req, env);
  const [, what, id] = seg;
  if (m === "GET" && what === "me") return { email };
  if (m === "GET" && what === "data") return adminData(env);
  if (what === "overrides" && id) {
    if (m === "PUT") return putOverride(env, id, await body(req));
    if (m === "DELETE") { await env.DB.prepare("delete from product_overrides where product_key = ?").bind(id).run(); return { ok: true }; }
  }
  if (what === "products") {
    if (m === "POST" && !id) return saveProduct(env, null, await body(req));
    if (m === "PATCH" && id) return saveProduct(env, id, await body(req));
    if (m === "DELETE" && id) { await env.DB.prepare("delete from products where id = ?").bind(id).run(); return { ok: true }; }
  }
  if (what === "photos") {
    if (m === "POST" && !id) return addPhoto(env, await body(req));
    if (m === "DELETE" && id) { await env.DB.prepare("delete from project_photos where id = ?").bind(id).run(); return { ok: true }; }
  }
  if (what === "inquiries" && id) {
    if (m === "PATCH") return setInquiry(env, id, await body(req));
    if (m === "DELETE") { await env.DB.prepare("delete from inquiries where id = ?").bind(id).run(); return { ok: true }; }
  }
  if (m === "PUT" && what === "settings") return putSettings(env, await body(req));
  if (what === "media") {
    if (m === "PUT") return upload(req, env, seg.slice(2).join("/"));
    if (m === "POST" && id === "delete") return removeMedia(env, await body(req));
  }
  if (m === "POST" && what === "publish") return publish(env, email);
  throw new Bad(404, "Няма такъв адрес.");
}

export default {
  async fetch(req, env, ctx) {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(req, env) });
    try {
      const out = await route(req, env, ctx);
      return out instanceof Response ? out : reply(req, env, 200, out);
    } catch (e) {
      if (e instanceof Bad) return reply(req, env, e.status, { error: e.message });
      console.log("error", e && e.stack || String(e));
      return reply(req, env, 500, { error: "Грешка на сървъра. Опитайте след малко." });
    }
  },
};
