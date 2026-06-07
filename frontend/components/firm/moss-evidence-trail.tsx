'use client';

import type { CaseRecord } from '@/hooks/useCaseflowEvents';

/**
 * Enhancement F — the Moss "evidence trail": every retrieval fired during the
 * call with its result count, latency, cache/error state, and whether Aria
 * actually cited it. Makes retrieval auditable ("retrieval is the new bottleneck").
 */

type Snippet = { id?: string };
type Retrieval = {
  namespace?: string;
  query?: string;
  results_count?: number;
  time_taken_ms?: number | null;
  timestamp?: number;
  seq?: number;
  cached?: boolean;
  error?: string | null;
  snippets?: Snippet[];
};
type Citation = { citation_id?: string; timestamp?: number; turn?: number };

const NS_DOT: Record<string, string> = {
  'state-law': 'bg-sky-500',
  settlements: 'bg-violet-500',
  firms: 'bg-emerald-500',
  procedures: 'bg-amber-500',
};

function fmtTime(ts?: number): string {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function MossEvidenceTrail({ record }: { record: CaseRecord }) {
  const retrievals = (record.moss_retrievals as Retrieval[] | undefined) ?? [];
  const citations = (record.moss_citations as Citation[] | undefined) ?? [];

  if (retrievals.length === 0) {
    return null;
  }

  const citedIds = new Set(citations.map((c) => c.citation_id).filter(Boolean) as string[]);
  const totalMs = retrievals.reduce((sum, r) => sum + (r.time_taken_ms ?? 0), 0);
  const errorCount = retrievals.filter((r) => r.error).length;

  // Newest first.
  const rows = [...retrievals].sort((a, b) => (b.seq ?? 0) - (a.seq ?? 0));

  return (
    <section className="border-border rounded-lg border p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
          Moss evidence trail
        </h3>
        <div className="text-muted-foreground/70 flex items-center gap-3 text-[10px] tabular-nums">
          <span>{retrievals.length} queries</span>
          <span>{citedIds.size} cited</span>
          <span>{Math.round(totalMs)} ms total</span>
          {errorCount > 0 ? <span className="text-red-600">{errorCount} errors</span> : null}
        </div>
      </div>

      <ol className="space-y-1.5">
        {rows.map((r, i) => {
          const cited = (r.snippets ?? []).some((s) => s.id && citedIds.has(s.id));
          return (
            <li
              key={`${r.seq ?? i}`}
              className="border-border grid grid-cols-[auto_1fr_auto] items-center gap-2 rounded border px-2 py-1.5 text-xs"
            >
              <div className="flex items-center gap-1.5">
                <span
                  className={`size-2 rounded-full ${NS_DOT[r.namespace ?? ''] ?? 'bg-muted-foreground'}`}
                />
                <span className="text-muted-foreground/60 tabular-nums">
                  {fmtTime(r.timestamp)}
                </span>
              </div>
              <div className="min-w-0">
                <span className="font-medium">{r.namespace}</span>
                <span className="text-muted-foreground ml-1.5 truncate">{r.query}</span>
              </div>
              <div className="flex items-center gap-1.5 justify-self-end tabular-nums">
                {r.error ? (
                  <span className="rounded-full bg-red-500/15 px-1.5 py-0.5 text-[9px] font-semibold text-red-600">
                    error
                  </span>
                ) : (
                  <span className="text-muted-foreground/70">{r.results_count ?? 0}×</span>
                )}
                {r.cached ? (
                  <span className="text-muted-foreground/50 text-[9px]">cached</span>
                ) : (
                  <span className="text-muted-foreground/70">
                    {Math.round(r.time_taken_ms ?? 0)}ms
                  </span>
                )}
                {cited ? (
                  <span className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-semibold text-amber-600">
                    ✓ cited
                  </span>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
