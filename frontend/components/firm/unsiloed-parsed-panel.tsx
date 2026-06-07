'use client';

import type { CaseRecord } from '@/hooks/useCaseflowEvents';

const FIELD_LABELS: Record<string, string> = {
  fault_determination: 'Fault determination',
  injuries: 'Injuries',
  diagnosis: 'Diagnosis',
  treatment: 'Treatment',
  imaging_ordered: 'Imaging ordered',
  incident_date: 'Incident date',
  location: 'Location',
  patient_name: 'Patient',
};

type ParsingStatus = {
  doc_type?: string;
  status?: string;
  provider?: string;
  field_count?: number;
  timestamp?: number;
};

function formatDocType(docType: string): string {
  return docType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function FieldGrid({ fields }: { fields: Record<string, unknown> }) {
  const entries = Object.entries(fields).filter(
    ([key, value]) =>
      !['capture_source', 'turn', 'raw'].includes(key) &&
      value !== null &&
      value !== undefined &&
      String(value).trim() !== ''
  );

  if (entries.length === 0) {
    return <p className="text-muted-foreground text-sm italic">Awaiting parsed fields…</p>;
  }

  return (
    <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <div key={key} className="border-border rounded border px-2 py-1.5">
          <dt className="text-muted-foreground text-xs">{FIELD_LABELS[key] ?? key}</dt>
          <dd className="font-medium">{String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function UnsiloedParsedPanel({ record }: { record: CaseRecord }) {
  const documents = record.documents as Record<string, Record<string, unknown>> | undefined;
  const parsing = record.document_parsing as ParsingStatus | undefined;
  const hasDocs = documents && Object.keys(documents).length > 0;

  if (!hasDocs && !parsing) {
    return (
      <section className="border-border rounded-lg border border-dashed p-4">
        <h3 className="text-muted-foreground mb-1 text-xs font-semibold tracking-wide uppercase">
          Unsiloed · live document parsing
        </h3>
        <p className="text-muted-foreground text-sm">
          Parsed fields stream in when the caller holds documents to the camera.
        </p>
      </section>
    );
  }

  return (
    <section className="border-border rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
          Unsiloed · live document parsing
        </h3>
        {parsing?.status === 'parsing' && (
          <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-400">
            Parsing {formatDocType(String(parsing.doc_type ?? 'document'))}…
          </span>
        )}
        {parsing?.status === 'parsed' && (
          <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-400">
            {parsing.field_count ?? 0} fields extracted
          </span>
        )}
      </div>

      {hasDocs && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {Object.entries(documents!).map(([docType, fields]) => (
            <div key={docType} className="border-border bg-card rounded-lg border p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold">{formatDocType(docType)}</span>
                <span className="text-muted-foreground text-xs">Unsiloed Vision API</span>
              </div>
              <FieldGrid fields={fields} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
