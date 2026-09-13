-- اگر جدول inquiries ستون user_id ندارد این را در Supabase → SQL Editor اجرا کنید
alter table inquiries add column if not exists user_id uuid;
alter table inquiries add column if not exists payload jsonb;
alter table inquiries add column if not exists created_at timestamptz default now();

-- در صورت نیاز ایندکس
create index if not exists inquiries_user_id_idx on inquiries (user_id);
