-- Privacy layer: redaction flags, sensitive blob pointer, consent, privacy stats

alter table public.cases
  add column if not exists pii_redacted boolean not null default true,
  add column if not exists sensitive_blob_url text,
  add column if not exists consent_given_at timestamptz,
  add column if not exists privacy_stats jsonb not null default '{}';

create index if not exists cases_consent_given_at_idx on public.cases (consent_given_at desc);
