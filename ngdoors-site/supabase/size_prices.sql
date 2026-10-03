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
