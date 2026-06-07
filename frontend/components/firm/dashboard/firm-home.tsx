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
import { StartAudioButton } from '@/components/agents-ui/start-audio-button';
import { FirmCasesView } from '@/components/firm/dashboard/firm-cases-view';
import { FirmCounselControls } from '@/components/firm/dashboard/firm-counsel-controls';
import { Toaster } from '@/components/ui/sonner';
import { type CaseRecord } from '@/hooks/useCaseflowEvents';
import { useFirmAgentAutoConnect, useFirmAgentErrors } from '@/hooks/useFirmAgentSession';
import { type FirmSession } from '@/lib/firm-session';

const AGENT_NAME = APP_CONFIG_DEFAULTS.agentName ?? 'caseflow-agent';

function FirmAgentSetup() {
  useFirmAgentAutoConnect();
  useFirmAgentErrors(AGENT_NAME);
  return null;
}

function FirmCounselConversation() {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const { state: agentState } = useVoiceAssistant();

  return (
    <div className="border-border bg-background flex h-full min-h-[28rem] flex-col overflow-hidden rounded-2xl border lg:min-h-0">
      <div className="border-border shrink-0 border-b px-4 py-3">
        <h2 className="text-sm font-semibold tracking-tight">Conversation</h2>
        <p className="text-muted-foreground text-xs">
          Caseflowy Counsel — turn your mic on to talk; transcript updates live
        </p>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
        <AgentChatTranscript
          agentState={agentState}
          messages={messages}
          className="h-full [&_.is-user>div]:rounded-[22px] [&>div>div]:px-2 [&>div>div]:pt-2"
        />
      </div>
      <div className="border-border shrink-0 border-t px-4 py-3">
        <FirmCounselControls className="w-full" />
      </div>
    </div>
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
    <div className="grid min-h-[min(72vh,720px)] gap-4 lg:grid-cols-2">
      <div className="flex min-h-0 flex-col overflow-hidden">
        <div className="mb-3 shrink-0">
          <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
            Cases hub
          </p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight">
            Matched leads for {session.firm_name}
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Live intakes matched to your firm — open a dossier or start a voice briefing.
          </p>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          <FirmCasesView firmCases={firmCases} onSelectCase={onSelectCase} />
        </div>
      </div>
      <FirmCounselConversation />
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
