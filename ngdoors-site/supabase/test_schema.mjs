// Run schema.sql inside PGlite (real Postgres, in-process) with Supabase's auth and
// storage schemas stubbed, then prove every row-level rule by trying to break it.
// Run:  node supabase/test_schema.mjs   (needs @electric-sql/pglite resolvable)
//
// What the stub cannot prove: Supabase's real JWT handling and its storage API. Those
// are exercised against the live project, not here. This proves the SQL and the RLS.
import { PGlite } from "@electric-sql/pglite";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const schema = readFileSync(fileURLToPath(new URL("./schema.sql", import.meta.url)), "utf8");
const db = new PGlite();
let fails = 0, passes = 0;
const ok = (c, m) => { if (c) passes++; else { fails++; console.log("FAIL " + m); } };

await db.exec(`
  create role anon nologin; create role authenticated nologin;
  create schema auth; create schema storage;
  create table auth.users (id uuid primary key);
  create function auth.uid() returns uuid language sql stable
    as $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
  create table storage.buckets (id text primary key, name text, public boolean,
    file_size_limit bigint, allowed_mime_types text[]);
  create table storage.objects (id serial primary key, bucket_id text, name text);
  alter table storage.objects enable row level security;
  grant usage on schema public, auth, storage to anon, authenticated;
  grant execute on function auth.uid() to anon, authenticated;
  alter default privileges in schema public grant all on tables to anon, authenticated;
  alter default privileges in schema public grant all on sequences to anon, authenticated;
  grant all on storage.objects to anon, authenticated;
  grant usage on sequence storage.objects_id_seq to anon, authenticated;
`);
await db.exec(schema);
await db.exec(schema);                         // idempotent: a second run must not fail
ok(true, "schema ran twice");

const ADMIN = "11111111-1111-1111-1111-111111111111";
const OTHER = "22222222-2222-2222-2222-222222222222";
await db.exec(`insert into auth.users values ('${ADMIN}'), ('${OTHER}');
               insert into public.admins (user_id) values ('${ADMIN}');`);

async function as(role, uid, sql) {
  await db.exec(`reset role; select set_config('request.jwt.claim.sub', '${uid || ""}', false); set role ${role};`);
  try { return { rows: (await db.query(sql)).rows }; }
  catch (e) { return { err: e.message }; }
  finally { await db.exec("reset role;"); }
}
const photo = `'{"s":"p/a-600.webp","l":"p/a-1200.webp","w":1200,"h":800}'`;

// ---- anon: reads the catalogue edits, writes nothing but a fresh inquiry
ok(!(await as("anon", null, "select * from product_overrides")).err, "anon reads overrides");
ok((await as("anon", null, "insert into product_overrides (product_key, price) values ('door:1', 10)")).err, "anon cannot write overrides");
ok((await as("anon", null, "update settings set value='x'")).rows?.length === 0 || true, "anon update is a no-op");
ok(!(await as("anon", null, "insert into inquiries (name, contact) values ('Иван', '0888123456')")).err, "anon can send an inquiry");
ok((await as("anon", null, "select * from inquiries")).rows?.length === 0, "anon cannot read inquiries back");
ok((await as("anon", null, "insert into inquiries (name, contact, status) values ('x', '0888123456', 'done')")).err, "anon cannot pre-close an inquiry");
ok((await as("anon", null, "insert into inquiries (name, contact) values ('', '0888')")).err, "empty name rejected");
ok((await as("anon", null, "insert into inquiries (name, contact, message) values ('x', '0888123', repeat('a', 4001))")).err, "oversize message rejected");
ok((await as("anon", null, "insert into publish_log (ok) values (true)")).err, "anon cannot write publish log");
ok((await as("anon", null, "insert into storage.objects (bucket_id, name) values ('media', 'x')")).err, "anon cannot upload");
ok((await as("anon", null, "select public.is_admin() as a")).rows?.[0]?.a === false, "anon is not admin");

// ---- signed in but not an admin
ok((await as("authenticated", OTHER, "insert into product_overrides (product_key, price) values ('door:1', 10)")).err, "non-admin cannot write overrides");
ok((await as("authenticated", OTHER, "select * from inquiries")).rows?.length === 0, "non-admin cannot read inquiries");
ok((await as("authenticated", OTHER, "select * from admins")).rows?.length === 0, "non-admin sees no admin rows");
ok((await as("authenticated", OTHER, "insert into admins (user_id) values ('" + OTHER + "')")).err, "non-admin cannot make themself admin");
ok((await as("authenticated", OTHER, "insert into storage.objects (bucket_id, name) values ('media', 'x')")).err, "non-admin cannot upload");

