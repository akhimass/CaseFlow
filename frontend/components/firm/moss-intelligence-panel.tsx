'use client';

import { useEffect, useRef, useState } from 'react';
import type { CaseRecord } from '@/hooks/useCaseflowEvents';

/** One retrieved snippet card pushed by the agent's Retriever. */
type MossSnippet = {
  id?: string;
  title?: string;
  subtitle?: string;
  text?: string;
  score?: number | null;
  citation?: string;
  amount_range?: string;
  reasons?: string[];
  phone?: string;
};

/** One Moss retrieval event (a stream firing once). */
type MossRetrieval = {
  namespace?: string;
  query?: string;
  results_count?: number;
  time_taken_ms?: number | null;
  /** epoch seconds */
  timestamp?: number;
  seq?: number;
  cached?: boolean;
  error?: string | null;
  snippets?: Array<MossSnippet | string>;
};

type CitedSource = { citation_id?: string; timestamp?: number; seq?: number };

const SECTIONS: Array<{ key: string; label: string; accent: string }> = [
  { key: 'state-law', label: 'State Law', accent: 'bg-sky-500' },
  { key: 'settlements', label: 'Comparable Settlements', accent: 'bg-violet-500' },
  { key: 'firms', label: 'Firm Matches', accent: 'bg-emerald-500' },
  { key: 'procedures', label: 'Procedural Guidance', accent: 'bg-amber-500' },
];

const LIVE_WINDOW_MS = 4000;
const PULSE_MS = 3000;
const REFINED_MS = 4000;

function normalizeSnippet(snippet: MossSnippet | string): MossSnippet {
  return typeof snippet === 'string' ? { text: snippet } : snippet;
}

/**
 * Derive a human-readable source reference from a citation id of the form
 * `namespace:doc-id` (e.g. `settlements:ca-rear-end-high-clear`). This is the
 * underlying comparable case / statute / firm record the snippet was retrieved
 * from — surfaced as a clickable "case link" so the lawyer can trace provenance.
 */
function deriveSource(id?: string): { label: string; docId: string } | null {
  if (!id || !id.includes(':')) return null;
  const docId = id.slice(id.indexOf(':') + 1);
  if (!docId) return null;
  const label = docId.replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  return { label, docId };
}

function formatScore(score?: number | null): string | null {
  if (score === null || score === undefined || Number.isNaN(score)) return null;
  const pct = score <= 1 ? Math.round(score * 100) : Math.round(score);
  return `${pct}%`;
}

