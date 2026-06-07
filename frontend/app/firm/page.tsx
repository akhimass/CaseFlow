'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AwsArtifactsPanel } from '@/components/firm/aws-artifacts-panel';
import { CaseflowDecisionCard } from '@/components/firm/caseflow-decision-card';
import { FirmKpiStrip } from '@/components/firm/dashboard/firm-kpis';
import { GuardrailsDashboard } from '@/components/firm/dashboard/guardrails';
import { LeadHeader } from '@/components/firm/dashboard/lead-header';
import { MossOverview } from '@/components/firm/dashboard/moss-overview';
import { TrueFoundryPrivacyDashboard } from '@/components/firm/dashboard/truefoundry-privacy';
import {
  SectionHeader,
  estimatedValue,
  formatUsd,
  strengthTone,
} from '@/components/firm/dashboard/viz';
import { DocumentsPanel } from '@/components/firm/documents-panel';
import { LiveTranscriptPanel } from '@/components/firm/live-transcript-panel';
import { MossEvidenceTrail } from '@/components/firm/moss-evidence-trail';
import { MossIntelligencePanel } from '@/components/firm/moss-intelligence-panel';
import { UnsiloedParsedPanel } from '@/components/firm/unsiloed-parsed-panel';
import { VoiceBridgePanel } from '@/components/firm/voice-bridge-panel';
import { Button } from '@/components/ui/button';
import { type CaseRecord, useCaseflowEvents } from '@/hooks/useCaseflowEvents';
import { type FirmSession, caseVisibleToFirm } from '@/lib/firm-session';

function CaseDetail({
  record,
  revealed,
  onReveal,
}: {
  record: CaseRecord;
  revealed: boolean;
  onReveal: () => void;
}) {
  return (
    <div className="space-y-8">
      <LeadHeader record={record} />

      <GuardrailsDashboard record={record} />

      <div>
        <SectionHeader
          eyebrow="Moss · retrieval"
          title="Moss retrieval intelligence"
          description="Four live retrieval streams ground every recommendation in real CA law, comparable settlements, firm fit, and procedure."
        />
        <div className="space-y-4">
          <MossOverview record={record} />
          <MossIntelligencePanel record={record} />
          <CaseflowDecisionCard record={record} />
          <MossEvidenceTrail record={record} />
        </div>
      </div>

      <div>
        <SectionHeader
          eyebrow="Unsiloed · documents"
          title="Document parsing"
          description="Documents the caller holds to the camera are parsed live into structured fields with per-field confidence."
        />
        <div className="space-y-4">
          <UnsiloedParsedPanel record={record} />
          <DocumentsPanel record={record} />
        </div>
      </div>

      <TrueFoundryPrivacyDashboard record={record} revealed={revealed} onReveal={onReveal} />

      <div>
        <SectionHeader
          eyebrow="Conversation"
          title="Intake conversation & delivery"
          description="The verbatim transcript and the speech pipeline that ran the multilingual intake."
        />
        <div className="grid gap-4 lg:grid-cols-2">
          <LiveTranscriptPanel record={record} />
          <VoiceBridgePanel record={record} />
        </div>
      </div>

      <AwsArtifactsPanel record={record} />
    </div>
  );
}

