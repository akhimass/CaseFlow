-- Caseflow schema: cases, documents, firms, matches

create extension if not exists "pgcrypto";

create table if not exists public.firms (
  id           text primary key,
  name         text not null,
  jurisdictions text[] not null default '{}',
  specialties  text[] not null default '{}',
  languages    text[] not null default '{}',
  phone        text,
  created_at   timestamptz not null default now()
);

create table if not exists public.cases (
  id              uuid primary key default gen_random_uuid(),
  caller_id       text not null,
  transcript      text not null default '',
  language        text,
  accident_type   text,
  jurisdiction    text,
  case_strength   integer,
  status          text not null default 'intake',
  intake_json     jsonb not null default '{}',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create table if not exists public.documents (
  id            uuid primary key default gen_random_uuid(),
  case_id       uuid not null references public.cases(id) on delete cascade,
  doc_type      text not null,
  parsed_fields jsonb not null default '{}',
  image_url     text,
  created_at    timestamptz not null default now()
);

create table if not exists public.matches (
  id         uuid primary key default gen_random_uuid(),
  case_id    uuid not null references public.cases(id) on delete cascade,
  firm_id    text not null references public.firms(id),
  score      integer,
  reasoning  text,
  status     text not null default 'pending',
  created_at timestamptz not null default now()
);

create index if not exists cases_caller_id_idx on public.cases (caller_id);
create index if not exists cases_updated_at_idx on public.cases (updated_at desc);
create index if not exists documents_case_id_idx on public.documents (case_id);
create index if not exists matches_case_id_idx on public.matches (case_id);

insert into public.firms (id, name, jurisdictions, specialties, languages, phone) values
  ('martinez', 'Martinez & Associates', array['CA'], array['auto','rear_end'], array['en','es'], '(714) 555-0142'),
  ('brennan', 'Brennan Law', array['CA'], array['motorcycle','auto'], array['en'], '(310) 555-0198'),
  ('reyes', 'Reyes Injury Law', array['CA'], array['slip_fall','premises'], array['en','es'], '(619) 555-0167'),
  ('patel', 'Patel Personal Injury', array['CA'], array['general_pi'], array['en','es','hi'], '(415) 555-0133'),
  ('cohen', 'Cohen Law Group', array['CA'], array['high_value'], array['en'], '(800) 555-0171')
on conflict (id) do nothing;
