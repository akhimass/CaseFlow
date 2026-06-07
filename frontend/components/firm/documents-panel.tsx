'use client';

import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  CheckCircleIcon,
  FileTextIcon,
  ScrollIcon,
  WarningCircleIcon,
} from '@phosphor-icons/react';
import { type CaseRecord } from '@/hooks/useCaseflowEvents';
import { Button } from '@/components/ui/button';
import { Shimmer } from '@/components/ai-elements/shimmer';

type GeneratedDoc = {
  doc_type?: string;
  title?: string;
  generated_at?: string;
  audit_status?: string;
  page_count?: number;
  audit_confidence?: number;
  s3_path_md?: string;
  s3_path_pdf?: string;
};

const DOC_ORDER = ['intake_summary', 'demand_letter', 'action_sheet'];

const ICONS: Record<string, typeof FileTextIcon> = {
  intake_summary: FileTextIcon,
  demand_letter: ScrollIcon,
  action_sheet: FileTextIcon,
};

function AuditBadge({ status }: { status?: string }) {
  if (status === 'verified') {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
        <CheckCircleIcon weight="fill" className="size-3.5" />
        Verified
      </span>
    );
  }
  if (status === 'flagged') {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-amber-600">
        <WarningCircleIcon weight="fill" className="size-3.5" />
        Flagged
      </span>
    );
  }
  return <span className="text-muted-foreground text-xs">Auditing…</span>;
}

function renderMarkdownPreview(md: string) {
  const parts = md.split(/(\[cite:[^\]]+\])/g);
  return parts.map((part, i) => {
    const m = part.match(/^\[cite:(.+)\]$/);
    if (m) {
      const id = m[1];
      return (
        <button
          key={`${id}-${i}`}
          type="button"
          className="mx-0.5 inline rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-medium text-indigo-800 hover:bg-indigo-200 dark:bg-indigo-950 dark:text-indigo-200"
          onClick={() => {
            document
              .querySelector(`[data-citation-id="${id}"]`)
              ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }}
        >
          cite:{id}
        </button>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export function DocumentsPanel({ record }: { record: CaseRecord }) {
  const docs = (record.generated_documents as GeneratedDoc[] | undefined) ?? [];
  const [preview, setPreview] = useState<{ docType: string; content: string } | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  const ordered = useMemo(
    () =>
      [...docs].sort(
        (a, b) =>
          DOC_ORDER.indexOf(String(a.doc_type)) - DOC_ORDER.indexOf(String(b.doc_type))
      ),
    [docs]
  );

  const caseId = String(record.case_id ?? '');

  async function openPreview(docType: string) {
    setLoading(docType);
    try {
      const res = await fetch(`/api/cases/${caseId}/documents/${docType}?format=md`);
      const data = await res.json();
      setPreview({ docType, content: data.content ?? '' });
    } finally {
      setLoading(null);
    }
  }

  async function downloadPdf(docType: string) {
    const res = await fetch(`/api/cases/${caseId}/documents/${docType}?format=pdf`);
    const data = await res.json();
    if (data.url) window.open(data.url, '_blank', 'noopener');
  }

  return (
    <section className="border-border rounded-lg border p-4">
      <h3 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
        Generated case file
      </h3>
      <p className="text-muted-foreground mt-1 text-xs">
        Documents build in real time during intake — Intake Summary first, then Demand Letter and
        Action Sheet after firm match.
      </p>

      {ordered.length === 0 ? (
        <div className="mt-4 py-6 text-center">
          <Shimmer className="text-sm font-medium">Documents generating during the call…</Shimmer>
        </div>
      ) : (
        <ul className="mt-4 space-y-3">
          <AnimatePresence initial={false}>
            {ordered.map((doc) => {
              const docType = String(doc.doc_type ?? '');
              const Icon = ICONS[docType] ?? FileTextIcon;
              return (
                <motion.li
                  key={docType}
                  initial={{ opacity: 0, x: 24 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.35, ease: 'easeOut' }}
                  className="border-border bg-card flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3"
                >
                  <div className="flex min-w-0 items-start gap-3">
                    <Icon className="text-primary mt-0.5 size-5 shrink-0" />
                    <div>
                      <div className="font-medium">{doc.title ?? docType}</div>
                      <div className="text-muted-foreground mt-0.5 flex flex-wrap gap-2 text-xs">
                        {doc.generated_at ? (
                          <span>{new Date(doc.generated_at).toLocaleTimeString()}</span>
                        ) : null}
                        {doc.page_count ? <span>{doc.page_count} pages</span> : null}
                        <AuditBadge status={doc.audit_status} />
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={loading === docType}
                      onClick={() => openPreview(docType)}
                    >
                      Preview
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => downloadPdf(docType)}>
                      Download PDF
                    </Button>
                  </div>
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ul>
      )}

      <AnimatePresence>
        {preview && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="bg-background/80 fixed inset-0 z-[80] flex items-center justify-center p-4"
            onClick={() => setPreview(null)}
          >
            <motion.div
              initial={{ scale: 0.96, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="bg-card border-border max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border p-6 shadow-lg"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="mb-4 flex items-center justify-between gap-2">
                <h4 className="font-semibold capitalize">{preview.docType.replace(/_/g, ' ')}</h4>
                <Button size="sm" variant="ghost" onClick={() => setPreview(null)}>
                  Close
                </Button>
              </div>
              <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap leading-relaxed">
                {renderMarkdownPreview(preview.content)}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
