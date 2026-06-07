import * as React from 'react';
import type { MossContextEvent } from '@/hooks/useMossContextEvents';
import { cn } from '@/lib/shadcn/utils';

interface MossResultsPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  events: MossContextEvent[];
  hidden?: boolean;
}

const NS_LABEL: Record<string, string> = {
  'state-law': 'State law',
  settlements: 'Comparable settlements',
  firms: 'Matched firms',
  firm_leads: 'Matched firms',
  procedures: 'Guidance',
  memory: 'Case memory',
};

const NS_DOT: Record<string, string> = {
  'state-law': 'bg-sky-500',
  settlements: 'bg-violet-500',
  firms: 'bg-emerald-500',
  firm_leads: 'bg-emerald-500',
  procedures: 'bg-amber-500',
  memory: 'bg-slate-400',
};

type MossMeta = {
  title?: string;
  subtitle?: string;
  amount_range?: string;
  citation?: string;
  source_url?: string;
};

/** Split "[settlements] car crash ... CA settlement" into namespace + remainder. */
function parseNamespace(query: string): { ns: string; rest: string } {
  const m = query.match(/^\[([^\]]+)\]\s*(.*)$/);
  return m ? { ns: m[1], rest: m[2].trim() } : { ns: '', rest: query };
}

/** First sentence (or a word-boundary truncation) — never a mid-word cut. */
function concise(text: string, max = 140): string {
  const s = (text || '').trim();
  if (!s) return '';
  const end = s.search(/[.!?](\s|$)/);
  if (end > 0 && end + 1 <= max) return s.slice(0, end + 1);
  if (s.length <= max) return s;
  return s.slice(0, max).replace(/\s+\S*$/, '') + '…';
}

export function MossResultsPanel({
  events,
  hidden = false,
  className,
  ...props
}: MossResultsPanelProps) {
  // Keep only the latest retrieval per stream (the agent re-fires the same query
  // as the case evolves; showing every event is the "slop"). Newest first.
  const latest = new Map<string, MossContextEvent>();
  for (const ev of events) {
    const { ns } = parseNamespace(ev.query);
    const key = ns === 'firm_leads' ? 'firms' : ns || ev.query;
    const prev = latest.get(key);
    if (!prev || ev.timestamp > prev.timestamp) latest.set(key, ev);
  }
  const cards = [...latest.values()].sort((a, b) => b.timestamp - a.timestamp);

  if (hidden || cards.length === 0) {
    return null;
  }

  return (
    <div className={cn('space-y-3', className)} {...props}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
          Moss Intelligence
        </h3>
        <span className="text-muted-foreground text-[10px]">real-time retrieval</span>
      </div>

      <div className="space-y-2">
        {cards.map((ev) => {
          const { ns } = parseNamespace(ev.query);
          const isFit = ns === 'firms' || ns === 'firm_leads';
          return (
            <div
              key={ev.id}
              className="border-border bg-card text-card-foreground rounded-lg border p-3 shadow-sm"
            >
              <div className="mb-1.5 flex items-center gap-2">
                <span className={cn('size-2 rounded-full', NS_DOT[ns] ?? 'bg-muted-foreground')} />
                <span className="text-sm font-semibold">{NS_LABEL[ns] ?? ns ?? 'Knowledge'}</span>
                {typeof ev.timeTakenMs === 'number' && (
                  <span className="text-muted-foreground/70 text-[10px] tabular-nums">
                    {ev.timeTakenMs.toFixed(0)} ms
                  </span>
                )}
              </div>

              <ul className="space-y-1.5">
                {ev.matches.slice(0, 3).map((match, index) => {
                  const meta = (match.metadata ?? {}) as MossMeta;
                  const headline = meta.title || concise(match.text, 70);
                  const detailBits = [meta.subtitle, meta.amount_range].filter(Boolean) as string[];
                  const detail =
                    detailBits.length > 0
                      ? detailBits.join(' · ')
                      : meta.title
                        ? concise(match.text, 120)
                        : '';
                  const scoreLabel =
                    typeof match.score === 'number'
                      ? isFit
                        ? `fit ${Math.round(match.score)}`
                        : `${Math.round(Math.min(1, match.score) * 100)}%`
                      : '';
                  return (
                    <li key={`${ev.id}-${index}`} className="text-sm">
                      <div className="flex items-start justify-between gap-2">
                        <span className="leading-snug font-medium">{headline}</span>
                        {scoreLabel && (
                          <span className="text-muted-foreground/70 shrink-0 text-[10px] tabular-nums">
                            {scoreLabel}
                          </span>
                        )}
                      </div>
                      {detail && (
                        <p className="text-muted-foreground text-xs leading-snug">{detail}</p>
                      )}
                      {meta.citation && !meta.title?.includes(meta.citation) ? (
                        <p className="text-muted-foreground/70 font-mono text-[10px]">
                          {meta.citation}
                        </p>
                      ) : null}
                      {meta.source_url && (
                        <a
                          href={meta.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary text-[10px] hover:underline"
                        >
                          verify source ↗
                        </a>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}
