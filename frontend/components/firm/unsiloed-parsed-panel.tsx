'use client';

import type { CaseRecord } from '@/hooks/useCaseflowEvents';

const FIELD_LABELS: Record<string, string> = {
  fault_determination: 'Fault determination',
  other_driver_claim: 'Other driver claim',
  injuries: 'Injuries',
  primary_diagnosis: 'Diagnosis',
  diagnosis: 'Diagnosis',
  treatment: 'Treatment',
  discharge_instructions: 'Discharge instructions',
  imaging_ordered: 'Imaging ordered',
  incident_date: 'Incident date',
  visit_date: 'Visit date',
  location: 'Location',
  report_number: 'Report number',
  patient_name: 'Patient',
};

// Internal keys never shown as parsed fields.
const HIDDEN_KEYS = new Set([
  'capture_source',
  'turn',
  'raw',
  'raw_excerpt',
  'doc_type',
  '_meta',
  'thumbnail',
  'parsed_summary',
]);

const VERIFY_THRESHOLD = 0.75;

type DocMeta = {
  confidence?: Record<string, number>;
  low_confidence?: string[];
  latency_ms?: number;
  source?: string;
};

type ParsingStatus = {
  doc_type?: string;
  status?: string;
  provider?: string;
  source?: string;
  field_count?: number;
  latency_ms?: number;
  error?: string;
  timestamp?: number;
};

function formatDocType(docType: string): string {
  return docType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function confColor(conf: number): string {
  if (conf >= 0.85) return 'bg-emerald-500';
  if (conf >= VERIFY_THRESHOLD) return 'bg-amber-500';
  return 'bg-red-500';
}

function FieldGrid({ fields }: { fields: Record<string, unknown> }) {
  const meta = (fields._meta as DocMeta | undefined) ?? {};
  const confidence = meta.confidence ?? {};
  const entries = Object.entries(fields).filter(
    ([key, value]) =>
      !HIDDEN_KEYS.has(key) && value !== null && value !== undefined && String(value).trim() !== ''
  );

  if (entries.length === 0) {
    return <p className="text-muted-foreground text-sm italic">Awaiting parsed fields…</p>;
  }

  return (
    <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
      {entries.map(([key, value]) => {
        const conf = confidence[key];
        const low = conf !== undefined && conf < VERIFY_THRESHOLD;
        return (
          <div key={key} className="border-border rounded border px-2 py-1.5">
            <div className="flex items-center justify-between gap-2">
              <dt className="text-muted-foreground text-xs">{FIELD_LABELS[key] ?? key}</dt>
              {low ? (
                <span className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-semibold text-amber-700 dark:text-amber-400">
                  verify with caller
                </span>
              ) : null}
            </div>
            <dd className={`mt-0.5 ${low ? 'text-muted-foreground' : 'font-medium'}`}>
              {String(value)}
            </dd>
            {conf !== undefined ? (
              <div className="mt-1 flex items-center gap-1.5">
                <div className="bg-muted h-1 flex-1 overflow-hidden rounded-full">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${confColor(conf)}`}
                    style={{ width: `${Math.round(conf * 100)}%` }}
                  />
                </div>
                <span className="text-muted-foreground/70 text-[9px] tabular-nums">
                  {Math.round(conf * 100)}%
                </span>
              </div>
            ) : null}
          </div>
        );
      })}
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
        <div className="flex items-center gap-2">
          {parsing?.latency_ms ? (
            <span className="text-muted-foreground/70 text-[10px] tabular-nums">
              {Math.round(parsing.latency_ms)} ms
            </span>
          ) : null}
          {parsing?.status === 'parsing' && (
            <span className="animate-pulse rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-400">
              Parsing {formatDocType(String(parsing.doc_type ?? 'document'))}…
            </span>
          )}
          {parsing?.status === 'parsed' && (
            <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-400">
              {parsing.field_count ?? 0} fields · {parsing.source ?? 'Unsiloed'}
            </span>
          )}
          {parsing?.status === 'error' && (
            <span className="rounded-full bg-red-500/15 px-2 py-0.5 text-xs font-medium text-red-600">
              Parse failed
            </span>
          )}
        </div>
      </div>

      {parsing?.status === 'error' && parsing.error ? (
        <p className="mt-2 rounded border border-red-500/30 bg-red-500/5 px-2 py-1.5 text-xs text-red-600">
          Unsiloed error: {parsing.error}. Ask the caller to re-show the document.
        </p>
      ) : null}

      {hasDocs && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {Object.entries(documents!).map(([docType, fields]) => {
            const thumb = fields.thumbnail as string | undefined;
            const meta = (fields._meta as DocMeta | undefined) ?? {};
            const fieldCount = Object.keys(fields).filter(
              (k) =>
                !HIDDEN_KEYS.has(k) &&
                fields[k] !== null &&
                fields[k] !== undefined &&
                String(fields[k]).trim() !== ''
            ).length;
            return (
              <div key={docType} className="border-border bg-card rounded-lg border p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{formatDocType(docType)}</span>
                  <span className="text-muted-foreground text-xs">
                    {meta.source === 'demo_no_key' ? 'demo' : 'Unsiloed Vision API'}
                  </span>
                </div>
                {thumb ? (
                  <figure className="bg-muted/40 mt-2 overflow-hidden rounded-md border">
                    <img
                      src={thumb}
                      alt={`Redacted ${formatDocType(docType)} preview`}
                      className="h-40 w-full bg-black/5 object-contain"
                    />
                    <figcaption className="text-muted-foreground/70 border-border/60 border-t px-2 py-1 text-[9px]">
                      PII-redacted source image (blurred) — verify the {fieldCount} parsed fields
                      below match the document
                    </figcaption>
                  </figure>
                ) : (
                  <div className="border-border/60 text-muted-foreground/60 mt-2 flex h-40 items-center justify-center rounded-md border border-dashed text-[10px]">
                    No source image captured
                  </div>
                )}
                <FieldGrid fields={fields} />
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
