-- NG Doors admin backend. Run once on a fresh Supabase project (SQL editor or
-- `supabase db query`). Safe to re-run: everything is create-if-missing or replace.
--
-- Who can do what:
--   anyone          reads the catalogue edits (the build and the public site need them)
--                   and inserts an inquiry through the contact form
--   admins          everything else; an admin is a row in public.admins
--   nobody          signs up: sign-ups are disabled in the dashboard, users are invited

-- ------------------------------------------------------------------ admins
create table if not exists public.admins (
  user_id    uuid primary key references auth.users on delete cascade,
  created_at timestamptz not null default now()
);
alter table public.admins enable row level security;
drop policy if exists "admins read self" on public.admins;
create policy "admins read self" on public.admins
  for select to authenticated using (user_id = (select auth.uid()));

create or replace function public.is_admin() returns boolean
  language sql stable security definer set search_path = ''
as $$ select exists (select 1 from public.admins where user_id = (select auth.uid())) $$;
revoke execute on function public.is_admin() from public;
grant execute on function public.is_admin() to anon, authenticated;

create or replace function public.touch() returns trigger
  language plpgsql set search_path = ''
as $$ begin new.updated_at = now(); return new; end $$;

-- ------------------------------------------------------------------ catalogue edits
-- One row per catalogue product she has touched. product_key is 'door:<id>' or
-- 'floor:<id>', the ids build.py already uses. Every price she enters is EURO, stored
-- exactly as typed; build.py converts to leva at the statutory rate. Storing leva
-- made a typed 250,50 € read back as 250,51 €.
create table if not exists public.product_overrides (
  product_key text primary key check (product_key ~ '^(door|floor):[A-Za-z0-9_-]{1,80}$'),
  price       numeric(10,2) check (price is null or (price >= 0 and price < 1000000)),
  old_price   numeric(10,2) check (old_price is null or (old_price > 0 and old_price < 1000000)),
  hidden      boolean not null default false,
  badge       text check (badge is null or badge in ('new', 'sale', 'hit')),
  updated_at  timestamptz not null default now()
);

-- One uploaded photo, as the panel stores it: the browser resizes before upload, so
-- the bucket holds a 600px and a 1200px copy and the site links them directly.
--   {"s": "<path of 600px copy>", "l": "<path of 1200px copy>", "w": <px>, "h": <px>}
create or replace function public.valid_photo(j jsonb) returns boolean
  language sql immutable set search_path = ''
-- coalesce: a missing key makes the AND chain NULL, not false, and NOT (NULL) let a
-- photo with no 'l' through valid_photos. Caught by supabase/test_schema.mjs.
as $$ select coalesce(jsonb_typeof(j) = 'object'
         and jsonb_typeof(j->'s') = 'string' and jsonb_typeof(j->'l') = 'string'
         and length(j->>'s') between 1 and 300 and length(j->>'l') between 1 and 300
         and jsonb_typeof(j->'w') = 'number' and jsonb_typeof(j->'h') = 'number'
         and (j->>'w')::numeric between 1 and 20000 and (j->>'h')::numeric between 1 and 20000, false) $$;

create or replace function public.valid_photos(j jsonb) returns boolean
  language sql immutable set search_path = ''
as $$ select jsonb_typeof(j) = 'array' and jsonb_array_length(j) <= 20
         and not exists (select 1 from jsonb_array_elements(j) e where public.valid_photo(e) is not true) $$;

-- Her own photo for a catalogue product (2026-10-02). Empty = the supplier's photos.
alter table public.product_overrides add column if not exists images jsonb not null default '[]'
  check (public.valid_photos(images));

