import { useEffect, useState } from 'react';

export type CaseRecord = Record<string, unknown> & { case_id?: string };

export function useCaseflowEvents() {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const source = new EventSource('/api/cases/events');

    source.onopen = () => setConnected(true);
    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'snapshot') {
          setCases(data.cases ?? []);
        }
        if (data.type === 'update') {
          const { case_id, payload } = data;
          setCases((prev) => {
            const idx = prev.findIndex((c) => c.case_id === case_id);
            const next = [...prev];
            const existing = idx >= 0 ? next[idx] : {};
            const merged = { case_id, ...existing, ...payload };
            if (payload?.transcript_line) {
              const line = payload.transcript_line as Record<string, unknown>;
              const prior = (existing.transcript_lines as unknown[]) ?? [];
              merged.transcript_lines = [...prior, line];
            }
            if (payload?.moss_retrievals) {
              merged.moss_retrievals = payload.moss_retrievals;
            }
            if (payload?.consistency_audit) {
              merged.consistency_audit = payload.consistency_audit;
            }
            if (payload?.transcript_lines) {
              merged.transcript_lines = payload.transcript_lines;
            }
            if (payload?.verbal_summary) {
              merged.verbal_summary = payload.verbal_summary;
            }
            if (payload?.firm_brief) {
              merged.firm_brief = payload.firm_brief;
            }
            if (payload?.intake_structured) {
              merged.intake_structured = payload.intake_structured;
            }
            if (payload?.privacy_stats) {
              merged.privacy_stats = payload.privacy_stats;
            }
            if (payload?.consent_given_at) {
              merged.consent_given_at = payload.consent_given_at;
            }
            if (payload?.pii_redacted !== undefined) {
              merged.pii_redacted = payload.pii_redacted;
            }
            if (payload?.generated_documents) {
              merged.generated_documents = payload.generated_documents;
            }
            if (payload?.latest_document) {
              const latest = payload.latest_document as Record<string, unknown>;
              const prior = (merged.generated_documents as unknown[]) ?? [];
              const docType = String(latest.doc_type ?? '');
              merged.generated_documents = [
                ...prior.filter((d) => String((d as Record<string, unknown>).doc_type) !== docType),
                latest,
              ];
            }
            if (payload?.case_completeness !== undefined) {
              merged.case_completeness = payload.case_completeness;
            }
            if (payload?.voice_bridge) {
              merged.voice_bridge = payload.voice_bridge;
            }
            if (payload?.document_parsing) {
              merged.document_parsing = payload.document_parsing;
            }
            if (payload?.s3_artifacts) {
              merged.s3_artifacts = payload.s3_artifacts;
            }
            if (idx >= 0) next[idx] = merged;
            else next.unshift(merged);
            return next;
          });
        }
      } catch {
        // ignore malformed events
      }
    };

    source.onerror = () => setConnected(false);

    return () => source.close();
  }, []);

  return { cases, connected };
}
