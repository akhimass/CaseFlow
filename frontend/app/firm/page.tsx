'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeftIcon } from '@phosphor-icons/react/dist/ssr';
import { AwsArtifactsPanel } from '@/components/firm/aws-artifacts-panel';
import { CaseflowDecisionCard } from '@/components/firm/caseflow-decision-card';
import { FirmCasesView } from '@/components/firm/dashboard/firm-cases-view';
import {
  FirmDashboardShell,
  type FirmDashboardView,
} from '@/components/firm/dashboard/firm-dashboard-shell';
import { FirmHomeDashboard } from '@/components/firm/dashboard/firm-home';
import { FirmKpiStrip } from '@/components/firm/dashboard/firm-kpis';
import { FirmMetricsPanel } from '@/components/firm/dashboard/firm-metrics-panel';
import { GuardrailsDashboard } from '@/components/firm/dashboard/guardrails';
import { LeadHeader } from '@/components/firm/dashboard/lead-header';
import { MossOverview } from '@/components/firm/dashboard/moss-overview';
import { TrueFoundryPrivacyDashboard } from '@/components/firm/dashboard/truefoundry-privacy';
import { SectionHeader } from '@/components/firm/dashboard/viz';
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
  onBack,
}: {
  record: CaseRecord;
  revealed: boolean;
  onReveal: () => void;
  onBack: () => void;
}) {
  return (
    <div className="space-y-6">
      <Button type="button" variant="ghost" size="sm" onClick={onBack}>
        <ArrowLeftIcon weight="bold" /> Back to cases
      </Button>
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

function FirmInfoPanel({ session }: { session: FirmSession }) {
  return (
    <div className="border-border bg-background max-w-lg space-y-3 rounded-xl border p-6">
      <h2 className="text-lg font-semibold">{session.firm_name}</h2>
      {session.city ? <p className="text-muted-foreground text-sm">{session.city}</p> : null}
      <p className="text-muted-foreground text-sm leading-relaxed">
        Matched leads appear in the left sidebar and in the Cases table. Home is Caseflowy Counsel
        with a live transcript — open any lead for the full dossier or a voice briefing.
      </p>
      <Button asChild variant="outline" size="sm">
        <Link href="/firm/login">Switch firm</Link>
      </Button>
    </div>
  );
}

export default function FirmPage() {
  const router = useRouter();
  const { cases, connected } = useCaseflowEvents();
  const [session, setSession] = useState<FirmSession | null | undefined>(undefined);
  const [view, setView] = useState<FirmDashboardView>('home');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [revealedIds, setRevealedIds] = useState<Set<string>>(new Set());
  const [autoBrief, setAutoBrief] = useState(
    () => typeof window !== 'undefined' && localStorage.getItem('caseflow_auto_brief') === 'on'
  );

  useEffect(() => {
    fetch('/api/firm/session')
      .then((res) => (res.ok ? res.json() : { session: null }))
      .then((data) => setSession(data.session ?? null))
      .catch(() => setSession(null));
  }, []);

  useEffect(() => {
    if (session === null) router.replace('/firm/login');
  }, [session, router]);

  // Every firm sign-in lands on the home dashboard (Counsel), never a case dossier.
  const seenCaseIds = useRef<Set<string>>(new Set());
  const snapshotSeeded = useRef(false);
  useEffect(() => {
    if (!session?.firm_id) return;
    setView('home');
    setSelectedId(null);
    snapshotSeeded.current = false;
    seenCaseIds.current = new Set();
  }, [session?.firm_id]);

  const firmCases = useMemo(() => {
    if (!session) return [];
    return cases.filter((record) => caseVisibleToFirm(record, session.firm_id));
  }, [cases, session]);

  const selected = useMemo(
    () => (selectedId ? firmCases.find((c) => c.case_id === selectedId) : undefined),
    [firmCases, selectedId]
  );

  // Seed once after the SSE snapshot lands so demo/historical leads are never
  // treated as "new" (empty-then-populate and late autoBrief hydration both
  // used to auto-redirect to demo-sofia-reyes on sign-in).
  useEffect(() => {
    if (!session || !connected) return;

    const ids = firmCases.map((c) => String(c.case_id));
    if (!snapshotSeeded.current) {
      if (ids.length === 0) return;
      seenCaseIds.current = new Set(ids);
      snapshotSeeded.current = true;
      return;
    }

    const fresh = ids.filter((id) => !seenCaseIds.current.has(id));
    fresh.forEach((id) => seenCaseIds.current.add(id));
    if (autoBrief && fresh.length > 0) {
      router.push(`/firm/brief/${fresh[0]}`);
    }
  }, [firmCases, autoBrief, connected, session, router]);

  function openCase(caseId: string) {
    setSelectedId(caseId);
    setView('cases');
  }

  if (session === undefined) {
    return (
      <div className="text-muted-foreground flex min-h-svh items-center justify-center text-sm">
        Loading firm session…
      </div>
    );
  }

  if (!session) return null;

  return (
    <FirmDashboardShell
      session={session}
      connected={connected}
      view={selectedId ? 'cases' : view}
      onViewChange={(next) => {
        setView(next);
        if (next !== 'cases') setSelectedId(null);
      }}
      autoBrief={autoBrief}
      onToggleAutoBrief={() => {
        const next = !autoBrief;
        setAutoBrief(next);
        localStorage.setItem('caseflow_auto_brief', next ? 'on' : 'off');
      }}
      firmCases={firmCases}
      selectedCaseId={selectedId}
      onSelectCase={openCase}
    >
      {selected ? (
        <CaseDetail
          record={selected}
          revealed={revealedIds.has(String(selected.case_id))}
          onReveal={async () => {
            const id = String(selected.case_id);
            await fetch(`/api/cases/${id}/reveal`, { method: 'POST' });
            setRevealedIds((prev) => new Set(prev).add(id));
          }}
          onBack={() => setSelectedId(null)}
        />
      ) : view === 'home' ? (
        <FirmHomeDashboard session={session} />
      ) : view === 'metrics' ? (
        <FirmMetricsPanel />
      ) : view === 'cases' ? (
        <FirmCasesView firmCases={firmCases} onSelectCase={openCase} />
      ) : view === 'overview' ? (
        <div className="space-y-6">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
            <p className="text-muted-foreground mt-1 text-sm">
              Pipeline snapshot for {session.firm_name}
            </p>
          </div>
          {firmCases.length > 0 ? <FirmKpiStrip cases={firmCases} /> : null}
          <FirmCasesView firmCases={firmCases} onSelectCase={openCase} />
        </div>
      ) : view === 'firm' ? (
        <FirmInfoPanel session={session} />
      ) : null}
    </FirmDashboardShell>
  );
}
