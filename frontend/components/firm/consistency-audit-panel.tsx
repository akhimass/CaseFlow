'use client';

import type { CaseRecord } from '@/hooks/useCaseflowEvents';

type SecondOpinion = {
  agrees?: boolean;
  confidence?: number;
  assessment?: string;
  model?: string;
  provider?: string;
};

type Audit = {
  conflict?: boolean;
  conflict_type?: string;
  reason?: string;
  clarifying_question?: string;
  source?: string;
  llm_provider?: string;
  llm_model?: string;
  failover?: boolean;
  second_opinion?: SecondOpinion;
};

export function ConsistencyAuditPanel({ record }: { record: CaseRecord }) {
  const audit = (record.consistency_audit ?? record) as Audit & CaseRecord;
  const hasConflict = Boolean(
    audit.conflict ??
      (record.last_event === 'discrepancy_found' || record.last_event === 'discrepancy_verified')
  );
  const secondOpinion =
    audit.second_opinion ?? ((record as Record<string, unknown>).second_opinion as SecondOpinion);

  if (!hasConflict && !audit.reason) {
    return (
      <section className="border-border rounded-lg border border-dashed p-4">
        <h3 className="text-muted-foreground mb-2 text-xs font-semibold tracking-wide uppercase">
          Consistency audit (Qwen)
        </h3>
        <p className="text-muted-foreground text-sm">No discrepancies flagged yet.</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-4">
      <h3 className="text-muted-foreground mb-2 text-xs font-semibold tracking-wide uppercase">
        Consistency audit (Qwen via TrueFoundry)
      </h3>
      <div className="space-y-2 text-sm">
        <p>
          <span className="font-medium">Conflict:</span> {hasConflict ? 'Detected' : 'None'}
        </p>
        {audit.conflict_type ? (
          <p>
            <span className="font-medium">Type:</span> {audit.conflict_type}
          </p>
        ) : null}
        {audit.reason ? (
          <p>
            <span className="font-medium">Reasoning:</span> {audit.reason}
          </p>
        ) : null}
        {audit.clarifying_question ? (
          <p className="border-border bg-background mt-2 rounded border p-3 italic">
            {audit.clarifying_question}
          </p>
        ) : null}
        {secondOpinion ? (
          <div className="border-border bg-background mt-2 rounded border p-3">
            <p className="text-muted-foreground mb-1 text-xs font-semibold tracking-wide uppercase">
              Independent second opinion (Claude · AWS Bedrock)
            </p>
            <p>
              <span className="font-medium">{secondOpinion.agrees ? 'Confirmed' : 'Disputed'}</span>
              {typeof secondOpinion.confidence === 'number'
                ? ` · ${Math.round(secondOpinion.confidence * 100)}% confidence`
                : ''}
            </p>
            {secondOpinion.assessment ? (
              <p className="text-muted-foreground mt-1">{secondOpinion.assessment}</p>
            ) : null}
          </div>
        ) : null}
        <p className="text-muted-foreground text-xs">
          Source: {audit.source ?? 'gateway'} · {audit.llm_model ?? 'qwen-max'}
          {audit.failover ? ' · failover' : ''}
        </p>
      </div>
    </section>
  );
}
