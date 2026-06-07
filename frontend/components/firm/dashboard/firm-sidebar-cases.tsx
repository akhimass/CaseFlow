'use client';

import { type CaseRecord } from '@/hooks/useCaseflowEvents';
import { cn } from '@/lib/shadcn/utils';
import { estimatedValue, formatUsd, strengthTone } from './viz';

function prettyAccident(value: unknown): string {
  return String(value ?? '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function FirmSidebarCases({
  firmCases,
  selectedCaseId,
  onSelectCase,
  onOpenCasesTab,
}: {
  firmCases: CaseRecord[];
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
  onOpenCasesTab?: () => void;
}) {
  return (
    <div className="border-border mt-2 border-t pt-3">
      <p className="text-muted-foreground mb-2 px-1 text-[10px] font-semibold tracking-wide uppercase">
        Matched leads
      </p>
      {firmCases.length === 0 ? (
        <p className="text-muted-foreground px-1 text-xs leading-relaxed">
          No intakes yet. Run a client call from /intake.
        </p>
      ) : (
        <ul className="max-h-48 space-y-1 overflow-y-auto">
          {firmCases.map((c) => {
            const id = String(c.case_id);
            const score = Number(c.score ?? c.case_strength ?? 0);
            const tone = strengthTone(score);
            const active = selectedCaseId === id;
            return (
              <li key={id}>
                <button
                  type="button"
                  onClick={() => onSelectCase(id)}
                  className={cn(
                    'w-full rounded-lg px-2 py-2 text-left text-xs transition-colors',
                    active ? 'bg-accent text-accent-foreground' : 'hover:bg-muted/60'
                  )}
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="truncate font-medium">{String(c.caller_id ?? id)}</span>
                    <span
                      className={cn('shrink-0 text-[10px] font-semibold', tone.text)}
                      title={`Case strength ${score}/100`}
                    >
                      {score ? `${tone.label} ${score}` : '—'}
                    </span>
                  </div>
                  <div className="text-muted-foreground mt-0.5 flex justify-between gap-1">
                    <span className="truncate capitalize">
                      {prettyAccident(c.accident_type) || 'Intake'}
                    </span>
                    <span className="shrink-0 tabular-nums">
                      Est. {formatUsd(estimatedValue(c))}
                    </span>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {firmCases.length > 0 && onOpenCasesTab ? (
        <button
          type="button"
          onClick={onOpenCasesTab}
          className="text-primary mt-2 block px-1 text-left text-[10px] font-medium"
        >
          View all in Cases tab →
        </button>
      ) : null}
    </div>
  );
}
