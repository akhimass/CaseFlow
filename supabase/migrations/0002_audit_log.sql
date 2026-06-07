-- Gateway audit trail + transcript events

create table if not exists public.audit_log (
  id           uuid primary key default gen_random_uuid(),
  case_id      uuid references public.cases(id) on delete set null,
  event_type   text not null,
  actor        text,
  model_id     text,
  payload      jsonb not null default '{}',
  latency_ms   integer,
  cost_usd     numeric(10, 6),
  created_at   timestamptz not null default now()
);

create index if not exists audit_log_case_id_idx on public.audit_log (case_id);
create index if not exists audit_log_event_type_idx on public.audit_log (event_type);
create index if not exists audit_log_created_at_idx on public.audit_log (created_at desc);

-- Supabase Storage bucket for transcripts (create in dashboard if not exists):
-- caseflow-transcripts — private, agent uploads via service role
