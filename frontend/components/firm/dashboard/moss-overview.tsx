'use client';

import type { CaseRecord } from '@/hooks/useCaseflowEvents';

type MossRetrieval = {
  namespace?: string;
  results_count?: number;
  time_taken_ms?: number | null;
};

const NAMESPACES: Array<{ key: string; label: string; dot: string }> = [
  { key: 'state-law', label: 'State law', dot: 'bg-sky-500' },
  { key: 'settlements', label: 'Settlements', dot: 'bg-violet-500' },
  { key: 'firms', label: 'Firm matches', dot: 'bg-emerald-500' },
  { key: 'procedures', label: 'Procedures', dot: 'bg-amber-500' },
];

/** Quick-read summary tiles for the four Moss retrieval streams. */
export function MossOverview({ record }: { record: CaseRecord }) {
  const retrievals = (record.moss_retrievals as MossRetrieval[] | undefined) ?? [];
  const byNs = new Map<string, MossRetrieval>();
  for (const r of retrievals) if (r.namespace) byNs.set(r.namespace, r);

  const totalResults = retrievals.reduce((s, r) => s + (r.results_count ?? 0), 0);
  const avgLatency =
    retrievals.length > 0
      ? Math.round(retrievals.reduce((s, r) => s + (r.time_taken_ms ?? 0), 0) / retrievals.length)
      : 0;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {NAMESPACES.map((ns) => {
        const r = byNs.get(ns.key);
        const active = (r?.results_count ?? 0) > 0;
        return (
          <div key={ns.key} className="border-border bg-background rounded-xl border p-4">
            <div className="flex items-center gap-2">
              <span
                className={`size-2 rounded-full ${active ? ns.dot : 'bg-muted-foreground/30'}`}
              />
              <span className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
                {ns.label}
              </span>
            </div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">{r?.results_count ?? 0}</div>
            <div className="text-muted-foreground/80 text-xs">
              {r?.time_taken_ms != null ? `${Math.round(r.time_taken_ms)} ms` : 'idle'}
            </div>
          </div>
        );
      })}
      <p className="text-muted-foreground col-span-2 text-xs sm:col-span-4">
        {totalResults} sources retrieved across 4 namespaces · avg {avgLatency} ms per stream
      </p>
    </div>
  );
}
