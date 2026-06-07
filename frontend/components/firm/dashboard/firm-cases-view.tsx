'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { type CaseRecord } from '@/hooks/useCaseflowEvents';
import { cn } from '@/lib/shadcn/utils';
import { estimatedValue, formatUsd, strengthTone } from './viz';

function prettyType(record: CaseRecord): string {
  const type = String(record.accident_type ?? 'Intake')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
  const lang = String(record.language ?? '').toLowerCase();
  if (lang === 'es' || lang === 'spanish') return `${type} · ES`;
  return type;
}

function dispositionFor(record: CaseRecord): { label: string; qualified: boolean } {
  const score = Number(record.score ?? record.case_strength ?? 0);
  const status = String(record.status ?? '').toLowerCase();
  if (status === 'declined' || score < 40) return { label: 'Declined', qualified: false };
  return { label: 'Qualified', qualified: true };
}

function caseSummary(record: CaseRecord): string {
  const text = String(record.verbal_summary ?? record.injuries ?? record.fault_claim ?? '').trim();
  if (text) return text;
  return 'Open to review evidence, Moss retrieval, and the consistency audit.';
}

function isLiveIntake(record: CaseRecord): boolean {
  const updated = Number(record.updated_at ?? 0);
  if (!updated || Date.now() - updated > 45 * 60 * 1000) return false;
  const terminal = new Set(['booked', 'declined', 'post_call_package', 'complete']);
  const last = String(record.last_event ?? '');
  if (terminal.has(String(record.status ?? '').toLowerCase())) return false;
  if (last === 'post_call_package' || last === 'firms_matched') return false;
  return true;
}

function intakesToday(cases: CaseRecord[]): number {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const cutoff = start.getTime();
  return cases.filter((c) => Number(c.updated_at ?? c.timestamp ?? 0) >= cutoff).length;
}

function LeadCard({
  record,
  onSelectCase,
}: {
  record: CaseRecord;
  onSelectCase: (caseId: string) => void;
}) {
  const id = String(record.case_id);
  const disp = dispositionFor(record);
  const score = Number(record.score ?? record.case_strength ?? 0);
  const tone = strengthTone(score);
  const value = estimatedValue(record);

  return (
    <div className="border-border bg-background flex flex-col rounded-xl border p-4 shadow-sm transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-semibold">{String(record.caller_id ?? id)}</p>
          <p className="text-muted-foreground mt-0.5 truncate text-xs">{prettyType(record)}</p>
        </div>
        <div className="shrink-0 text-right" title={`Case strength ${score || 0}/100`}>
          <div className="text-muted-foreground text-[9px] font-semibold tracking-wide uppercase">
            Case strength
          </div>
          <div className={cn('text-xl leading-none font-bold tabular-nums', tone.text)}>
            {score || '—'}
          </div>
          {score ? (
            <div className={cn('text-[10px] font-semibold', tone.text)}>{tone.label}</div>
          ) : null}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span
          className={cn(
            'inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium',
            disp.qualified
              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300'
              : 'bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-300'
          )}
        >
          {disp.label}
        </span>
        <span className="text-muted-foreground text-xs">
          Est. value{' '}
          <span className="text-foreground font-semibold tabular-nums">
            {value > 0 ? formatUsd(value) : '—'}
          </span>
        </span>
      </div>

      <p className="text-muted-foreground mt-3 line-clamp-2 text-xs leading-relaxed">
        {caseSummary(record)}
      </p>

      <div className="mt-4 flex gap-2">
        <Button type="button" size="sm" className="flex-1" onClick={() => onSelectCase(id)}>
          View dossier
        </Button>
        <Button asChild size="sm" variant="outline" className="flex-1">
          <Link href={`/firm/brief/${id}`}>Voice briefing</Link>
        </Button>
      </div>
    </div>
  );
}

export function FirmCasesView({
  firmCases,
  onSelectCase,
}: {
  firmCases: CaseRecord[];
  onSelectCase: (caseId: string) => void;
}) {
  const qualified = firmCases.filter((c) => dispositionFor(c).qualified).length;
  const liveNow = firmCases.filter(isLiveIntake).length;
  const today = intakesToday(firmCases);

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: 'Intakes today', value: today || firmCases.length },
          { label: 'Qualified', value: qualified, accent: true },
          { label: 'Live now', value: liveNow },
        ].map(({ label, value, accent }) => (
          <div key={label} className="border-border bg-background rounded-xl border p-4">
            <div className="text-muted-foreground text-[11px] font-semibold tracking-wide uppercase">
              {label}
            </div>
            <div
              className={cn(
                'mt-1 text-3xl font-bold tracking-tight tabular-nums',
                accent && 'text-primary'
              )}
            >
              {value}
            </div>
          </div>
        ))}
      </div>

      {firmCases.length === 0 ? (
        <div className="border-border text-muted-foreground rounded-xl border border-dashed px-4 py-12 text-center text-sm">
          No matched intakes yet. Complete a client call at /intake — leads appear here live once
          matched to your firm.
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {firmCases.map((record) => (
            <LeadCard key={String(record.case_id)} record={record} onSelectCase={onSelectCase} />
          ))}
        </div>
      )}
    </div>
  );
}
