-- Additional Feature 1 - Nurse Console
-- ALREADY APPLIED to Supabase project whgkrdzoicepntnxtuab on 2026-09-29.
-- Kept here for reference / re-creating the database.

create table if not exists public.nurses (
  id uuid primary key default gen_random_uuid(),
  nurse_code text not null unique check (nurse_code ~ '^N[0-9]{6}$'),
  name text,
  created_at timestamptz not null default now()
);

create table if not exists public.qr_scan_logs (
  id uuid primary key default gen_random_uuid(),
  nurse_id uuid references public.nurses(id),
  nurse_code text,
  patient_id text not null,
  patient_name text,
  expected_qr_uuid uuid,
  scanned_value text not null,
  matched boolean not null,
  scan_method text not null check (scan_method in ('phone_camera','pi_camera')),
  scanned_at timestamptz not null default now()
);

create table if not exists public.medication_administrations (
  id uuid primary key default gen_random_uuid(),
  nurse_id uuid references public.nurses(id),
  nurse_code text,
  patient_id text not null,
  patient_name text,
  prescription_id uuid,
  verification_id uuid,
  medicine_index integer,
  medicine_name text,
  dose text,
  unit text,
  route text,
  frequency text,
  qr_scan_log_id uuid references public.qr_scan_logs(id),
  scanned_qr_uuid text,
  scan_method text,
  administered_at timestamptz not null default now()
);

create index if not exists idx_qr_scan_logs_patient on public.qr_scan_logs(patient_id, scanned_at desc);
create index if not exists idx_med_admin_patient on public.medication_administrations(patient_id, administered_at desc);

alter table public.nurses enable row level security;
alter table public.qr_scan_logs enable row level security;
alter table public.medication_administrations enable row level security;

create policy "nurses read" on public.nurses for select to anon, authenticated using (true);
create policy "scan logs read" on public.qr_scan_logs for select to anon, authenticated using (true);
create policy "scan logs insert" on public.qr_scan_logs for insert to anon, authenticated with check (true);
create policy "admin read" on public.medication_administrations for select to anon, authenticated using (true);
create policy "admin insert" on public.medication_administrations for insert to anon, authenticated with check (true);

insert into public.nurses (nurse_code, name) values ('N123456', 'Test Nurse')
on conflict (nurse_code) do nothing;

-- Add more nurses:
-- insert into public.nurses (nurse_code, name) values ('N654321', 'Nurse Aina');
