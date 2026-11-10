// Drives the real Worker under `wrangler dev` (local D1 + R2) through every route the
// panel, the build and the contact form use. Fresh state each run. Run from api/:
//   node test_api.mjs
import { spawn, execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";
import assert from "node:assert/strict";

const state = mkdtempSync(join(tmpdir(), "ngapi-"));
const sh = (args) => execFileSync("npx", ["wrangler", ...args, "--persist-to", state], { shell: true, stdio: "pipe" });
sh(["d1", "execute", "ngdoors", "--local", "--file", "schema.sql"]);
sh(["d1", "execute", "ngdoors", "--local", "--file", "seed.sql"]);
const RESET = "test-reset-token-0123456789";
const hash = createHash("sha256").update(RESET).digest("base64url");
sh(["d1", "execute", "ngdoors", "--local", "--command",
    `"insert into resets (token_hash, email, expires_at) values ('${hash}', 'ngbuildings@abv.bg', ${Date.now() + 3600000})"`]);

let hookHits = 0;
const hook = createServer((q, r) => { hookHits++; r.end("{}"); });
await new Promise((ok) => hook.listen(0, "127.0.0.1", ok));
const port = 20000 + Math.floor(Math.random() * 20000);
const dev = spawn("npx", ["wrangler", "dev", "--port", String(port), "--persist-to", state,
  "--var", `DEPLOY_HOOK:http://127.0.0.1:${hook.address().port}/hook`], { shell: true, stdio: "pipe" });
let log = ""; dev.stdout.on("data", (d) => (log += d)); dev.stderr.on("data", (d) => (log += d));
const API = `http://127.0.0.1:${port}`;

async function call(method, path, body, tok, headers = {}) {
  const raw = body instanceof Uint8Array;
  const r = await fetch(API + path, { method, body: raw ? body : body && JSON.stringify(body),
    headers: { ...(raw ? {} : { "Content-Type": "application/json" }), ...(tok ? { Authorization: "Bearer " + tok } : {}), ...headers } });
  const t = await r.text(); let j; try { j = JSON.parse(t); } catch (_) { j = t; }
  return { s: r.status, j, h: r.headers };
}

let fail = 0;
async function t(name, fn) {
  try { await fn(); console.log("ok   " + name); } catch (e) { fail++; console.log("FAIL " + name + "\n     " + e.message); }
}

try {
  for (let i = 0; ; i++) {                       // wait until OUR server answers with OUR 404 body
    try { const r = await call("GET", "/nope"); if (r.s === 404 && r.j.error) break; } catch (_) {}
    if (i > 120) throw new Error("wrangler dev did not start:\n" + log);
    await new Promise((ok) => setTimeout(ok, 500));
  }
  let tok;
  await t("no password yet -> login refused", async () => {
    assert.equal((await call("POST", "/auth/login", { email: "ngbuildings@abv.bg", password: "" })).s, 401);
  });
  await t("admin route needs a session", async () => assert.equal((await call("GET", "/admin/data")).s, 401));
  await t("short password refused", async () => {
    assert.equal((await call("POST", "/auth/password", { token: RESET, password: "short" })).s, 400);
  });
  await t("reset link sets password and signs in", async () => {
    const r = await call("POST", "/auth/password", { token: RESET, password: "Vrata-2026-ok" });
    assert.equal(r.s, 200, JSON.stringify(r.j)); tok = r.j.token;
    assert.equal(r.j.email, "ngbuildings@abv.bg");
  });
  await t("reset link works once", async () => {
    assert.equal((await call("POST", "/auth/password", { token: RESET, password: "Vrata-2026-ok" })).s, 400);
  });
  await t("login with the new password", async () => {
    const r = await call("POST", "/auth/login", { email: " NGbuildings@abv.bg ", password: "Vrata-2026-ok" });
    assert.equal(r.s, 200); tok = r.j.token;
  });
  await t("reset request: same answer for stranger and admin", async () => {
    assert.deepEqual((await call("POST", "/auth/reset", { email: "x@y.bg" })).j, { ok: true });
    assert.deepEqual((await call("POST", "/auth/reset", { email: "hrisodim0@gmail.com" })).j, { ok: true });
  });
  await t("me", async () => assert.equal((await call("GET", "/admin/me", null, tok)).j.email, "ngbuildings@abv.bg"));
  await t("change password needs the current one", async () => {
    let r = await call("POST", "/auth/password", { current: "wrong-password", password: "Vrata-2027-ok" }, tok);
    assert.equal(r.s, 400); assert.match(r.j.error, /Сегашната/);
    r = await call("POST", "/auth/password", { current: "Vrata-2026-ok", password: "Vrata-2027-ok" }, tok);
    assert.equal(r.s, 200, JSON.stringify(r.j));
    assert.equal((await call("POST", "/auth/login", { email: "ngbuildings@abv.bg", password: "Vrata-2027-ok" })).s, 200);
  });
  await t("idle session: 7 days unused -> signed out, use pushes it out", async () => {
    const h = createHash("sha256").update(tok).digest("base64url");
    const q = (sql) => sh(["d1", "execute", "ngdoors", "--local", "--json", "--command", `"${sql}"`]).toString();
    q(`update sessions set expires_at = ${Date.now() + 86400000} where token_hash = '${h}'`);    // 6 days idle
    assert.equal((await call("GET", "/admin/me", null, tok)).s, 200);
    const left = JSON.parse(q(`select expires_at from sessions where token_hash = '${h}'`))[0].results[0].expires_at;
    assert.ok(left > Date.now() + 6.9 * 86400000, "use did not extend the session");
    q(`update sessions set expires_at = ${Date.now() - 1} where token_hash = '${h}'`);           // 7 days idle
    const r = await call("GET", "/admin/me", null, tok);
    assert.equal(r.s, 401); assert.match(r.j.error, /Влезте отново/);
    tok = (await call("POST", "/auth/login", { email: "ngbuildings@abv.bg", password: "Vrata-2027-ok" })).j.token;
  });
  await t("series prices: fixed or %, bad ones refused", async () => {
    const ok = JSON.stringify({ "входни-врати/x/серия-parkdoor": { price: 450 }, "входни-врати/y/серия-панел": { pct: -10 } });
    assert.equal((await call("PUT", "/admin/settings", { set: { series_prices: ok } }, tok)).s, 200);
    for (const bad of ["nope", "[]", '{"a":{"price":-1}}', '{"a":{"pct":0}}', '{"a":{"pct":500}}', '{"a":{"price":1,"pct":2}}'])
      assert.equal((await call("PUT", "/admin/settings", { set: { series_prices: bad } }, tok)).s, 400, bad);
    assert.equal((await call("PUT", "/admin/settings", { del: ["series_prices"] }, tok)).s, 200);
  });

  await t("override: partial upsert keeps the other fields", async () => {
    let r = await call("PUT", "/admin/overrides/door:abc-1", { price: 120.5, badge: "sale" }, tok);
    assert.equal(r.s, 200, JSON.stringify(r.j));
    r = await call("PUT", "/admin/overrides/door:abc-1", { hidden: true }, tok);
    assert.equal(r.j.price, 120.5); assert.equal(r.j.badge, "sale"); assert.equal(r.j.hidden, true);
    assert.deepEqual(r.j.images, []);
  });
  await t("override: bad values refused", async () => {
    assert.equal((await call("PUT", "/admin/overrides/door:abc-1", { price: 1.234 }, tok)).s, 400);
    assert.equal((await call("PUT", "/admin/overrides/door:abc-1", { badge: "free" }, tok)).s, 400);
    assert.equal((await call("PUT", "/admin/overrides/bad key", { price: 1 }, tok)).s, 400);
    assert.equal((await call("PUT", "/admin/overrides/door:abc-1",
      { size_prices: [{ size: "80", price: 1 }, { size: "80", price: 2 }] }, tok)).s, 400);
  });

  const path = "products/0f6c1a2b-3c4d-600.webp".replace("-600", "-5e6f-600");
  const big = "products/0f6c1a2b-3c4d-5e6f-1200.webp";
  await t("media: upload, serve, no overwrite, wrong type refused", async () => {
    const bytes = new Uint8Array([82, 73, 70, 70, 1, 2, 3, 4]);
    assert.equal((await call("PUT", "/admin/media/" + path, bytes, tok, { "Content-Type": "image/webp" })).s, 200);
    assert.equal((await call("PUT", "/admin/media/" + big, bytes, tok, { "Content-Type": "image/webp" })).s, 200);
    const g = await fetch(API + "/media/" + path);
    assert.equal(g.status, 200); assert.equal(g.headers.get("content-type"), "image/webp");
    assert.deepEqual(new Uint8Array(await g.arrayBuffer()), bytes);
    assert.equal((await call("PUT", "/admin/media/" + path, bytes, tok, { "Content-Type": "image/webp" })).s, 409);
    assert.equal((await call("PUT", "/admin/media/products/x.webp", bytes, tok, { "Content-Type": "image/webp" })).s, 400);
    assert.equal((await call("PUT", "/admin/media/" + big.replace("webp", "jpg"), bytes, tok, { "Content-Type": "image/webp" })).s, 400);
    assert.equal((await call("PUT", "/admin/media/" + path, bytes)).s, 401);
  });

  let pid;
  await t("product: create, edit, hidden ones stay off the public data", async () => {
    let r = await call("POST", "/admin/products", { section: "door", name: "Врата Тест", price: 199,
      images: [{ s: path, l: big, w: 600, h: 800 }], size_prices: [{ size: "80 см", price: 199 }] }, tok);
    assert.equal(r.s, 200, JSON.stringify(r.j)); pid = r.j.id;
    assert.equal(r.j.images[0].s, path); assert.equal(r.j.hidden, false);
    r = await call("PATCH", "/admin/products/" + pid, { old_price: 250 }, tok);
    assert.equal(r.j.old_price, 250); assert.equal(r.j.name, "Врата Тест");
    assert.equal((await call("POST", "/admin/products", { section: "door", name: "X" }, tok)).s, 400);
    assert.equal((await call("POST", "/admin/products", { section: "door", name: "Скрит", hidden: true }, tok)).s, 200);
  });
  await t("project photo + settings", async () => {
    let r = await call("POST", "/admin/photos", { album: "  Обект   София ", photo: { s: path, l: big, w: 600, h: 400 } }, tok);
    assert.equal(r.s, 200, JSON.stringify(r.j)); assert.equal(r.j.album, "Обект София");
    assert.equal((await call("PUT", "/admin/settings", { set: { phone: "+359 1" }, del: ["hours"] }, tok)).s, 200);
    assert.equal((await call("PUT", "/admin/settings", { set: { evil: "1" } }, tok)).s, 400);
  });
  await t("public data: what the build reads", async () => {
    const r = await call("GET", "/public-data");
    assert.equal(r.s, 200);
    assert.equal(r.j.overrides.length, 1); assert.equal(r.j.products.length, 1);
    assert.equal(r.j.products[0].name, "Врата Тест"); assert.equal(r.j.photos.length, 1);
    assert.deepEqual(r.j.settings, [{ key: "phone", value: "+359 1" }]);
    assert.equal(JSON.stringify(r.j).includes("inquir"), false);
  });

  await t("inquiry: public post, admin sees it and marks it done", async () => {
    let r = await call("POST", "/inquiry", { name: "Иван", contact: "i@x.bg / 0888", email: "i@x.bg", phone: "0888",
      topic: "Врати", message: "Здравейте", page: "/vrati/" });
    assert.equal(r.s, 200, JSON.stringify(r.j));
    assert.equal((await call("POST", "/inquiry", { name: "", contact: "abc" })).s, 400);
    const d = await call("GET", "/admin/data", null, tok);
    const q = d.j.inquiries[0]; assert.equal(q.name, "Иван"); assert.equal(q.status, "new");
    r = await call("PATCH", "/admin/inquiries/" + q.id, { status: "done" }, tok);
    assert.equal(r.j.status, "done");
    assert.equal((await call("DELETE", "/admin/inquiries/" + q.id, null, tok)).s, 200);
  });

  await t("publish calls the hook once, then throttles", async () => {
    const r = await call("POST", "/admin/publish", null, tok);
    assert.equal(r.s, 200, JSON.stringify(r.j)); assert.equal(hookHits, 1);
    assert.equal((await call("POST", "/admin/publish", null, tok)).s, 429); assert.equal(hookHits, 1);
    const d = await call("GET", "/admin/data", null, tok);
    assert.equal(d.j.lastPublish.ok, true); assert.equal(d.j.lastPublish.requested_by, "ngbuildings@abv.bg");
  });

  await t("delete product, photo media, override", async () => {
    assert.equal((await call("DELETE", "/admin/products/" + pid, null, tok)).s, 200);
    assert.equal((await call("POST", "/admin/media/delete", { paths: [path, big] }, tok)).s, 200);
    assert.equal((await fetch(API + "/media/" + path)).status, 404);
    assert.equal((await call("DELETE", "/admin/overrides/door:abc-1", null, tok)).s, 200);
  });

  await t("CORS: site origin echoed, stranger not", async () => {
    let r = await fetch(API + "/inquiry", { method: "OPTIONS", headers: { Origin: "https://ngdoors.pages.dev" } });
    assert.equal(r.headers.get("access-control-allow-origin"), "https://ngdoors.pages.dev");
    r = await fetch(API + "/inquiry", { method: "OPTIONS", headers: { Origin: "https://evil.example" } });
    assert.notEqual(r.headers.get("access-control-allow-origin"), "https://evil.example");
  });

  await t("logout kills the session", async () => {
    await call("POST", "/auth/logout", null, tok);
    assert.equal((await call("GET", "/admin/me", null, tok)).s, 401);
  });
  await t("five wrong passwords lock the address", async () => {
    for (let i = 0; i < 5; i++) assert.equal((await call("POST", "/auth/login", { email: "hrisodim0@gmail.com", password: "wrong-" + i })).s, 401);
    assert.equal((await call("POST", "/auth/login", { email: "hrisodim0@gmail.com", password: "x" })).s, 429);
  });
} finally {
  if (process.platform === "win32") execFileSync("taskkill", ["/pid", String(dev.pid), "/T", "/F"], { stdio: "ignore" });
  else dev.kill();
  hook.close();
  try { rmSync(state, { recursive: true, force: true }); } catch (_) {}
}
console.log(fail ? `\n${fail} FAILED` : "\nall passed");
if (fail) console.log(log.slice(-3000));
process.exit(fail ? 1 : 0);
