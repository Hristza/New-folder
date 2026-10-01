-- Her own photo for a catalogue product (2026-10-02). Empty = the supplier's photos.
alter table public.product_overrides add column if not exists images jsonb not null default '[]'
  check (public.valid_photos(images));

-- Storage deletes return rows, so they need SELECT too. Without this policy
-- remove() reported success and deleted nothing (found 2026-10-02).
drop policy if exists "media admin select" on storage.objects;
create policy "media admin select" on storage.objects for select to authenticated
  using (bucket_id = 'media' and (select public.is_admin()));
