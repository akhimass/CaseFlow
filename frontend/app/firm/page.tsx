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
import { SectionHeader, estimatedValue, formatUsd } from '@/components/firm/dashboard/viz';
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

const ACCIDENT_LABEL: Record<string, string> = {
  rear_end: 'Rear-end',
  t_bone: 'T-bone',
  slip_fall: 'Slip & fall',
  dog_bite: 'Dog bite',
  motorcycle: 'Motorcycle',
  pedestrian: 'Pedestrian',
  premises: 'Premises',
  auto: 'Auto',
};

function FirmInfoPanel({ session, cases }: { session: FirmSession; cases: CaseRecord[] }) {
  const total = cases.length;
  const byType: Record<string, number> = {};
  const byStatus: Record<string, number> = {};
  let pipeline = 0;
  let qualified = 0;
  for (const c of cases) {
    const t = String(c.accident_type ?? 'other');
    byType[t] = (byType[t] ?? 0) + 1;
    const s = String(c.status ?? c.last_event ?? 'new');
    byStatus[s] = (byStatus[s] ?? 0) + 1;
    pipeline += estimatedValue(c);
    if (Number(c.score ?? c.case_strength ?? 0) >= 40) qualified += 1;
  }
  const types = Object.entries(byType).sort((a, b) => b[1] - a[1]);
  const maxType = Math.max(1, ...types.map(([, n]) => n));

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{session.firm_name}</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            {session.city ? `${session.city} · ` : ''}Firm breakdown
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href="/firm/login">Switch firm</Link>
        </Button>
      </div>

      {total === 0 ? (
        <p className="text-muted-foreground text-sm">No matched cases yet.</p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              { label: 'Matched cases', value: String(total) },
              { label: 'Qualified', value: `${qualified}/${total}` },
              { label: 'Pipeline value', value: formatUsd(pipeline) },
              {
                label: 'Booked',
                value: String((byStatus['booked'] ?? 0) + (byStatus['consult_booked'] ?? 0)),
              },
            ].map((k) => (
              <div key={k.label} className="border-border bg-background rounded-xl border p-4">
                <div className="text-muted-foreground text-[11px] font-semibold tracking-wide uppercase">
                  {k.label}
                </div>
                <div className="mt-1 text-2xl font-bold tabular-nums">{k.value}</div>
              </div>
            ))}
          </div>

          <div className="border-border bg-background rounded-xl border p-5">
            <h3 className="text-muted-foreground mb-3 text-xs font-semibold tracking-wide uppercase">
              Case-type mix
            </h3>
            <div className="space-y-2">
              {types.map(([t, n]) => (
                <div key={t} className="flex items-center gap-3 text-sm">
                  <span className="w-28 shrink-0">{ACCIDENT_LABEL[t] ?? t.replace(/_/g, ' ')}</span>
                  <div className="bg-muted h-2.5 flex-1 overflow-hidden rounded-full">
                    <div
                      className="bg-primary h-full rounded-full"
                      style={{ width: `${(n / maxType) * 100}%` }}
                    />
                  </div>
                  <span className="text-muted-foreground w-6 text-right tabular-nums">{n}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
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
      view={view}
      onViewChange={(next) => {
        setView(next);
        setSelectedId(null);
      }}
      autoBrief={autoBrief}
      onToggleAutoBrief={() => {
        const next = !autoBrief;
        setAutoBrief(next);
        localStorage.setItem('caseflow_auto_brief', next ? 'on' : 'off');
      }}
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
        <FirmHomeDashboard session={session} firmCases={firmCases} onSelectCase={openCase} />
      ) : view === 'metrics' ? (
        <FirmMetricsPanel />
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
        <FirmInfoPanel session={session} cases={firmCases} />
      ) : null}
    </FirmDashboardShell>
  );
}
