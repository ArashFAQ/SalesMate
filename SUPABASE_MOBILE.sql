-- SalesMate — جدول اسنپ‌شات برای اپ موبایل (فقط‌خواندنی)
-- یک‌بار در Supabase → SQL Editor → Run  (بعد از SUPABASE_HARDEN.sql)
--
-- ویندوز آمار پارکت، سمپل/استند و بالانس موجودی را اینجا می‌نویسد؛ موبایل فقط می‌خواند.

create table if not exists public.mobile_snapshots (
  key text primary key,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.mobile_snapshots enable row level security;

do $$
declare p record;
begin
  for p in select policyname from pg_policies where schemaname = 'public' and tablename = 'mobile_snapshots' loop
    execute format('drop policy %I on public.mobile_snapshots', p.policyname);
  end loop;
end $$;

revoke all on table public.mobile_snapshots from anon;
grant select, insert, update, delete on table public.mobile_snapshots to authenticated;

-- فقط کاربران مجاز (جدول allowed_users از SUPABASE_HARDEN.sql)
-- فقط مالک (آمار پارکت، سمپل/استند و بالانس فقط برای این ایمیل)
create policy "mobile_snapshots_owner_only" on public.mobile_snapshots
  for all to authenticated
  using (public.is_allowed() and lower(auth.jwt() ->> 'email') = 'arash.e.maleki@gmail.com')
  with check (public.is_allowed() and lower(auth.jwt() ->> 'email') = 'arash.e.maleki@gmail.com');