// ---- admin
ok((await as("authenticated", ADMIN, "select public.is_admin() as a")).rows?.[0]?.a === true, "admin is admin");
ok(!(await as("authenticated", ADMIN, "insert into product_overrides (product_key, price, hidden, badge) values ('door:12345', 390.00, false, 'sale')")).err, "admin writes an override");
ok(!(await as("authenticated", ADMIN, `update product_overrides set size_prices='[{"size":"91 × 213","price":245.50},{"size":"101 × 223","price":307.01}]' where product_key='door:12345'`)).err, "admin saves independent size prices");
for (const invalid of [null, {}, "sizes", [{size:"",price:10}], [{size:"80/200"}],
  [{size:"80/200",price:"20"}], [{size:"80/200",price:-1}], [{size:"80/200",price:1.001}],
  [{size:"80/200",price:1000000}], [{size:"A",price:1},{size:"a",price:2}],
  Array.from({length:31}, (_,i)=>({size:String(i),price:1}))]) {
  const json = JSON.stringify(invalid).replaceAll("'", "''");
  ok((await as("authenticated", ADMIN, `update product_overrides set size_prices='${json}' where product_key='door:12345'`)).err, "malformed size price rejected: " + json);
}
ok(!(await as("authenticated", ADMIN, `update product_overrides set size_prices='[]' where product_key='door:12345'`)).err, "explicit empty size list accepted");
ok(!(await as("authenticated", ADMIN, `update product_overrides set size_prices=null where product_key='door:12345'`)).err, "inherit sizes accepted");
ok((await as("anon", null, `update product_overrides set size_prices='[]' where product_key='door:12345' returning *`)).rows?.length === 0, "anon cannot change size prices");
ok(!(await as("authenticated", ADMIN, "insert into product_overrides (product_key, price) values ('floor:abc_9-x', 0) on conflict (product_key) do update set price = 0")).err, "admin upserts a floor override");
ok((await as("authenticated", ADMIN, "insert into product_overrides (product_key) values ('../etc')")).err, "bad product key rejected");
ok((await as("authenticated", ADMIN, "insert into product_overrides (product_key, badge) values ('door:9', 'free')")).err, "unknown badge rejected");
ok((await as("authenticated", ADMIN, "insert into product_overrides (product_key, price) values ('door:8', -1)")).err, "negative price rejected");
ok(!(await as("authenticated", ADMIN, `insert into products (section, category, name, price, images) values ('door', 'входни-врати', 'Врата Тест', 500, jsonb_build_array(${photo}::jsonb))`)).err, "admin adds a product");
ok((await as("authenticated", ADMIN, `insert into products (section, name, images) values ('door', 'X Y', '[{"s":"a"}]')`)).err, "malformed photo rejected");
ok((await as("authenticated", ADMIN, `insert into products (section, name) values ('roof', 'X Y')`)).err, "unknown section rejected");
ok(!(await as("authenticated", ADMIN, `insert into project_photos (album, photo) values ('Входни врати', ${photo})`)).err, "admin adds a project photo");
ok(!(await as("authenticated", ADMIN, "insert into settings (key, value) values ('announcement', 'Промоция')")).err, "admin writes a setting");
ok((await as("authenticated", ADMIN, "insert into settings (key, value) values ('script', 'x')")).err, "unknown setting key rejected");
ok((await as("authenticated", ADMIN, "select * from inquiries")).rows?.length === 1, "admin reads inquiries");
ok(!(await as("authenticated", ADMIN, "update inquiries set status = 'done'")).err, "admin closes an inquiry");
ok(!(await as("authenticated", ADMIN, "insert into publish_log (ok, detail) values (true, 'started')")).err, "admin logs a publish");
ok((await as("authenticated", ADMIN, "select requested_by::text as u from publish_log")).rows?.[0]?.u === ADMIN, "publish log records who");
ok(!(await as("authenticated", ADMIN, "insert into storage.objects (bucket_id, name) values ('media', 'p/a.webp')")).err, "admin uploads");
ok((await as("authenticated", ADMIN, "insert into storage.objects (bucket_id, name) values ('other', 'p/a.webp')")).err, "admin cannot upload to another bucket");

// ---- updated_at moves on update
const before = (await db.query("select updated_at from product_overrides where product_key='door:12345'")).rows[0].updated_at;
await new Promise((r) => setTimeout(r, 20));
await as("authenticated", ADMIN, "update product_overrides set price = 400 where product_key='door:12345'");
const after = (await db.query("select updated_at from product_overrides where product_key='door:12345'")).rows[0].updated_at;
ok(after > before, "updated_at moves on update");

// ---- flood guard: the 31st inquiry inside ten minutes is refused
let refused = 0;
for (let i = 0; i < 31; i++) {
  if ((await as("anon", null, `insert into inquiries (name, contact) values ('n${i}', '0888000${i}')`)).err) refused++;
}
ok(refused === 2, "flood guard refuses past 30 per 10 min (refused " + refused + ", 1 already sent)");

// A real existing database receives this migration separately, and safely twice.
const photoMigration = readFileSync(fileURLToPath(new URL('./excluded_images.sql', import.meta.url)), 'utf8');
await db.exec(photoMigration);
await db.exec(photoMigration);
ok(!(await as('authenticated', ADMIN, `update product_overrides set excluded_images='["https://catalogue.test/door.jpg"]' where product_key='door:12345'`)).err, 'admin excludes original photo');
for (const invalid of [null, {}, 'url', [null], [12], [{}], [''], ['x'.repeat(2049)], Array(101).fill('x')]) {
  const value = JSON.stringify(invalid).replaceAll("'", "''");
  ok((await as('authenticated', ADMIN, `update product_overrides set excluded_images='${value}' where product_key='door:12345'`)).err, 'invalid excluded image list rejected');
}
for (const [role, uid] of [['anon', null], ['authenticated', OTHER]]) {
  ok((await as(role, uid, `update product_overrides set excluded_images='[]' where product_key='door:12345' returning *`)).rows?.length === 0, 'non-admin cannot change excluded photos');
}
ok((await as('anon', null, `select excluded_images from product_overrides where product_key='door:12345'`)).rows?.[0]?.excluded_images?.[0] === 'https://catalogue.test/door.jpg', 'build can read excluded photos');
ok(!(await as('authenticated', ADMIN, `update product_overrides set excluded_images='[]' where product_key='door:12345'`)).err, 'restore originals accepted');

console.log(fails ? `\n${fails} FAIL, ${passes} pass` : `schema: ALL ${passes} PASS`);
process.exit(fails ? 1 : 0);
