'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useCaseflowEvents, type CaseRecord } from '@/hooks/useCaseflowEvents';
import { MossResultsPanel } from '@/components/app/moss-results-panel';
import { Button } from '@/components/ui/button';

function ScoreGauge({ score }: { score: number }) {
  const color =
    score >= 70 ? 'text-emerald-600' : score >= 40 ? 'text-amber-600' : 'text-red-600';
  return (
    <div className={`text-5xl font-bold tabular-nums ${color}`}>
      {score}
      <span className="text-lg font-normal text-muted-foreground">/100</span>
    </div>
  );
}

function CaseDetail({ record }: { record: CaseRecord }) {
  const strength = Number(record.score ?? record.case_strength ?? 0);
  const matches = (record.matches as Array<Record<string, unknown>>) ?? [];
  const documents = record.documents as Record<string, Record<string, unknown>> | undefined;
  const outbound = record.status as string | undefined;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-border p-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Case strength
          </div>
          <ScoreGauge score={strength} />
        </div>
        <div className="rounded-lg border border-border p-4 sm:col-span-2">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Case fields
          </div>
          <dl className="mt-2 grid gap-1 text-sm sm:grid-cols-2">
            {['caller_id', 'state', 'accident_type', 'fault_claim', 'injuries', 'language'].map(
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
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Parsed documents
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(documents).map(([docType, fields]) => (
              <div key={docType} className="rounded-lg border border-border bg-card p-4">
                <div className="font-medium capitalize">{docType.replace('_', ' ')}</div>
                <pre className="mt-2 overflow-x-auto text-xs text-muted-foreground">
                  {JSON.stringify(fields, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}

      {matches.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Firm matches
          </h3>
          <div className="space-y-2">
            {matches.map((match) => (
              <div
                key={String(match.firm_id)}
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{String(match.name)}</span>
                  <span className="text-sm tabular-nums text-primary">{String(match.score)}</span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{String(match.reasoning)}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-lg border border-dashed border-border p-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
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
  const { cases, connected } = useCaseflowEvents();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selected = useMemo(
    () => cases.find((c) => c.case_id === selectedId) ?? cases[0],
    [cases, selectedId]
  );

  return (
    <div className="min-h-svh bg-background">
      <header className="border-b border-border px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <Link href="/" className="text-lg font-semibold">
              Caseflow
            </Link>
            <p className="text-sm text-muted-foreground">Firm dashboard · live case files</p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`size-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-amber-500'}`}
            />
            <span className="text-sm text-muted-foreground">
              {connected ? 'Live' : 'Reconnecting…'}
            </span>
            <Button asChild variant="outline" size="sm">
              <Link href="/intake">New intake</Link>
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-0 md:grid-cols-[280px_1fr]">
        <aside className="border-b border-border p-4 md:min-h-[calc(100svh-73px)] md:border-b-0 md:border-r">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Incoming cases
          </h2>
          {cases.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No live cases yet. Start an intake at /intake.
            </p>
          ) : (
            <ul className="space-y-2">
              {cases.map((c) => (
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
                    <div className="text-xs text-muted-foreground">
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
            <CaseDetail record={selected} />
          ) : (
            <p className="text-muted-foreground">Select a case to view details.</p>
          )}
        </main>
      </div>
    </div>
  );
}
