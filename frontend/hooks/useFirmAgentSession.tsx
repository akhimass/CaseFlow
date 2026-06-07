'use client';

import { ReactNode, useEffect, useRef } from 'react';
import { toast as sonnerToast } from 'sonner';
import { useAgent, useSessionContext } from '@livekit/components-react';
import { WarningIcon } from '@phosphor-icons/react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

function toastAlert(title: ReactNode, description: ReactNode) {
  return sonnerToast.custom(
    (id) => (
      <Alert onClick={() => sonnerToast.dismiss(id)} className="bg-accent w-full md:w-[364px]">
        <WarningIcon weight="bold" />
        <AlertTitle>{title}</AlertTitle>
        {description && <AlertDescription>{description}</AlertDescription>}
      </Alert>
    ),
    { duration: 10_000 }
  );
}

/**
 * Connects the firm-side LiveKit session on mount (mic off — counsel narrates first)
 * and disconnects on unmount. Intake waits for an explicit start button; firm pages
 * should connect immediately when the dashboard or briefing room loads.
 */
export function useFirmAgentAutoConnect() {
  const session = useSessionContext();
  const started = useRef(false);
  const startRef = useRef(session.start);
  const endRef = useRef(session.end);
  startRef.current = session.start;
  endRef.current = session.end;

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    const controller = new AbortController();
    void startRef
      .current({
        signal: controller.signal,
        tracks: { microphone: { enabled: false } },
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        console.error('Firm agent session failed to start:', err);
        started.current = false;
      });

    return () => {
      controller.abort();
      void endRef.current();
      started.current = false;
    };
    // Mount/unmount only — session object identity changes on every connection
    // state tick; depending on it would disconnect mid-briefing.
  }, []);
}

/** Surfaces agent dispatch failures for firm home + briefing rooms. */
export function useFirmAgentErrors(agentName = 'caseflow-agent') {
  const agent = useAgent();
  const { isConnected, end } = useSessionContext();

  useEffect(() => {
    if (!isConnected || agent.state !== 'failed') return;

    const reasons = agent.failureReasons;
    const isLocal =
      typeof window !== 'undefined' &&
      (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

    toastAlert(
      'Caseflowy Counsel could not join',
      <>
        {reasons.length > 0 ? (
          <p className="mb-2 w-full">{reasons.join(' · ')}</p>
        ) : (
          <p className="mb-2 w-full">
            No agent worker accepted the dispatch for <code className="text-xs">{agentName}</code>.
          </p>
        )}
        {isLocal ? (
          <p className="w-full">
            Run <code className="text-xs">uv run src/agent.py dev</code> in{' '}
            <code className="text-xs">agent-py</code> with agent name{' '}
            <code className="text-xs">{agentName}</code>.
          </p>
        ) : (
          <p className="w-full">
            The cloud agent may be restarting. Wait 30 seconds and refresh. If it persists, check
            LiveKit Cloud agent status.
          </p>
        )}
      </>
    );

    end();
  }, [agent, agentName, isConnected, end]);
}
