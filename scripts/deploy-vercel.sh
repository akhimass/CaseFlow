#!/usr/bin/env bash
# Deploy Caseflow frontend to Vercel under akhimass-projects (not akhi-chappidi-s-projects).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/frontend"
TEAM_SLUG="${VERCEL_TEAM_SLUG:-akhimass-projects}"
PROJECT_NAME="${VERCEL_PROJECT_NAME:-caseflow}"

echo "→ Checking Vercel scope (expect: ${TEAM_SLUG})..."
if ! vercel teams switch "$TEAM_SLUG" 2>/dev/null; then
  echo ""
  echo "Could not switch to ${TEAM_SLUG}."
  echo "Log in with your akhimass Vercel account, then re-run:"
  echo "  vercel login"
  echo "  VERCEL_TEAM_SLUG=${TEAM_SLUG} $0"
  exit 1
fi

cd "$FRONTEND"

if [[ ! -f .vercel/project.json ]]; then
  echo "→ Linking project ${PROJECT_NAME} on ${TEAM_SLUG}..."
  vercel link --yes --project "$PROJECT_NAME" --scope "$TEAM_SLUG"
fi

if [[ -f .env.local ]]; then
  echo "→ Syncing env vars from .env.local (production)..."
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    key="${line%%=*}"
    val="${line#*=}"
    [[ -z "$key" ]] && continue
    printf '%s' "$val" | vercel env add "$key" production --scope "$TEAM_SLUG" --force 2>/dev/null || true
  done < .env.local
fi

echo "→ Deploying to production..."
vercel deploy --prod --yes --scope "$TEAM_SLUG"
