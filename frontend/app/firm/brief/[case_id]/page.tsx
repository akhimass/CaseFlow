'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { TokenSource } from 'livekit-client';
import { useSession } from '@livekit/components-react';
import { WarningIcon } from '@phosphor-icons/react/dist/ssr';
import { APP_CONFIG_DEFAULTS } from '@/app-config';
import { AgentSessionProvider } from '@/components/agents-ui/agent-session-provider';
import { StartAudioButton } from '@/components/agents-ui/start-audio-button';
import { BriefingRoom } from '@/components/firm/briefing/briefing-room';
import { Toaster } from '@/components/ui/sonner';
import { type CaseRecord, useCaseflowEvents } from '@/hooks/useCaseflowEvents';
import { useFirmAgentAutoConnect, useFirmAgentErrors } from '@/hooks/useFirmAgentSession';
import { type FirmSession } from '@/lib/firm-session';

const AGENT_NAME = APP_CONFIG_DEFAULTS.agentName ?? 'caseflow-agent';

function FirmBriefAgentSetup() {
  useFirmAgentAutoConnect();
  useFirmAgentErrors(AGENT_NAME);
  return null;
}

export default function FirmBriefPage() {
  const router = useRouter();
  const params = useParams<{ case_id: string }>();
  const caseId = String(params.case_id);
  const [session, setSession] = useState<FirmSession | null | undefined>(undefined);
  const [paused, setPaused] = useState(false);
  const [seeded, setSeeded] = useState<CaseRecord | null>(null);
  const { cases } = useCaseflowEvents();

  useEffect(() => {
    fetch('/api/firm/session')
      .then((res) => (res.ok ? res.json() : { session: null }))
      .then((data) => setSession(data.session ?? null))
      .catch(() => setSession(null));
  }, []);

  useEffect(() => {
    if (session === null) router.replace('/firm/login');
  }, [session, router]);

  // Seed the record immediately from the single-case endpoint so the cards are
  // populated before the SSE snapshot lands.
  useEffect(() => {
    let cancelled = false;
    fetch(`/api/cases/${caseId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data?.case) setSeeded(data.case as CaseRecord);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  const tokenSource = useMemo(() => {
    if (!session) return null;
    return TokenSource.custom(async () => {
      const res = await fetch('/api/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          room_config: { agents: [{ agent_name: AGENT_NAME }] },
          agent_metadata: {
            mode: 'firm_briefing',
            case_id: caseId,
            firm_id: session.firm_id,
          },
        }),
      });
      if (!res.ok) throw new Error('Failed to fetch connection details');
      return res.json();
    });
  }, [session, caseId]);

  if (session === undefined) {
    return (
      <div className="text-muted-foreground flex min-h-svh items-center justify-center text-sm">
        Loading firm session…
      </div>
    );
  }
  if (!session) return null;

  return (
    <BriefSession
      tokenSource={tokenSource}
      caseId={caseId}
      firmName={session.firm_name}
      cases={cases}
      seeded={seeded}
      paused={paused}
      onTogglePause={() => setPaused((p) => !p)}
    />
  );
}

function BriefSession({
  tokenSource,
  caseId,
  firmName,
  cases,
  seeded,
  paused,
  onTogglePause,
}: {
  tokenSource: ReturnType<typeof TokenSource.custom> | null;
  caseId: string;
  firmName: string;
  cases: CaseRecord[];
  seeded: CaseRecord | null;
  paused: boolean;
  onTogglePause: () => void;
}) {
  const liveSession = useSession(tokenSource ?? TokenSource.custom(async () => ({}) as never), {
    agentName: AGENT_NAME,
    agentConnectTimeoutMilliseconds: 60_000,
  });

  const record = useMemo<CaseRecord>(() => {
    const live = cases.find((c) => c.case_id === caseId);
    return { ...(seeded ?? {}), ...(live ?? {}), case_id: caseId };
  }, [cases, caseId, seeded]);

  return (
    <AgentSessionProvider session={liveSession} muted={paused}>
      <FirmBriefAgentSetup />
      <BriefingRoom
        record={record}
        caseId={caseId}
        firmName={firmName}
        paused={paused}
        onTogglePause={onTogglePause}
      />
      <StartAudioButton label="Start briefing audio" />
      <Toaster position="top-center" icons={{ warning: <WarningIcon weight="bold" /> }} />
    </AgentSessionProvider>
  );
}
