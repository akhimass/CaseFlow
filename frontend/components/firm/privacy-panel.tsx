'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { type CaseRecord } from '@/hooks/useCaseflowEvents';

type PrivacyStats = {
  redaction_count?: number;
  categories?: Record<string, number>;
  encryption?: string;
  sensitive_bucket?: string;
  consent_given_at?: string;
  stt_note?: string;
};

export function PrivacyPanel({
  record,
  revealed,
  onReveal,
}: {
  record: CaseRecord;
  revealed: boolean;
  onReveal: () => void;
}) {
  const stats = (record.privacy_stats as PrivacyStats | undefined) ?? {};
  const [auditCount, setAuditCount] = useState<number | null>(null);

  useEffect(() => {
    const caseId = String(record.case_id ?? '');
    if (!caseId) return;
    fetch(`/api/cases/${caseId}/privacy`)
      .then((r) => r.json())
      .then((data) => setAuditCount(data.audit_count ?? 0))
      .catch(() => setAuditCount(null));
  }, [record.case_id]);

  const categories = stats.categories ?? {};
  const categorySummary = Object.entries(categories)
    .filter(([, n]) => n > 0)
    .map(([k, n]) => `${k}: ${n}`)
    .join(' · ');

  return (
    <div className="border-border bg-card rounded-lg border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
            Privacy & data handling
          </div>
          <p className="text-muted-foreground mt-1 max-w-prose text-xs">
            Firm view is redacted by default. In production, revealing full details requires
            firm-side authentication; this button logs the access pattern for the demo.
          </p>
        </div>
        <Button
          variant={revealed ? 'secondary' : 'default'}
          size="sm"
          onClick={onReveal}
          disabled={revealed}
        >
          {revealed ? 'Full details revealed (audited)' : 'Reveal full case details'}
        </Button>
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-muted-foreground text-xs">PII redactions</dt>
          <dd className="font-semibold tabular-nums">
            {typeof stats.redaction_count === 'number' ? stats.redaction_count : '—'}
          </dd>
          {categorySummary ? (
            <dd className="text-muted-foreground mt-1 text-xs">{categorySummary}</dd>
          ) : null}
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">Encryption</dt>
          <dd className="font-medium">{stats.encryption ?? 'SSE-KMS'}</dd>
          <dd className="text-muted-foreground text-xs">
            Sensitive: {stats.sensitive_bucket ?? 'caseflow-sensitive'}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">Consent</dt>
          <dd className="font-medium">
            {String(stats.consent_given_at ?? record.consent_given_at ?? 'Pending')}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">Audit entries</dt>
          <dd className="font-semibold tabular-nums">{auditCount ?? '…'}</dd>
        </div>
      </dl>

      <p className="text-muted-foreground mt-3 text-xs">{stats.stt_note}</p>
      {record.pii_redacted !== false && !revealed && (
        <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">
          Operational store: redacted only. Unredacted data + mapping live in the sensitive S3
          prefix.
        </p>
      )}
    </div>
  );
}
