'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import type { CaseRecord } from '@/hooks/useCaseflowEvents';
import { BarMeter, DashboardSection, StatTile } from './viz';

type AuditMetrics = {
  totalCalls: number;
  totalFailovers: number;
  totalTtsAudits?: number;
  totalCostUsd: number;
  qualityChecks: number;
  latencyByModel: Record<string, { count: number; avgLatencyMs: number }>;
};

type PrivacyStats = {
  redaction_count?: number;
  categories?: Record<string, number>;
  encryption?: string;
  sensitive_bucket?: string;
  consent_given_at?: string;
  stt_note?: string;
};

const CATEGORY_LABELS: Record<string, string> = {
  name: 'Names',
  phone: 'Phone numbers',
  address: 'Addresses',
  email: 'Emails',
  dob: 'Dates of birth',
  ssn_partial: 'SSN (partial)',
  plate: 'License plates',
};

export function TrueFoundryPrivacyDashboard({
  record,
  revealed,
  onReveal,
}: {
  record: CaseRecord;
  revealed: boolean;
  onReveal: () => void;
}) {
  const [metrics, setMetrics] = useState<AuditMetrics | null>(null);
  const [auditCount, setAuditCount] = useState<number | null>(null);

  useEffect(() => {
    const load = () =>
      fetch('/api/audit')
        .then((r) => r.json())
        .then((d) => setMetrics(d.metrics ?? null))
        .catch(() => setMetrics(null));
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const caseId = String(record.case_id ?? '');
    if (!caseId) return;
    fetch(`/api/cases/${caseId}/privacy`)
      .then((r) => r.json())
      .then((d) => setAuditCount(d.audit_count ?? 0))
      .catch(() => setAuditCount(null));
  }, [record.case_id]);

  const stats = (record.privacy_stats as PrivacyStats | undefined) ?? {};
  const categories = Object.entries(stats.categories ?? {}).filter(([, n]) => n > 0);
  const maxCat = Math.max(1, ...categories.map(([, n]) => n));
  const latency = Object.entries(metrics?.latencyByModel ?? {});
  const maxLatency = Math.max(1, ...latency.map(([, s]) => s.avgLatencyMs));

  return (
    <DashboardSection
      eyebrow="TrueFoundry · gateway"
      title="Privacy & gateway metrics"
      description="Every model call is routed and audited through the TrueFoundry gateway. PII is redacted before it ever reaches a model — the firm view stays redacted until access is explicitly logged."
      right={
        <Button
          variant={revealed ? 'secondary' : 'default'}
          size="sm"
          onClick={onReveal}
          disabled={revealed}
        >
          {revealed ? 'Revealed (audited)' : 'Reveal full details'}
        </Button>
      }
    >
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatTile value={metrics?.totalCalls ?? 0} label="Gateway calls" tone="accent" />
        <StatTile
          value={metrics?.totalFailovers ?? 0}
          label="Failovers"
          tone={(metrics?.totalFailovers ?? 0) > 0 ? 'warn' : 'good'}
        />
        <StatTile value={metrics?.totalTtsAudits ?? 0} label="MiniMax TTS audits" />
        <StatTile value={`$${(metrics?.totalCostUsd ?? 0).toFixed(3)}`} label="Est. cost" />
        <StatTile value={metrics?.qualityChecks ?? 0} label="Quality checks" />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div className="border-border bg-background rounded-xl border p-4">
          <div className="flex items-baseline justify-between">
            <h3 className="text-sm font-semibold">PII redaction</h3>
            <span className="text-primary text-2xl font-bold tabular-nums">
              {stats.redaction_count ?? 0}
            </span>
          </div>
          <p className="text-muted-foreground mt-0.5 text-xs">
            Identifiers removed before persistence & gateway calls
          </p>
          <div className="mt-3 space-y-2.5">
            {categories.length === 0 ? (
              <p className="text-muted-foreground text-sm">No redactions recorded for this case.</p>
            ) : (
              categories.map(([key, n]) => (
                <BarMeter
                  key={key}
                  label={CATEGORY_LABELS[key] ?? key}
                  value={n}
                  max={maxCat}
                  display={String(n)}
                  color="bg-violet-500"
                />
              ))
            )}
          </div>
        </div>

        <div className="border-border bg-background rounded-xl border p-4">
          <h3 className="text-sm font-semibold">Gateway latency by model</h3>
          <p className="text-muted-foreground mt-0.5 text-xs">Rolling average response time</p>
          <div className="mt-3 space-y-2.5">
            {latency.length === 0 ? (
              <p className="text-muted-foreground text-sm">Awaiting gateway traffic…</p>
            ) : (
              latency.map(([model, s]) => (
                <BarMeter
                  key={model}
                  label={model}
                  value={s.avgLatencyMs}
                  max={maxLatency}
                  display={`${Math.round(s.avgLatencyMs)} ms`}
                  color="bg-sky-500"
                />
              ))
            )}
          </div>
          <dl className="border-border mt-4 grid grid-cols-2 gap-x-4 gap-y-2 border-t pt-3 text-sm">
            <div>
              <dt className="text-muted-foreground text-xs">Encryption</dt>
              <dd className="font-medium">{stats.encryption ?? 'SSE-KMS'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground text-xs">Audit entries</dt>
              <dd className="font-semibold tabular-nums">{auditCount ?? '…'}</dd>
            </div>
            <div className="col-span-2">
              <dt className="text-muted-foreground text-xs">Consent</dt>
              <dd className="font-medium">
                {stats.consent_given_at
                  ? new Date(stats.consent_given_at).toLocaleString()
                  : String(record.consent_given_at ?? 'Pending')}
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </DashboardSection>
  );
}
