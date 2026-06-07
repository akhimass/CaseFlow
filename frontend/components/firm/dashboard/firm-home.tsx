'use client';

import { useMemo } from 'react';
import { TokenSource } from 'livekit-client';
import {
  useSession,
  useSessionContext,
  useSessionMessages,
  useVoiceAssistant,
} from '@livekit/components-react';
import { WarningIcon } from '@phosphor-icons/react/dist/ssr';
import { APP_CONFIG_DEFAULTS } from '@/app-config';
import { AgentChatTranscript } from '@/components/agents-ui/agent-chat-transcript';
import { AgentSessionProvider } from '@/components/agents-ui/agent-session-provider';
import { AudioVisualizer } from '@/components/agents-ui/blocks/agent-session-view-01/components/audio-visualizer';
import { StartAudioButton } from '@/components/agents-ui/start-audio-button';
import { FirmCounselControls } from '@/components/firm/dashboard/firm-counsel-controls';
import { Toaster } from '@/components/ui/sonner';
import { useFirmAgentAutoConnect, useFirmAgentErrors } from '@/hooks/useFirmAgentSession';
import { type FirmSession } from '@/lib/firm-session';

const AGENT_NAME = APP_CONFIG_DEFAULTS.agentName ?? 'caseflow-agent';

function FirmAgentSetup() {
  useFirmAgentAutoConnect();
  useFirmAgentErrors(AGENT_NAME);
  return null;
}

function FirmCounselTranscript() {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const { state: agentState } = useVoiceAssistant();

  return (
    <div className="border-border bg-background flex h-full min-h-[22rem] flex-col overflow-hidden rounded-2xl border lg:min-h-0">
      <div className="border-border shrink-0 border-b px-4 py-3">
        <h2 className="text-sm font-semibold tracking-tight">Conversation</h2>
        <p className="text-muted-foreground text-xs">
          Turn your mic on to talk — transcript updates here live
        </p>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        <AgentChatTranscript
          agentState={agentState}
          messages={messages}
          className="h-full [&_.is-user>div]:rounded-[22px] [&>div>div]:px-2 [&>div>div]:pt-2"
        />
      </div>
    </div>
  );
}

function FirmHomeAgentPanel({ firmName }: { firmName: string }) {
  const { state: agentState } = useVoiceAssistant();
  const connecting = agentState === 'connecting' || agentState === 'initializing';

  return (
    <div className="border-border bg-background flex h-full min-h-[22rem] flex-col items-center justify-center rounded-2xl border px-6 py-8 text-center">
      <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
        Caseflowy Counsel
      </p>
      <h2 className="mt-2 text-2xl font-semibold tracking-tight">
        Your marketplace command center
      </h2>
      <p className="text-muted-foreground mt-2 max-w-md text-sm leading-relaxed">
        Matched leads are in the left sidebar. Use the mic below to have a conversation with Counsel
        — same controls as client intake.
      </p>

      <div className="relative mt-6 flex h-36 w-full items-center justify-center">
        <AudioVisualizer
          isChatOpen={false}
          audioVisualizerType="aura"
          audioVisualizerColor="#2563EB"
          className="!size-36"
        />
      </div>

      <p className="text-muted-foreground mt-4 min-h-[3rem] max-w-md text-sm leading-relaxed">
        {connecting
          ? 'Connecting to Caseflowy Counsel…'
          : agentState === 'speaking'
            ? 'Counsel is speaking — follow along in the transcript.'
            : agentState === 'listening'
              ? 'Listening — speak anytime.'
              : `Welcome back${firmName ? `, ${firmName}` : ''}. Counsel is ready.`}
      </p>
    </div>
  );
}

function FirmHomeContent({ session }: { session: FirmSession }) {
  return (
    <div className="flex min-h-[min(72vh,680px)] flex-col gap-4">
      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-2">
        <FirmHomeAgentPanel firmName={session.firm_name} />
        <FirmCounselTranscript />
      </div>
      <div className="border-border shrink-0 border-t pt-4">
        <FirmCounselControls className="mx-auto max-w-3xl" />
      </div>
    </div>
  );
}

function FirmHomeSession({ session }: { session: FirmSession }) {
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
      <FirmHomeContent session={session} />
      <StartAudioButton label="Start Counsel audio" />
      <Toaster position="top-center" icons={{ warning: <WarningIcon weight="bold" /> }} />
    </AgentSessionProvider>
  );
}

export function FirmHomeDashboard({ session }: { session: FirmSession }) {
  return <FirmHomeSession session={session} />;
}
