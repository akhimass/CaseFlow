-- Lawyer feedback on Moss sources — the Caseflow learning loop.
-- Each row is one helpful / not-helpful vote on a cited source (namespace:docid),
-- aggregated into a per-source net score that re-ranks future retrieval.
create table if not exists public.source_feedback (
  id uuid primary key default gen_random_uuid(),
  source_id text not null,
  namespace text,
  helpful boolean not null,
  case_id uuid,
  firm_id text,
  note text,
  created_at timestamptz not null default now()
);

create index if not exists source_feedback_source_id_idx on public.source_feedback (source_id);
create index if not exists source_feedback_created_at_idx on public.source_feedback (created_at desc);
create index if not exists source_feedback_firm_id_idx on public.source_feedback (firm_id);
