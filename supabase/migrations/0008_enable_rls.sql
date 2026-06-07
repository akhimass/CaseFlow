-- Enable Row Level Security on every Caseflow public table.
--
-- Access model: the Caseflow app reaches Postgres ONLY through the service role
-- — the Next.js API routes via supabaseAdmin() and the Python agent via the REST
-- service key. The service role bypasses RLS, and the app has no Supabase Auth
-- users (firm login is a custom signed cookie, not auth.users).
--
-- Therefore we enable RLS with NO permissive policies: the public Data API
-- (anon / authenticated roles) gets zero access to these tables, while the
-- server keeps full access. This closes the "RLS disabled in public" exposure
-- without changing app behavior. If a table ever needs browser access, add a
-- narrowly-scoped policy at that point rather than loosening this default.

alter table public.cases enable row level security;
alter table public.documents enable row level security;
alter table public.matches enable row level security;
alter table public.firms enable row level security;
alter table public.audit_log enable row level security;
alter table public.source_feedback enable row level security;

-- Defense in depth: revoke the broad table grants PostgREST hands the anon /
-- authenticated roles, so the Data API surface for these tables is empty even
-- before RLS policy evaluation.
revoke all on public.cases from anon, authenticated;
revoke all on public.documents from anon, authenticated;
revoke all on public.matches from anon, authenticated;
revoke all on public.firms from anon, authenticated;
revoke all on public.audit_log from anon, authenticated;
revoke all on public.source_feedback from anon, authenticated;

-- Lock down legacy SECURITY DEFINER helper functions so signed-in users can't
-- invoke them through PostgREST RPC. The current Caseflow app never calls these.
do $$
begin
  if to_regprocedure('public.current_firm_phone()') is not null then
    execute 'revoke all on function public.current_firm_phone() from anon, authenticated';
  end if;
  if to_regprocedure('public.is_admin()') is not null then
    execute 'revoke all on function public.is_admin() from anon, authenticated';
  end if;
end $$;
