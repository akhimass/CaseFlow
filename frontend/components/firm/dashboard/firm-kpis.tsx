'use client';

import type { CaseRecord } from '@/hooks/useCaseflowEvents';
import { StatTile, estimatedValue, formatUsd } from './viz';

/** Firm-wide snapshot KPIs derived from the firm's matched leads. */
export function FirmKpiStrip({ cases }: { cases: CaseRecord[] }) {
  const total = cases.length;
  const avgStrength =
    total > 0
      ? Math.round(
          cases.reduce((sum, c) => sum + Number(c.score ?? c.case_strength ?? 0), 0) / total
        )
      : 0;
  const pipeline = cases.reduce((sum, c) => sum + estimatedValue(c), 0);
  const discrepancies = cases.filter(
    (c) => (c.consistency_audit as { conflict?: boolean } | undefined)?.conflict
  ).length;
  const booked = cases.filter((c) => c.status === 'booked').length;
  const strongLeads = cases.filter((c) => Number(c.score ?? c.case_strength ?? 0) >= 70).length;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <StatTile value={total} label="Matched leads" tone="accent" hint="In your queue" />
      <StatTile
        value={formatUsd(pipeline)}
        label="Est. pipeline"
        tone="good"
        hint="Comparable-value est."
      />
      <StatTile value={avgStrength} label="Avg case strength" hint={`${strongLeads} strong`} />
      <StatTile
        value={discrepancies}
        label="Discrepancies caught"
        tone={discrepancies > 0 ? 'warn' : 'default'}
        hint="Guardrails review"
      />
      <StatTile value={booked} label="Consults booked" tone="good" hint="Via outbound call" />
    </div>
  );
}