function prettyAccident(value: unknown): string {
  return String(value ?? '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function FirmPage() {
  const router = useRouter();
  const { cases, connected } = useCaseflowEvents();
  const [session, setSession] = useState<FirmSession | null | undefined>(undefined);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [revealedIds, setRevealedIds] = useState<Set<string>>(new Set());
  const [autoBrief, setAutoBrief] = useState(false);

  useEffect(() => {
    setAutoBrief(localStorage.getItem('caseflow_auto_brief') === 'on');
  }, []);

  useEffect(() => {
    fetch('/api/firm/session')
      .then((res) => (res.ok ? res.json() : { session: null }))
      .then((data) => setSession(data.session ?? null))
      .catch(() => setSession(null));
  }, []);

  useEffect(() => {
    if (session === null) router.replace('/firm/login');
  }, [session, router]);

  const firmCases = useMemo(() => {
    if (!session) return [];
    return cases.filter((record) => caseVisibleToFirm(record, session.firm_id));
  }, [cases, session]);

  const selected = useMemo(
    () => firmCases.find((c) => c.case_id === selectedId) ?? firmCases[0],
    [firmCases, selectedId]
  );

  // Auto-brief: when a genuinely new lead arrives (after the initial snapshot),
  // jump straight into the voice briefing. Seeded once so we don't redirect on
  // first load.
  const seenCaseIds = useRef<Set<string> | null>(null);
  useEffect(() => {
    const ids = firmCases.map((c) => String(c.case_id));
    if (seenCaseIds.current === null) {
      seenCaseIds.current = new Set(ids);
      return;
    }
    const fresh = ids.filter((id) => !seenCaseIds.current!.has(id));
    fresh.forEach((id) => seenCaseIds.current!.add(id));
    if (autoBrief && fresh.length > 0) {
      router.push(`/firm/brief/${fresh[0]}`);
    }
  }, [firmCases, autoBrief, router]);

  if (session === undefined) {
    return (
      <div className="text-muted-foreground flex min-h-svh items-center justify-center text-sm">
        Loading firm session…
      </div>
    );
  }

  if (!session) return null;

  return (
    <div className="bg-muted/30 min-h-svh">
      <header className="border-border bg-background border-b px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div>
            <Link href="/" className="text-lg font-semibold tracking-tight">
              Caseflowy <span className="text-muted-foreground font-normal">Intelligence</span>
            </Link>
            <p className="text-muted-foreground text-sm">
              {session.firm_name}
              {session.city ? ` · ${session.city}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="border-border flex items-center gap-1.5 rounded-full border px-2.5 py-1">
              <span
                className={`size-2 rounded-full ${connected ? 'animate-pulse bg-emerald-500' : 'bg-amber-500'}`}
              />
              <span className="text-muted-foreground text-xs font-medium">
                {connected ? 'Live' : 'Reconnecting…'}
              </span>
            </span>
            <Button
              variant={autoBrief ? 'default' : 'outline'}
              size="sm"
              aria-pressed={autoBrief}
              onClick={() => {
                const next = !autoBrief;
                setAutoBrief(next);
                localStorage.setItem('caseflow_auto_brief', next ? 'on' : 'off');
              }}
            >
              {autoBrief ? 'Auto-brief: On' : 'Auto-brief: Off'}
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/admin/metrics">Metrics</Link>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                await fetch('/api/firm/logout', { method: 'POST' });
                router.replace('/firm/login');
              }}
            >
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-6">
        {firmCases.length > 0 ? <FirmKpiStrip cases={firmCases} /> : null}

        <div className="mt-6 grid gap-6 md:grid-cols-[300px_1fr]">
          <aside className="md:sticky md:top-6 md:self-start">
            <div className="border-border bg-background rounded-2xl border p-4">
              <h2 className="text-muted-foreground mb-3 text-xs font-semibold tracking-wide uppercase">
                Incoming cases
              </h2>
              {firmCases.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  No matched intakes yet. Open /intake/consent in another tab, enter San Francisco
                  as your location, and complete a call.
                </p>
              ) : (
                <ul className="space-y-2">
                  {firmCases.map((c) => {
                    const score = Number(c.score ?? c.case_strength ?? 0);
                    const tone = strengthTone(score);
                    const active = selected?.case_id === c.case_id;
                    return (
                      <li key={String(c.case_id)}>
                        <button
                          type="button"
                          onClick={() => setSelectedId(String(c.case_id))}
                          className={`w-full rounded-xl border px-3 py-2.5 text-left transition-colors ${
                            active
                              ? 'border-primary bg-primary/5'
                              : 'border-border hover:bg-muted/50'
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate font-medium">
                              {String(c.caller_id ?? c.case_id)}
                            </span>
                            <span className={`text-sm font-semibold tabular-nums ${tone.text}`}>
                              {score}
                            </span>
                          </div>
                          <div className="text-muted-foreground mt-0.5 flex items-center justify-between gap-2 text-xs">
                            <span className="truncate">
                              {prettyAccident(c.accident_type) || 'Intake'}
                            </span>
                            <span className="tabular-nums">{formatUsd(estimatedValue(c))}</span>
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </aside>

          <main>
            {selected ? (
              <CaseDetail
                record={selected}
                revealed={revealedIds.has(String(selected.case_id))}
                onReveal={async () => {
                  const id = String(selected.case_id);
                  await fetch(`/api/cases/${id}/reveal`, { method: 'POST' });
                  setRevealedIds((prev) => new Set(prev).add(id));
                }}
              />
            ) : (
              <div className="border-border bg-background text-muted-foreground rounded-2xl border border-dashed p-12 text-center">
                Select a case to view its full intelligence dashboard.
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
