'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { type FirmSession, caseVisibleToFirm } from '@/lib/firm-session';
import { AwsArtifactsPanel } from '@/components/firm/aws-artifacts-panel';
import { CaseflowDecisionCard } from '@/components/firm/caseflow-decision-card';
import { DocumentsPanel } from '@/components/firm/documents-panel';
import { ConsistencyAuditPanel } from '@/components/firm/consistency-audit-panel';
import { GatewayMetricsPanel } from '@/components/firm/gateway-metrics-panel';
import { LiveTranscriptPanel } from '@/components/firm/live-transcript-panel';
import { MossIntelligencePanel } from '@/components/firm/moss-intelligence-panel';
import { PrivacyPanel } from '@/components/firm/privacy-panel';
import { Button } from '@/components/ui/button';
import { type CaseRecord, useCaseflowEvents } from '@/hooks/useCaseflowEvents';

function ScoreGauge({ score }: { score: number }) {
  const color = score >= 70 ? 'text-emerald-600' : score >= 40 ? 'text-amber-600' : 'text-red-600';
  return (
    <div className={`text-5xl font-bold tabular-nums ${color}`}>
      {score}
      <span className="text-muted-foreground text-lg font-normal">/100</span>
    </div>
  );
}

function CaseDetail({
  record,
  revealed,
  onReveal,
}: {
  record: CaseRecord;
  revealed: boolean;
  onReveal: () => void;
}) {
  const strength = Number(record.score ?? record.case_strength ?? 0);
  const matches = (record.matches as Array<Record<string, unknown>>) ?? [];
  const documents = record.documents as Record<string, Record<string, unknown>> | undefined;
  const outbound = record.status as string | undefined;

  return (
    <div className="space-y-6">
      <PrivacyPanel record={record} revealed={revealed} onReveal={onReveal} />

      <div className="grid gap-4 lg:grid-cols-2">
        <LiveTranscriptPanel record={record} />
        <ConsistencyAuditPanel record={record} />
      </div>

      <MossIntelligencePanel record={record} />

      <CaseflowDecisionCard record={record} />

      <DocumentsPanel record={record} />

      <AwsArtifactsPanel record={record} />

      <GatewayMetricsPanel collapsed />

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="border-border rounded-lg border p-4">
          <div className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
            Case strength
          </div>
          <ScoreGauge score={strength} />
        </div>
        <div className="border-border rounded-lg border p-4 sm:col-span-2">
          <div className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
            Case fields
          </div>
          <dl className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
            {['caller_id', 'caller_location', 'location', 'state', 'accident_type', 'fault_claim', 'injuries', 'language'].map(
              (key) =>
                record[key] ? (
                  <div key={key}>
                    <dt className="text-muted-foreground">{key}</dt>
                    <dd className="font-medium">{String(record[key])}</dd>
                  </div>
                ) : null
            )}
          </dl>
        </div>
      </div>

      {documents && Object.keys(documents).length > 0 && (
        <div>
          <h3 className="text-muted-foreground mb-2 text-sm font-semibold tracking-wide uppercase">
            Parsed documents (Unsiloed)
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(documents).map(([docType, fields]) => (
              <div key={docType} className="border-border bg-card rounded-lg border p-4">
                <div className="font-medium capitalize">{docType.replace('_', ' ')}</div>
                <pre className="text-muted-foreground mt-2 overflow-x-auto text-xs">
                  {JSON.stringify(fields, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}

      {matches.length > 0 && (
        <div>
          <h3 className="text-muted-foreground mb-2 text-sm font-semibold tracking-wide uppercase">
            Firm matches
          </h3>
          <div className="space-y-2">
            {matches.map((match) => (
              <div
                key={String(match.firm_id)}
                className="border-border bg-card rounded-lg border p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{String(match.name)}</span>
                  <span className="text-primary text-sm tabular-nums">{String(match.score)}</span>
                </div>
                <p className="text-muted-foreground mt-1 text-sm">{String(match.reasoning)}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="border-border rounded-lg border border-dashed p-4">
        <div className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
          Outbound call status
        </div>
        <p className="mt-1 text-sm">
          {outbound === 'booked'
            ? 'Briefing complete — consult booked'
            : record.last_event === 'outbound_call'
              ? 'Dialing → briefing → booked'
              : 'Idle — waiting for intake to complete'}
        </p>
      </div>
    </div>
  );
}

export default function FirmPage() {
  const router = useRouter();
  const { cases, connected } = useCaseflowEvents();
  const [session, setSession] = useState<FirmSession | null | undefined>(undefined);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [revealedIds, setRevealedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetch('/api/firm/session')
      .then((res) => (res.ok ? res.json() : { session: null }))
      .then((data) => setSession(data.session ?? null))
      .catch(() => setSession(null));
  }, []);

  useEffect(() => {
    if (session === null) router.replace('/firm/login');
  }, [session, router]);

  const firmCases = useMemo(() => {
    if (!session) return [];
    return cases.filter((record) => caseVisibleToFirm(record, session.firm_id));
  }, [cases, session]);

  const selected = useMemo(
    () => firmCases.find((c) => c.case_id === selectedId) ?? firmCases[0],
    [firmCases, selectedId]
  );

  if (session === undefined) {
    return (
      <div className="text-muted-foreground flex min-h-svh items-center justify-center text-sm">
        Loading firm session…
      </div>
    );
  }

  if (!session) return null;

  return (
    <div className="bg-background min-h-svh">
      <header className="border-border border-b px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <Link href="/" className="text-lg font-semibold">
              Caseflow
            </Link>
            <p className="text-muted-foreground text-sm">
              {session.firm_name}
              {session.city ? ` · ${session.city}` : ''} · live matched intakes
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`size-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-amber-500'}`}
            />
            <span className="text-muted-foreground text-sm">
              {connected ? 'Live' : 'Reconnecting…'}
            </span>
            <Button asChild variant="outline" size="sm">
              <Link href="/admin/metrics">Metrics</Link>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                await fetch('/api/firm/logout', { method: 'POST' });
                router.replace('/firm/login');
              }}
            >
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-0 md:grid-cols-[280px_1fr]">
        <aside className="border-border border-b p-4 md:min-h-[calc(100svh-73px)] md:border-r md:border-b-0">
          <h2 className="text-muted-foreground mb-3 text-xs font-semibold tracking-wide uppercase">
            Incoming cases
          </h2>
          {firmCases.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No matched intakes yet. Open /intake/consent in another tab, enter San Francisco as
              your location, and complete a call.
            </p>
          ) : (
            <ul className="space-y-2">
              {firmCases.map((c) => (
                <li key={String(c.case_id)}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(String(c.case_id))}
                    className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                      selected?.case_id === c.case_id
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:bg-muted/50'
                    }`}
                  >
                    <div className="font-medium">{String(c.caller_id ?? c.case_id)}</div>
                    <div className="text-muted-foreground text-xs">
                      {String(c.last_event ?? 'intake')}
                      {c.language ? ` · ${String(c.language)}` : ''}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <main className="p-6">
          {selected ? (
            <CaseDetail
              record={selected}
              revealed={revealedIds.has(String(selected.case_id))}
              onReveal={async () => {
                const id = String(selected.case_id);
                await fetch(`/api/cases/${id}/reveal`, { method: 'POST' });
                setRevealedIds((prev) => new Set(prev).add(id));
              }}
            />
          ) : (
            <p className="text-muted-foreground">Select a case to view details.</p>
          )}
        </main>
      </div>
    </div>
  );
}
