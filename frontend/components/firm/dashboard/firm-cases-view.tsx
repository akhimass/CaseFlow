'use client';

import { FileTextIcon } from '@phosphor-icons/react/dist/ssr';
import { type CaseRecord } from '@/hooks/useCaseflowEvents';
import { cn } from '@/lib/shadcn/utils';
import { estimatedValue, formatUsd, strengthTone } from './viz';

const TABLE_COLS =
  'grid-cols-[minmax(7rem,1.15fr)_minmax(5rem,0.85fr)_minmax(5.5rem,0.9fr)_minmax(5rem,0.8fr)_minmax(3.5rem,0.65fr)_minmax(5.5rem,0.85fr)]';

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

function summaryLabel(record: CaseRecord): string | null {
  const id = String(record.case_id ?? '');
  const docs = (record.documents as Array<{ doc_type?: string }> | undefined) ?? [];
  if (docs.length > 0) {
    const docType = docs[0]?.doc_type ?? 'intake';
    return `${docType}-${id.slice(0, 8)}.pdf`;
  }
  if (record.verbal_summary || record.firm_brief) {
    return `intake-${id.slice(0, 8)}.pdf`;
  }
  return null;
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

      <div className="border-border bg-background overflow-x-auto rounded-xl border">
        <div className="min-w-[40rem]">
          <div
            className={cn(
              'grid',
              TABLE_COLS,
              'border-border bg-muted/40 text-muted-foreground gap-2 border-b px-4 py-3 text-[11px] font-semibold tracking-wide uppercase'
            )}
          >
            <span>Caller</span>
            <span>Type</span>
            <span>Disposition</span>
            <span>Case strength</span>
            <span>Est. value</span>
            <span>Summary</span>
          </div>
          {firmCases.length === 0 ? (
            <p className="text-muted-foreground px-4 py-10 text-center text-sm">
              No matched intakes yet. Complete a client call at /intake — leads appear here live
              once matched to your firm.
            </p>
          ) : (
            firmCases.map((record) => {
              const id = String(record.case_id);
              const disp = dispositionFor(record);
              const score = Number(record.score ?? record.case_strength ?? 0);
              const value = estimatedValue(record);
              const summary = summaryLabel(record);
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => onSelectCase(id)}
                  className={cn(
                    'grid',
                    TABLE_COLS,
                    'border-border hover:bg-muted/30 w-full gap-2 border-b px-4 py-3 text-left text-sm transition-colors last:border-b-0'
                  )}
                >
                  <span className="truncate font-medium">{String(record.caller_id ?? id)}</span>
                  <span className="text-muted-foreground truncate">{prettyType(record)}</span>
                  <span>
                    <span
                      className={cn(
                        'inline-flex rounded-full px-2 py-0.5 text-xs font-medium',
                        disp.qualified
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300'
                          : 'bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-300'
                      )}
                    >
                      {disp.label}
                    </span>
                  </span>
                  <span className="flex items-baseline gap-1 tabular-nums">
                    {score ? (
                      <>
                        <span className={cn('font-semibold', strengthTone(score).text)}>
                          {score}
                        </span>
                        <span className="text-muted-foreground text-[11px]">
                          {strengthTone(score).label}
                        </span>
                      </>
                    ) : (
                      '—'
                    )}
                  </span>
                  <span className="font-medium tabular-nums">
                    {value > 0 ? formatUsd(value) : '—'}
                  </span>
                  <span>
                    {summary ? (
                      <span className="text-primary inline-flex max-w-full items-center gap-1 truncate">
                        <FileTextIcon className="size-3.5 shrink-0" weight="bold" />
                        <span className="truncate underline underline-offset-2">{summary}</span>
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </span>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
