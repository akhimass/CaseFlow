#!/usr/bin/env bash
# Applies Caseflow schema to remote Supabase (requires database password).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REF="nhlosagycvihmnbeuyag"

if [[ -z "${SUPABASE_DB_PASSWORD:-}" ]]; then
  echo "Set SUPABASE_DB_PASSWORD, then re-run."
  echo "Or paste scripts/apply-supabase-schema.sql into Supabase Dashboard → SQL Editor."
  exit 1
fi

cat "$ROOT/supabase/migrations/0001_caseflow.sql" "$ROOT/supabase/migrations/0002_audit_log.sql" | \
  psql "postgresql://postgres.${REF}:${SUPABASE_DB_PASSWORD}@aws-0-us-west-1.pooler.supabase.com:6543/postgres"

echo "Schema applied."
