-- Email the owner on every new enquiry, via the ngdoors-notify Cloudflare worker (notify/worker.js).
-- The shared secret lives in Vault as 'notify_hook_secret'; set it once with
--   select vault.create_secret('<secret>', 'notify_hook_secret');
create extension if not exists pg_net;

create or replace function public.notify_new_inquiry() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  perform net.http_post(
    url     := 'https://ngdoors-notify.hristofor-georgiev-highschool.workers.dev',
    body    := jsonb_build_object('type', 'INSERT', 'record', to_jsonb(new)),
    headers := jsonb_build_object('content-type', 'application/json',
                 'x-hook-secret', (select decrypted_secret from vault.decrypted_secrets where name = 'notify_hook_secret')));
  return new;   -- ponytail: fire-and-forget; a failed email never blocks the enquiry being saved
end $$;
revoke all on function public.notify_new_inquiry() from public, anon, authenticated;

drop trigger if exists inquiries_notify on public.inquiries;
create trigger inquiries_notify after insert on public.inquiries
  for each row execute function public.notify_new_inquiry();
