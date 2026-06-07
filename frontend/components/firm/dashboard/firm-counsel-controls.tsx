'use client';

import { type ReactNode } from 'react';
import { useSessionContext } from '@livekit/components-react';
import { AgentControlBar } from '@/components/agents-ui/agent-control-bar';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/shadcn/utils';

type FirmCounselControlsProps = {
  leaveLabel?: string;
  onLeave?: () => void;
  extraControls?: ReactNode;
  className?: string;
};

/** Mic toggle + end session — same control pattern as client intake. */
export function FirmCounselControls({
  leaveLabel = 'END CALL',
  onLeave,
  extraControls,
  className,
}: FirmCounselControlsProps) {
  const session = useSessionContext();

  const handleDisconnect = () => {
    onLeave?.();
    // AgentDisconnectButton calls session.end() after onClick.
  };

  if (!session.isConnected) {
    return (
      <div className={cn('w-full', className)}>
        <Button
          size="lg"
          className="w-full"
          onClick={() =>
            void session.start({
              tracks: { microphone: { enabled: false } },
            })
          }
        >
          Talk to Counsel
        </Button>
      </div>
    );
  }

  return (
    <div className={cn('flex w-full flex-wrap items-center justify-center gap-2', className)}>
      {extraControls}
      <AgentControlBar
        variant="livekit"
        controls={{
          leave: true,
          microphone: true,
          camera: false,
          screenShare: false,
          chat: false,
        }}
        isChatOpen={false}
        isConnected={session.isConnected}
        onDisconnect={handleDisconnect}
        onIsChatOpenChange={() => undefined}
        leaveLabel={leaveLabel}
        className="w-auto shrink-0"
      />
    </div>
  );
}
