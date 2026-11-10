-- NG Doors admin backend on Cloudflare D1 (SQLite). Replaces the Supabase project,
-- which the free plan paused after a week without visits and took the panel down.
-- Safe to re-run: everything is create-if-missing.
--
-- Who can do what is decided in worker.js, not here: D1 has no row-level security.
--   anyone   reads the catalogue edits (GET /public-data, used by the build)
--            and sends an inquiry (POST /inquiry)
--   admins   everything else, with a session token from POST /auth/login
-- JSON columns hold text; worker.js validates them before every write.

create table if not exists admins (
  email      text primary key,
  pass_hash  text,                       -- null until she sets one through the emailed link
  created_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

create table if not exists sessions (
  token_hash text primary key,           -- sha-256 of the token; the token itself is never stored
  email      text not null references admins(email) on delete cascade,
  expires_at integer not null            -- unix ms
);

create table if not exists resets (
  token_hash text primary key,
  email      text not null references admins(email) on delete cascade,
  expires_at integer not null
);

create table if not exists login_fails (
  email text not null,
  at    integer not null
);
create index if not exists login_fails_at on login_fails (at);

-- One row per catalogue product she has touched. Prices are EURO, exactly as typed.
create table if not exists product_overrides (
  product_key     text primary key,
  price           real,
  old_price       real,
  hidden          integer not null default 0,
  badge           text,
  images          text not null default '[]',
  size_prices     text,                  -- null = inherit the catalogue sizes
  excluded_images text not null default '[]',
  updated_at      text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

create table if not exists products (
  id          text primary key,
  section     text not null,
  category    text,
  name        text not null,
  brand       text,
  description text,
  price       real not null default 0,
  old_price   real,
  sizes       text not null default '[]',
  size_prices text,
  images      text not null default '[]',
  badge       text,
  hidden      integer not null default 0,
  created_at  text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at  text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

create table if not exists project_photos (
  id         text primary key,
  album      text not null,
  photo      text not null,
  caption    text,
  hidden     integer not null default 0,
  created_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

create table if not exists settings (
  key        text primary key,
  value      text not null,
  updated_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

create table if not exists publish_log (
  id           integer primary key autoincrement,
  requested_by text,
  requested_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  ok           integer,
  detail       text
);

create table if not exists inquiries (
  id         text primary key,
  name       text not null,
  contact    text not null,
  topic      text,
  message    text,
  page       text,
  status     text not null default 'new',
  email      text not null default '',
  phone      text not null default '',
  created_at text not null default (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
create index if not exists inquiries_created on inquiries (created_at desc);
