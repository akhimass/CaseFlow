'use client';

import { Fragment, useEffect, useRef, useState } from 'react';
import type { CaseRecord } from '@/hooks/useCaseflowEvents';

const UPDATED_MS = 4000;

type CaseflowDecision = {
  synthesis?: string;
  confidence?: number;
  language?: string;
  citations?: string[];
  source?: string;
  status?: 'synthesizing' | 'ready' | 'error';
  seq?: number;
};

const CITE_RE = /\[cite:([^\]]+)\]/g;

// Human label per namespace — never render the raw technical id.
const NS_LABEL: Record<string, string> = {
  'state-law': 'state law',
  settlements: 'settlement',
  firms: 'firm',
  procedures: 'procedure',
};

const NS_STYLE: Record<string, string> = {
  'state-law': 'bg-sky-500/15 text-sky-600 hover:bg-sky-500/25',
  settlements: 'bg-violet-500/15 text-violet-600 hover:bg-violet-500/25',
  firms: 'bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/25',
  procedures: 'bg-amber-500/15 text-amber-700 hover:bg-amber-500/25',
};

function CiteBadge({ id }: { id: string }) {
  const namespace = id.split(':', 1)[0];
  const label = NS_LABEL[namespace] ?? 'source';
  const style = NS_STYLE[namespace] ?? 'bg-muted text-muted-foreground hover:bg-muted/70';
  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new CustomEvent('moss-cite', { detail: { id } }))}
      className={`mx-0.5 inline-flex items-center rounded-full px-1.5 py-0.5 align-middle text-[10px] font-semibold transition-colors ${style}`}
      title={`Jump to the ${label} that grounds this`}
    >
      ↗ {label}
    </button>
  );
}

function renderSynthesis(text: string) {
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  CITE_RE.lastIndex = 0;
  while ((match = CITE_RE.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(<Fragment key={key++}>{text.slice(last, match.index)}</Fragment>);
    }
    nodes.push(<CiteBadge key={key++} id={match[1].trim()} />);
    last = match.index + match[0].length;
  }
  if (last < text.length) {
    nodes.push(<Fragment key={key++}>{text.slice(last)}</Fragment>);
  }
  return nodes;
}

function confidenceStyle(confidence: number): string {
  if (confidence >= 70) return 'bg-emerald-500/15 text-emerald-600';
  if (confidence >= 40) return 'bg-amber-500/15 text-amber-700';
  return 'bg-red-500/15 text-red-600';
}

export function CaseflowDecisionCard({ record }: { record: CaseRecord }) {
  const decision = record.caseflow_decision as CaseflowDecision | undefined;
  const seq = decision?.seq ?? 0;
  const [now, setNow] = useState(() => Date.now());
  const [updatedAt, setUpdatedAt] = useState(0);
  const prevSeq = useRef<number>(0);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, []);

  // After the first decision, a higher seq means a re-synthesis landed.
  useEffect(() => {
    if (prevSeq.current && seq > prevSeq.current) {
      setUpdatedAt(Date.now());
    }
    prevSeq.current = seq;
  }, [seq]);

  if (!decision) return null;

  const status = decision.status ?? 'ready';
  const hasBody = Boolean(decision.synthesis);
  const synthesizing = status === 'synthesizing' && !hasBody;
  const recentlyUpdated = updatedAt > 0 && now - updatedAt < UPDATED_MS;

  return (
    <div className="caseflow-decision-in rounded-lg bg-gradient-to-r from-slate-800 to-amber-500 p-[1.5px]">
      <section className="bg-card rounded-[7px] p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold tracking-wide">Caseflow Decision</h3>
            {recentlyUpdated || (status === 'synthesizing' && hasBody) ? (
              <span className="rounded-full bg-sky-500/15 px-2 py-0.5 text-[10px] font-semibold text-sky-600">
                ↑ updated
              </span>
            ) : null}
          </div>
          {typeof decision.confidence === 'number' ? (
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums ${confidenceStyle(
                decision.confidence
              )}`}
            >
              {decision.confidence}% confidence
            </span>
          ) : null}
        </div>

        {synthesizing ? (
          <p className="text-muted-foreground animate-pulse text-sm">Synthesizing…</p>
        ) : status === 'error' && !hasBody ? (
          <p className="text-muted-foreground text-sm">
            Synthesis unavailable — see the four streams above.
          </p>
        ) : (
          <p
            key={decision.seq ?? 0}
            className="caseflow-decision-body-in text-sm leading-relaxed"
          >
            {renderSynthesis(decision.synthesis ?? '')}
          </p>
        )}
      </section>
    </div>
  );
}
