'use client';

import type { CaseRecord } from '@/hooks/useCaseflowEvents';

const ARTIFACT_PATHS = [
  'transcript.jsonl',
  'intake_structured.json',
  'verbal_summary.md',
  'parsed/police_report.json',
  'parsed/er_discharge.json',
  'audit/consistency.json',
  'match/result.json',
  'brief/firm_brief.txt',
  'case/snapshot.json',
  'docs/intake_summary.md',
  'docs/demand_letter.md',
  'docs/action_sheet.md',
];

const SENSITIVE_NOTE =
  'Raw document images (frames/) are stored only in s3://caseflow-sensitive/ — not listed here.';

export function AwsArtifactsPanel({ record }: { record: CaseRecord }) {
  const prefix = String(record.s3_prefix ?? '');
  const caseId = String(record.case_id ?? '');

  if (!prefix && !caseId) {
    return (
      <section className="border-border rounded-lg border border-dashed p-4">
        <h3 className="text-muted-foreground mb-2 text-xs font-semibold tracking-wide uppercase">
          AWS S3 case file
        </h3>
        <p className="text-muted-foreground text-sm">S3 prefix will appear once intake starts.</p>
      </section>
    );
  }

  const base = prefix || `s3://caseflow-cases-dev/${caseId}/`;

  return (
    <section className="border-border rounded-lg border p-4">
      <h3 className="text-muted-foreground mb-2 text-xs font-semibold tracking-wide uppercase">
        AWS S3 case file
      </h3>
      <p className="text-sm font-medium break-all">{base}</p>
      <ul className="text-muted-foreground mt-3 space-y-1 font-mono text-xs">
        {ARTIFACT_PATHS.map((path) => (
          <li key={path}>
            {base.endsWith('/') ? base : `${base}/`}
            {path}
          </li>
        ))}
      </ul>
      <p className="text-muted-foreground mt-3 text-xs">{SENSITIVE_NOTE}</p>
    </section>
  );
}
