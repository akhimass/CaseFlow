'use client';

import { useEffect, useMemo, useRef } from 'react';
import Link from 'next/link';
import { TokenSource } from 'livekit-client';
import { useLocalParticipant, useSession, useVoiceAssistant } from '@livekit/components-react';
import { MicrophoneIcon, MicrophoneSlashIcon, WarningIcon } from '@phosphor-icons/react/dist/ssr';
import { APP_CONFIG_DEFAULTS } from '@/app-config';
import { AgentSessionProvider } from '@/components/agents-ui/agent-session-provider';
import { AudioVisualizer } from '@/components/agents-ui/blocks/agent-session-view-01/components/audio-visualizer';
import { StartAudioButton } from '@/components/agents-ui/start-audio-button';
import { Button } from '@/components/ui/button';
import { Toaster } from '@/components/ui/sonner';
import { type CaseRecord } from '@/hooks/useCaseflowEvents';
import { useFirmAgentAutoConnect, useFirmAgentErrors } from '@/hooks/useFirmAgentSession';
import { type FirmSession } from '@/lib/firm-session';
import { cn } from '@/lib/shadcn/utils';
import { estimatedValue, formatUsd, strengthTone } from './viz';

const AGENT_NAME = APP_CONFIG_DEFAULTS.agentName ?? 'caseflow-agent';

function FirmAgentSetup() {
  useFirmAgentAutoConnect();
  useFirmAgentErrors(AGENT_NAME);
  return null;
}

function prettyAccident(value: unknown): string {
  return String(value ?? '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function FirmHomeAgentPanel({ firmName }: { firmName: string }) {
  const { state: agentState } = useVoiceAssistant();
  const connecting = agentState === 'connecting' || agentState === 'initializing';

  return (
    <div className="border-border bg-background flex flex-col items-center rounded-2xl border px-6 py-8 text-center">
      <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
        Caseflowy Counsel
      </p>
      <h2 className="mt-2 text-2xl font-semibold tracking-tight">
        Your marketplace command center
      </h2>
      <p className="text-muted-foreground mt-2 max-w-lg text-sm leading-relaxed">
        Matched leads appear in the sidebar. Select one for the full dossier, or open a voice
        briefing on any lead. Ask Counsel about your pipeline anytime.
      </p>

      <div className="relative mt-6 flex h-40 w-full items-center justify-center">
        <AudioVisualizer
          isChatOpen={false}
          audioVisualizerType="aura"
          audioVisualizerColor="#2563EB"
          className="!size-40"
        />
      </div>

      <p className="text-muted-foreground mt-4 min-h-[3rem] max-w-xl text-sm leading-relaxed">
        {connecting
          ? 'Connecting to Caseflowy Counsel…'
          : agentState === 'speaking'
            ? 'Counsel is speaking — use the mic below to ask a follow-up.'
            : `Welcome back${firmName ? `, ${firmName}` : ''}. Your agent is ready when you are.`}
      </p>

      <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
        <HomeMicToggle />
        <span className="text-muted-foreground text-xs">
          {agentState === 'listening' ? 'Listening' : 'Tap mic to ask a question'}
        </span>
      </div>
    </div>
  );
}

function HomeMicToggle() {
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const micInitialized = useRef(false);

  useEffect(() => {
    if (localParticipant && !micInitialized.current) {
      micInitialized.current = true;
      void localParticipant.setMicrophoneEnabled(false);
    }
  }, [localParticipant]);

  return (
    <Button
      type="button"
      variant={isMicrophoneEnabled ? 'default' : 'outline'}
      size="sm"
      onClick={() => void localParticipant?.setMicrophoneEnabled(!isMicrophoneEnabled)}
    >
      {isMicrophoneEnabled ? (
        <MicrophoneIcon weight="bold" />
      ) : (
        <MicrophoneSlashIcon weight="bold" />
      )}
      {isMicrophoneEnabled ? 'Mic on' : 'Ask a question'}
    </Button>
  );
}

function FirmHomeContent({
  session,
  firmCases,
  onSelectCase,
}: {
  session: FirmSession;
  firmCases: CaseRecord[];
  onSelectCase: (caseId: string) => void;
}) {
  return (
    <div className="space-y-6">
      <FirmHomeAgentPanel firmName={session.firm_name} />

      <div className="border-border bg-background rounded-2xl border p-5">
        <h3 className="text-sm font-semibold">Your matched leads</h3>
        <p className="text-muted-foreground mt-1 text-sm">
          {firmCases.length === 0
            ? 'No intakes yet. Run a client call from /intake — new leads will appear here live.'
            : `${firmCases.length} lead${firmCases.length === 1 ? '' : 's'} in your queue. Open one to review evidence, Moss retrieval, and guardrails.`}
        </p>

        {firmCases.length > 0 ? (
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {firmCases.map((c) => {
              const score = Number(c.score ?? c.case_strength ?? 0);
              const tone = strengthTone(score);
              const id = String(c.case_id);
              const isDemo = id.startsWith('demo-');
              return (
                <li key={id} className="border-border flex flex-col gap-3 rounded-xl border p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-medium">{String(c.caller_id ?? id)}</div>
                      <div className="text-muted-foreground text-xs capitalize">
                        {prettyAccident(c.accident_type) || 'Intake'}
                        {isDemo ? ' · Demo seed' : ''}
                      </div>
                    </div>
                    <span className={cn('text-sm font-semibold tabular-nums', tone.text)}>
                      {score}
                    </span>
                  </div>
                  <div className="text-muted-foreground text-xs tabular-nums">
                    Est. {formatUsd(estimatedValue(c))}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" size="sm" onClick={() => onSelectCase(id)}>
                      View dossier
                    </Button>
                    <Button asChild type="button" size="sm" variant="outline">
                      <Link href={`/firm/brief/${id}`}>Voice briefing</Link>
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

function FirmHomeSession({
  session,
  firmCases,
  onSelectCase,
}: {
  session: FirmSession;
  firmCases: CaseRecord[];
  onSelectCase: (caseId: string) => void;
}) {
  const tokenSource = useMemo(
    () =>
      TokenSource.custom(async () => {
        const res = await fetch('/api/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            room_config: { agents: [{ agent_name: AGENT_NAME }] },
            agent_metadata: {
              mode: 'firm_home',
              firm_id: session.firm_id,
              firm_name: session.firm_name,
            },
          }),
        });
        if (!res.ok) throw new Error('Failed to fetch connection details');
        return res.json();
      }),
    [session.firm_id, session.firm_name]
  );

  const liveSession = useSession(tokenSource, {
    agentName: AGENT_NAME,
    agentConnectTimeoutMilliseconds: 60_000,
  });

  return (
    <AgentSessionProvider session={liveSession}>
      <FirmAgentSetup />
      <FirmHomeContent session={session} firmCases={firmCases} onSelectCase={onSelectCase} />
      <StartAudioButton label="Start Counsel audio" />
      <Toaster position="top-center" icons={{ warning: <WarningIcon weight="bold" /> }} />
    </AgentSessionProvider>
  );
}

export function FirmHomeDashboard({
  session,
  firmCases,
  onSelectCase,
}: {
  session: FirmSession;
  firmCases: CaseRecord[];
  onSelectCase: (caseId: string) => void;
}) {
  return <FirmHomeSession session={session} firmCases={firmCases} onSelectCase={onSelectCase} />;
}
