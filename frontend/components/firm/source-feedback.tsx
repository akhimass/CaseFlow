'use client';

import { useState } from 'react';

/**
 * 👍/👎 on a Moss source (the learning loop). Posts a vote keyed by the cited
 * source id; the agent loads aggregated scores at the next call and re-ranks
 * retrieval so validated sources rise and unhelpful ones sink.
 */
export function SourceFeedback({
  sourceId,
  namespace,
  caseId,
}: {
  sourceId?: string;
  namespace?: string;
  caseId?: string;
}) {
  const [sent, setSent] = useState<null | boolean>(null);
  if (!sourceId) return null;

  async function vote(helpful: boolean) {
    setSent(helpful);
    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_id: sourceId, namespace, helpful, case_id: caseId }),
      });
    } catch {
      // best-effort; the loop tolerates dropped votes
    }
  }

  return (
    <span
      className="inline-flex items-center gap-0.5"
      title="Did this source help your assessment?"
    >
      <button
        type="button"
        aria-label="This source helped"
        onClick={() => vote(true)}
        className={`rounded px-1 leading-none transition-colors ${
          sent === true ? 'text-emerald-600' : 'text-muted-foreground/60 hover:text-emerald-600'
        }`}
      >
        👍
      </button>
      <button
        type="button"
        aria-label="This source did not help"
        onClick={() => vote(false)}
        className={`rounded px-1 leading-none transition-colors ${
          sent === false ? 'text-red-600' : 'text-muted-foreground/60 hover:text-red-600'
        }`}
      >
        👎
      </button>
      {sent !== null ? <span className="text-[9px] text-emerald-600/80">recorded</span> : null}
    </span>
  );
}
