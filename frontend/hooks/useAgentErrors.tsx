import { ReactNode, useEffect } from 'react';
import { toast as sonnerToast } from 'sonner';
import { useAgent, useSessionContext } from '@livekit/components-react';
import { WarningIcon } from '@phosphor-icons/react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface ToastProps {
  title: ReactNode;
  description: ReactNode;
}

function toastAlert(toast: ToastProps) {
  const { title, description } = toast;

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

export function useAgentErrors(agentName = 'caseflow-agent') {
  const agent = useAgent();
  const { isConnected, end } = useSessionContext();

  useEffect(() => {
    if (isConnected && agent.state === 'failed') {
      const reasons = agent.failureReasons;
      const isLocal =
        typeof window !== 'undefined' &&
        (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

      toastAlert({
        title: 'The intake specialist could not join the call',
        description: (
          <>
            {reasons.length > 0 ? (
              <>
                <p className="mb-2 w-full font-medium">What went wrong:</p>
                {reasons.length > 1 ? (
                  <ul className="mb-2 list-inside list-disc">
                    {reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mb-2 w-full">{reasons[0]}</p>
                )}
              </>
            ) : (
              <p className="mb-2 w-full">
                No agent worker accepted the dispatch for{' '}
                <code className="text-xs">{agentName}</code>.
              </p>
            )}
            {isLocal ? (
              <p className="w-full">
                In <code className="text-xs">agent-py</code>, run{' '}
                <code className="text-xs">uv run src/agent.py dev</code> and confirm logs show{' '}
                <code className="text-xs">registered worker</code> with agent name{' '}
                <code className="text-xs">{agentName}</code>. Stop any other local agent using{' '}
                <code className="text-xs">caseflow-agent</code> — that steals production sessions.
              </p>
            ) : (
              <p className="w-full">
                The cloud agent may be restarting. Wait 30 seconds and try again. If it keeps
                failing, check LiveKit Cloud agent status for{' '}
                <code className="text-xs">caseflow-agent</code>.
              </p>
            )}
          </>
        ),
      });

      end();
    }
  }, [agent, agentName, isConnected, end]);
}
