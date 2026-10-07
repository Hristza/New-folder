-- Remove individual built-in photos without deleting shared catalogue assets.
-- Apply before deploying the corresponding admin panel and build.py.
create or replace function public.valid_excluded_images(j jsonb)
returns boolean language plpgsql immutable set search_path = public as $$
declare item jsonb;
begin
  if j is null or jsonb_typeof(j) <> 'array' then return false; end if;
  if jsonb_array_length(j) > 100 then return false; end if;
  for item in select value from jsonb_array_elements(j) loop
    if jsonb_typeof(item) <> 'string' or length(item #>> '{}') not between 1 and 2048 then
      return false;
    end if;
  end loop;
  return true;
end;
$$;
alter table public.product_overrides
  add column if not exists excluded_images jsonb not null default '[]'
  check (public.valid_excluded_images(excluded_images));