-- Products she adds herself.
create table if not exists public.products (
  id          uuid primary key default gen_random_uuid(),
  section     text not null check (section in ('door', 'nastilki', 'granitogres', 'parvazi')),
  category    text check (category is null or length(category) <= 120),
  name        text not null check (length(btrim(name)) between 2 and 160),
  brand       text check (brand is null or length(brand) <= 80),
  description text check (description is null or length(description) <= 4000),
  price       numeric(10,2) not null default 0 check (price >= 0 and price < 1000000),
  old_price   numeric(10,2) check (old_price is null or (old_price > 0 and old_price < 1000000)),
  sizes       text[] not null default '{}' check (cardinality(sizes) <= 30),
  images      jsonb not null default '[]' check (public.valid_photos(images)),
  badge       text check (badge is null or badge in ('new', 'sale', 'hit')),
  hidden      boolean not null default false,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- Photos of finished jobs. album is the album's display name.
create table if not exists public.project_photos (
  id         uuid primary key default gen_random_uuid(),
  album      text not null check (length(btrim(album)) between 2 and 60),
  photo      jsonb not null check (public.valid_photo(photo)),
  caption    text check (caption is null or length(caption) <= 200),
  hidden     boolean not null default false,
  created_at timestamptz not null default now()
);

-- Site-wide values she can change: phone, email, hours, address, announcement.
create table if not exists public.settings (
  key        text primary key check (key in ('phone', 'email', 'hours', 'address', 'announcement')),
  value      text not null check (length(value) <= 300),
  updated_at timestamptz not null default now()
);

-- Every publish she asks for, so the dashboard can say when the site last changed.
create table if not exists public.publish_log (
  id           bigint generated always as identity primary key,
  requested_by uuid default auth.uid(),
  requested_at timestamptz not null default now(),
  ok           boolean,
  detail       text check (detail is null or length(detail) <= 500)
);

drop trigger if exists touch on public.product_overrides;
create trigger touch before update on public.product_overrides for each row execute function public.touch();
drop trigger if exists touch on public.products;
create trigger touch before update on public.products for each row execute function public.touch();
drop trigger if exists touch on public.settings;
create trigger touch before update on public.settings for each row execute function public.touch();

do $$
declare t text;
begin
  foreach t in array array['product_overrides', 'products', 'project_photos', 'settings'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists "public read" on public.%I', t);
    execute format('create policy "public read" on public.%I for select to anon, authenticated using (true)', t);
    execute format('drop policy if exists "admin write" on public.%I', t);
    execute format('create policy "admin write" on public.%I for all to authenticated
                    using ((select public.is_admin())) with check ((select public.is_admin()))', t);
  end loop;
end $$;

alter table public.publish_log enable row level security;
drop policy if exists "admin all" on public.publish_log;
create policy "admin all" on public.publish_log for all to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));

-- ------------------------------------------------------------------ inquiries
create table if not exists public.inquiries (
  id         uuid primary key default gen_random_uuid(),
  name       text not null check (length(btrim(name)) between 1 and 120),
  contact    text not null check (length(btrim(contact)) between 3 and 160),
  topic      text check (topic is null or length(topic) <= 80),
  message    text check (message is null or length(message) <= 4000),
  page       text check (page is null or length(page) <= 300),
  status     text not null default 'new' check (status in ('new', 'done')),
  created_at timestamptz not null default now()
);
create index if not exists inquiries_created on public.inquiries (created_at desc);
alter table public.inquiries enable row level security;

-- The public may only create a fresh, unhandled inquiry. It cannot read any back.
drop policy if exists "public insert" on public.inquiries;
create policy "public insert" on public.inquiries for insert to anon, authenticated
  with check (status = 'new');
drop policy if exists "admin all" on public.inquiries;
create policy "admin all" on public.inquiries for all to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));

-- Table-fill guard, NOT per-visitor abuse protection: it caps how fast the table can
-- grow (30 in ten minutes, far above what a door shop receives), so a script cannot
-- bury her inbox or the free-tier database. A determined flood can still use up the
-- 30 and block real visitors for ten minutes; the form then falls back to email.
-- Per-visitor limits need a captcha or an edge function, which is not built.
create or replace function public.inquiry_flood_guard() returns trigger
  language plpgsql security definer set search_path = ''
as $$
begin
  if (select count(*) from public.inquiries where created_at > now() - interval '10 minutes') >= 30 then
    raise exception 'too many inquiries, try again later' using errcode = 'P0001';
  end if;
  new.created_at = now();
  return new;
end $$;
drop trigger if exists flood_guard on public.inquiries;
create trigger flood_guard before insert on public.inquiries
  for each row execute function public.inquiry_flood_guard();

-- ------------------------------------------------------------------ storage
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('media', 'media', true, 10485760, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update set public = excluded.public,
  file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "media admin insert" on storage.objects;
create policy "media admin insert" on storage.objects for insert to authenticated
  with check (bucket_id = 'media' and (select public.is_admin()));
drop policy if exists "media admin update" on storage.objects;
create policy "media admin update" on storage.objects for update to authenticated
  using (bucket_id = 'media' and (select public.is_admin()));
-- Storage deletes return rows, so they need SELECT too. Without this policy
-- remove() reported success and deleted nothing (found 2026-10-02).
drop policy if exists "media admin select" on storage.objects;
create policy "media admin select" on storage.objects for select to authenticated
  using (bucket_id = 'media' and (select public.is_admin()));
drop policy if exists "media admin delete" on storage.objects;
create policy "media admin delete" on storage.objects for delete to authenticated
  using (bucket_id = 'media' and (select public.is_admin()));

-- Each size has its own exact euro price. NULL inherits the catalogue; [] removes sizes.
-- Existing prices, photos, accounts and row-level permissions are preserved.
create or replace function public.valid_size_prices(j jsonb) returns boolean
  language plpgsql immutable set search_path = ''
as $$
declare e jsonb; label text; amount numeric; labels text[] := '{}';
begin
  if j is null then return true; end if;
  if jsonb_typeof(j) <> 'array' then return false; end if;
  if jsonb_array_length(j) > 30 then return false; end if;
  for e in select value from jsonb_array_elements(j) loop
    if jsonb_typeof(e) <> 'object'
       or jsonb_typeof(e->'size') is distinct from 'string'
       or jsonb_typeof(e->'price') is distinct from 'number' then return false; end if;
    label := e->>'size'; amount := (e->>'price')::numeric;
    if length(label) not between 1 and 80 or label <> btrim(label)
       or label ~ '[[:cntrl:]]' or lower(label) = any(labels)
       or amount < 0 or amount >= 1000000 or amount <> round(amount, 2) then return false; end if;
    labels := array_append(labels, lower(label));
  end loop;
  return true;
end $$;

alter table public.product_overrides add column if not exists size_prices jsonb
  check (public.valid_size_prices(size_prices));
alter table public.products add column if not exists size_prices jsonb
  check (public.valid_size_prices(size_prices));