function formatTime(ts?: number): string {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function SnippetCard({
  snippet,
  index,
  citedAt,
  now,
}: {
  snippet: MossSnippet;
  index: number;
  citedAt?: number;
  now: number;
}) {
  const score = formatScore(snippet.score);
  const title = snippet.title ?? snippet.amount_range ?? `Result ${index + 1}`;
  const cited = citedAt !== undefined && now - citedAt < PULSE_MS;
  const source = deriveSource(snippet.id);

  return (
    <div
      data-citation-id={snippet.id}
      // key on citedAt so re-citing restarts the CSS animation (no queue).
      key={cited ? citedAt : 'idle'}
      className={`border-border bg-card rounded-md border p-3 transition-[outline-color,box-shadow] ${
        cited ? 'caseflow-cite-pulse' : ''
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="text-sm font-medium">{title}</div>
        <div className="flex shrink-0 items-center gap-2">
          {cited ? (
            <span className="caseflow-cite-pill rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-600">
              ← cited just now
            </span>
          ) : null}
          {score ? (
            <span className="text-primary text-xs font-semibold tabular-nums transition-all duration-500">
              {score}
            </span>
          ) : null}
        </div>
      </div>
      {snippet.subtitle ? (
        <div className="text-muted-foreground mt-0.5 text-xs">{snippet.subtitle}</div>
      ) : null}
      {snippet.amount_range && snippet.title ? (
        <div className="mt-1 text-sm font-semibold tabular-nums">{snippet.amount_range}</div>
      ) : null}
      {snippet.text ? (
        <p className="text-muted-foreground mt-1 line-clamp-4 text-xs leading-relaxed">
          {snippet.text}
        </p>
      ) : null}
      {snippet.reasons && snippet.reasons.length > 0 ? (
        <ul className="text-muted-foreground mt-1.5 space-y-0.5 text-xs">
          {snippet.reasons.map((reason, i) => (
            <li key={i} className="before:text-primary before:mr-1 before:content-['•']">
              {reason}
            </li>
          ))}
        </ul>
      ) : null}
      {snippet.citation || snippet.phone || source ? (
        <div className="text-muted-foreground/70 mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px]">
          {snippet.citation ? <span className="font-mono">{snippet.citation}</span> : null}
          {snippet.phone ? <span>{snippet.phone}</span> : null}
          {source ? (
            <button
              type="button"
              title={`Source record: ${source.docId}`}
              onClick={() => {
                if (snippet.id) {
                  window.dispatchEvent(
                    new CustomEvent('moss-cite', { detail: { id: snippet.id } })
                  );
                }
              }}
              className="border-border/70 text-muted-foreground hover:border-primary hover:text-primary inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 font-mono transition-colors"
            >
              <span aria-hidden>↗</span>
              {source.docId}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function StreamSection({
  label,
  accent,
  retrieval,
  citedAt,
  refinedAt,
  now,
}: {
  label: string;
  accent: string;
  retrieval?: MossRetrieval;
  citedAt: Record<string, number>;
  refinedAt?: number;
  now: number;
}) {
  const snippets = (retrieval?.snippets ?? []).map(normalizeSnippet);
  const isLive =
    retrieval?.timestamp !== undefined && now - retrieval.timestamp * 1000 < LIVE_WINDOW_MS;
  const refined = refinedAt !== undefined && now - refinedAt < REFINED_MS;

  return (
    <div className="border-border rounded-lg border p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={`size-2 rounded-full ${accent} ${isLive ? 'animate-pulse' : 'opacity-30'}`}
          />
          <h4 className="text-sm font-semibold">{label}</h4>
          {retrieval?.results_count ? (
            <span className="text-muted-foreground text-xs tabular-nums">
              {retrieval.results_count}
            </span>
          ) : null}
          {refined ? (
            <span className="caseflow-cite-pill rounded-full bg-sky-500/15 px-2 py-0.5 text-[10px] font-semibold text-sky-600">
              ↑ refined
            </span>
          ) : null}
          {retrieval?.cached ? (
            <span className="bg-muted text-muted-foreground rounded-full px-2 py-0.5 text-[10px] font-medium">
              cached
            </span>
          ) : null}
        </div>
        {retrieval ? (
          <div className="text-muted-foreground/70 flex items-center gap-2 text-[10px] tabular-nums">
            {retrieval.time_taken_ms != null ? (
              <span>{Math.round(retrieval.time_taken_ms)} ms</span>
            ) : null}
            <span>{formatTime(retrieval.timestamp)}</span>
          </div>
        ) : null}
      </div>

      {retrieval?.error ? (
        <p className="rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-600">
          Retrieval failed: {retrieval.error}
        </p>
      ) : snippets.length === 0 ? (
        <p className="text-muted-foreground/70 text-xs">Awaiting retrieval…</p>
      ) : (
        <div className="space-y-2">
          {snippets.map((snippet, i) => (
            <SnippetCard
              key={`${snippet.id ?? i}`}
              snippet={snippet}
              index={i}
              citedAt={snippet.id ? citedAt[snippet.id] : undefined}
              now={now}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function MossIntelligencePanel({ record }: { record: CaseRecord }) {
  const [now, setNow] = useState(() => Date.now());
  const [citedAt, setCitedAt] = useState<Record<string, number>>({});
  const [refinedAt, setRefinedAt] = useState<Record<string, number>>({});

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, []);

  // Pulse a card when Aria cites it (SSE-driven cited_source).
  const cited = record.cited_source as CitedSource | undefined;
  useEffect(() => {
    if (cited?.citation_id) {
      const id = cited.citation_id;
      setCitedAt((prev) => ({ ...prev, [id]: Date.now() }));
    }
    // Re-run whenever a new citation arrives (seq/timestamp change).
  }, [cited?.seq, cited?.timestamp, cited?.citation_id]);

  // Pulse a card when a citation badge in the Decision card is clicked.
  useEffect(() => {
    function onCite(e: Event) {
      const id = (e as CustomEvent<{ id?: string }>).detail?.id;
      if (!id) return;
      setCitedAt((prev) => ({ ...prev, [id]: Date.now() }));
      document
        .querySelector(`[data-citation-id="${id}"]`)
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    window.addEventListener('moss-cite', onCite as EventListener);
    return () => window.removeEventListener('moss-cite', onCite as EventListener);
  }, []);

  // Normalize incoming retrievals (supports the legacy single `moss_retrieval`).
  const retrievals = ((record.moss_retrievals as MossRetrieval[] | undefined) ??
    (record.moss_retrieval ? [record.moss_retrieval as MossRetrieval] : [])) as MossRetrieval[];

  // Keep the most recent retrieval per namespace for its card section.
  const latestByNamespace = new Map<string, MossRetrieval>();
  for (const retrieval of retrievals) {
    if (retrieval?.namespace) latestByNamespace.set(retrieval.namespace, retrieval);
  }

  // Detect a "refined" namespace: top result id changed since the last render.
  const prevTopRef = useRef<Record<string, string | undefined>>({});
  useEffect(() => {
    const updates: Record<string, number> = {};
    for (const [ns, r] of latestByNamespace) {
      const first = (r.snippets ?? [])[0];
      const topId = typeof first === 'object' ? first?.id : undefined;
      const prevTop = prevTopRef.current[ns];
      if (prevTop !== undefined && topId !== undefined && topId !== prevTop) {
        updates[ns] = Date.now();
      }
      prevTopRef.current[ns] = topId;
    }
    if (Object.keys(updates).length) {
      setRefinedAt((prev) => ({ ...prev, ...updates }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [retrievals]);

  const anyLive = retrievals.some(
    (r) => r.timestamp !== undefined && now - r.timestamp * 1000 < LIVE_WINDOW_MS
  );

  return (
    <section className="border-border rounded-lg border p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
          Moss Intelligence
        </h3>
        <div className="flex items-center gap-1.5">
          <span
            className={`size-2 rounded-full ${anyLive ? 'animate-pulse bg-emerald-500' : 'bg-muted-foreground/30'}`}
          />
          <span className="text-muted-foreground text-[10px] tracking-wide uppercase">
            {anyLive ? 'Retrieving' : 'Idle'}
          </span>
        </div>
      </div>

      {retrievals.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          Four Moss streams — state law, comparable settlements, firm matches, and procedural
          guidance — will fire here as the agent learns the case.
        </p>
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {SECTIONS.map((section) => (
            <StreamSection
              key={section.key}
              label={section.label}
              accent={section.accent}
              retrieval={latestByNamespace.get(section.key)}
              citedAt={citedAt}
              refinedAt={refinedAt[section.key]}
              now={now}
            />
          ))}
        </div>
      )}
    </section>
  );
}
