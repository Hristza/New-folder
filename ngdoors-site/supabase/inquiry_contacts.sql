-- Separate contact details without rewriting existing inquiries or changing RLS.
begin;
alter table public.inquiries add column if not exists email text not null default '' check (length(email) <= 254);
alter table public.inquiries add column if not exists phone text not null default '' check (length(phone) <= 32);
notify pgrst, 'reload schema';
commit;
