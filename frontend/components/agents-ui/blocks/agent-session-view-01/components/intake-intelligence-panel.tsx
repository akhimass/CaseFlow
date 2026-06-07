'use client';

import { type AgentState, type ReceivedMessage } from '@livekit/components-react';
import { AgentChatTranscript } from '@/components/agents-ui/agent-chat-transcript';
import { DocumentParsingPanel } from '@/components/app/document-parsing-panel';
import { MossResultsPanel } from '@/components/app/moss-results-panel';
import type { DocumentParseEvent } from '@/hooks/useDocumentParseEvents';
import type { MossContextEvent } from '@/hooks/useMossContextEvents';

interface IntakeIntelligencePanelProps {
  agentState: AgentState;
  messages: ReceivedMessage[];
  mossEvents: MossContextEvent[];
  documentParseEvents: DocumentParseEvent[];
  showMoss: boolean;
}

export function IntakeIntelligencePanel({
  agentState,
  messages,
  mossEvents,
  documentParseEvents,
  showMoss,
}: IntakeIntelligencePanelProps) {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="border-border shrink-0 border-b px-4 py-3 lg:px-6">
          <h2 className="text-sm font-semibold tracking-tight">Conversation</h2>
          <p className="text-muted-foreground text-xs">
            Aria speaks aloud — transcript updates here
          </p>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2 lg:px-4">
          <AgentChatTranscript
            agentState={agentState}
            messages={messages}
            className="h-full [&_.is-user>div]:rounded-[22px] [&>div>div]:px-2 [&>div>div]:pt-2 lg:[&>div>div]:px-0"
          />
        </div>
      </div>

      <div className="border-border max-h-[42%] shrink-0 overflow-y-auto border-t px-4 py-4 lg:px-6">
        <div className="space-y-4">
          <DocumentParsingPanel events={documentParseEvents} />
          <MossResultsPanel events={mossEvents} hidden={!showMoss} />
        </div>
      </div>
    </div>
  );
}
