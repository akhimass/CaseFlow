'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import type { CaseRecord } from '@/hooks/useCaseflowEvents';
import { StrengthGauge, estimatedValue, formatUsd } from './viz';

const ACCIDENT_LABELS: Record<string, string> = {
  rear_end: 'Rear-end collision',
  pedestrian: 'Pedestrian',
  slip_fall: 'Slip & fall',
  motorcycle: 'Motorcycle',
  auto: 'Auto collision',
  mva: 'Motor-vehicle accident',
  premises: 'Premises liability',
};

const LANGUAGE_LABELS: Record<string, string> = {
  en: 'English',
  es: 'Spanish',
  zh: 'Mandarin',
  hi: 'Hindi',
};

const STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  booked: {
    label: 'Consult booked',
    cls: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400',
  },
  matched: { label: 'Matched — action needed', cls: 'bg-primary/15 text-primary' },
  intake: {
    label: 'Intake in progress',
    cls: 'bg-amber-500/15 text-amber-700 dark:text-amber-400',
  },
};

function Badge({
  children,
  cls = 'bg-muted text-muted-foreground',
}: {
  children: string;
  cls?: string;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}
    >
      {children}
    </span>
  );
}

export function LeadHeader({ record }: { record: CaseRecord }) {
  const strength = Number(record.score ?? record.case_strength ?? 0);
  const accident = String(record.accident_type ?? '');
  const language = String(record.language ?? '');
  const status = String(record.status ?? record.last_event ?? '');
  const statusMeta = STATUS_LABELS[status] ?? {
    label: status || 'New lead',
    cls: 'bg-muted text-muted-foreground',
  };
  const matches = (record.matches as Array<Record<string, unknown>>) ?? [];
  const topMatch = matches[0];

  const fields: Array<[string, string | undefined]> = [
    ['Injuries', record.injuries as string | undefined],
    ['Reported fault', record.fault_claim as string | undefined],
    ['Location', (record.caller_location ?? record.location) as string | undefined],
    ['Jurisdiction', record.state as string | undefined],
  ];

  return (
    <section className="border-border bg-card rounded-2xl border p-5 sm:p-6">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge cls={statusMeta.cls}>{statusMeta.label}</Badge>
            {accident ? <Badge>{ACCIDENT_LABELS[accident] ?? accident}</Badge> : null}
            {language ? <Badge>{LANGUAGE_LABELS[language] ?? language}</Badge> : null}
          </div>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">
            {String(record.caller_id ?? record.case_id)}
          </h1>

          <dl className="mt-4 grid gap-x-6 gap-y-3 sm:grid-cols-2">
            {fields.map(([label, value]) =>
              value ? (
                <div key={label}>
                  <dt className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
                    {label}
                  </dt>
                  <dd className="mt-0.5 text-base">{value}</dd>
                </div>
              ) : null
            )}
          </dl>
        </div>

        <div className="border-border flex shrink-0 flex-col items-center gap-3 rounded-xl border p-4 sm:flex-row sm:items-center sm:gap-6 lg:flex-col">
          <StrengthGauge score={strength} />
          <div className="text-center sm:text-left lg:text-center">
            <div className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
              Est. case value
            </div>
            <div className="mt-1 text-2xl font-bold text-emerald-600 tabular-nums">
              {formatUsd(estimatedValue(record))}
            </div>
            <Button asChild size="sm" className="mt-3 w-full">
              <Link href={`/firm/brief/${String(record.case_id)}`}>Brief me on this case</Link>
            </Button>
          </div>
        </div>
      </div>

      {topMatch ? (
        <div className="border-border from-primary/5 mt-5 rounded-xl border bg-gradient-to-r to-transparent p-4">
          <div className="text-primary/70 font-mono text-[11px] font-semibold tracking-[0.14em] uppercase">
            Recommended action
          </div>
          <div className="mt-1 flex flex-wrap items-baseline justify-between gap-2">
            <span className="text-lg font-semibold">{String(topMatch.name)}</span>
            <span className="text-primary text-sm font-semibold tabular-nums">
              {String(topMatch.score)}% match
            </span>
          </div>
          <p className="text-muted-foreground mt-1 text-sm">{String(topMatch.reasoning ?? '')}</p>
        </div>
      ) : null}
    </section>
  );
}
