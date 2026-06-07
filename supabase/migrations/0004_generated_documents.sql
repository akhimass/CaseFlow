-- Generated legal document metadata (bodies live in S3)

alter table public.documents
  add column if not exists s3_path_md text,
  add column if not exists s3_path_pdf text,
  add column if not exists generated_at timestamptz,
  add column if not exists audit_status text default 'pending',
  add column if not exists page_count integer,
  add column if not exists audit_confidence integer,
  add column if not exists flagged_claims jsonb default '[]';

create index if not exists documents_generated_at_idx on public.documents (generated_at desc);
create index if not exists documents_audit_status_idx on public.documents (audit_status);
