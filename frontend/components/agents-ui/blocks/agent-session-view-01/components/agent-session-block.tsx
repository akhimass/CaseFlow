'use client';

import React from 'react';
import { type MotionProps, motion } from 'motion/react';
import { toast } from 'sonner';
import { useAgent, useSessionContext, useSessionMessages } from '@livekit/components-react';
import {
  AgentControlBar,
  type AgentControlBarControls,
} from '@/components/agents-ui/agent-control-bar';
import { useDocumentCapture } from '@/hooks/useDocumentCapture';
import { useDocumentParseEvents } from '@/hooks/useDocumentParseEvents';
import { useFirmRecommendations } from '@/hooks/useFirmRecommendations';
import { useMossContextEvents } from '@/hooks/useMossContextEvents';
import { cn } from '@/lib/shadcn/utils';
import { IntakeIntelligencePanel } from './intake-intelligence-panel';
import { IntakeMediaPanel } from './intake-media-panel';

const BOTTOM_VIEW_MOTION_PROPS: MotionProps = {
  variants: {
    visible: {
      opacity: 1,
      translateY: '0%',
    },
    hidden: {
      opacity: 0,
      translateY: '100%',
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.3,
    delay: 0.5,
    ease: 'easeOut',
  },
};

interface FadeProps {
  top?: boolean;
  bottom?: boolean;
  className?: string;
}

export function Fade({ top = false, bottom = false, className }: FadeProps) {
  return (
    <div
      className={cn(
        'from-background pointer-events-none h-4 bg-linear-to-b to-transparent',
        top && 'bg-linear-to-b',
        bottom && 'bg-linear-to-t',
        className
      )}
    />
  );
}

export interface AgentSessionView_01Props {
  /**
   * Message shown above the controls before the first chat message is sent.
   *
   * @default 'Agent is listening, ask it a question'
   */
  preConnectMessage?: string;
  /**
   * Enables or disables the chat toggle and transcript input controls.
   *
   * @default true
   */
  supportsChatInput?: boolean;
  /**
   * Enables or disables camera controls in the bottom control bar.
   *
   * @default true
   */
  supportsVideoInput?: boolean;
  /**
   * Enables or disables screen sharing controls in the bottom control bar.
   *
   * @default true
   */
  supportsScreenShare?: boolean;
  /**
   * Shows a pre-connect buffer state with a shimmer message before messages appear.
   *
   * @default true
   */
  isPreConnectBufferEnabled?: boolean;

  /** Selects the visualizer style rendered in the main tile area. */
  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  /** Primary hex color used by supported audio visualizer variants. */
  audioVisualizerColor?: `#${string}`;
  /** Hue shift intensity used by certain visualizers. */
  audioVisualizerColorShift?: number;
  /** Number of bars to render when `audioVisualizerType` is `bar`. */
  audioVisualizerBarCount?: number;
  /** Number of rows in the visualizer when `audioVisualizerType` is `grid`. */
  audioVisualizerGridRowCount?: number;
  /** Number of columns in the visualizer when `audioVisualizerType` is `grid`. */
  audioVisualizerGridColumnCount?: number;
  /** Number of radial bars when `audioVisualizerType` is `radial`. */
  audioVisualizerRadialBarCount?: number;
  /** Base radius of the radial visualizer when `audioVisualizerType` is `radial`. */
  audioVisualizerRadialRadius?: number;
  /** Stroke width of the wave path when `audioVisualizerType` is `wave`. */
  audioVisualizerWaveLineWidth?: number;
  /** Optional class name merged onto the outer `<section>` container. */
  className?: string;
}

export function AgentSessionView_01({
  preConnectMessage = 'Agent is listening, ask it a question',
  supportsChatInput = true,
  supportsVideoInput = true,
  supportsScreenShare = true,
  isPreConnectBufferEnabled = true,

  audioVisualizerType,
  audioVisualizerColor,
  audioVisualizerColorShift,
  audioVisualizerBarCount,
  audioVisualizerGridRowCount,
  audioVisualizerGridColumnCount,
  audioVisualizerRadialBarCount,
  audioVisualizerRadialRadius,
  audioVisualizerWaveLineWidth,
  ref,
  className,
  ...props
}: React.ComponentProps<'section'> & AgentSessionView_01Props) {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const { state: agentState } = useAgent();
  const conversationStarted = messages.some((message) => message.from?.isLocal === true);
  const ariaActive =
    agentState === 'listening' || agentState === 'speaking' || agentState === 'thinking';
  // Live "Knowledge Matches" surfaced from the agent's `moss_context` data messages.
  const mossEvents = useMossContextEvents();
  const documentParseEvents = useDocumentParseEvents();
  const firmRecommendations = useFirmRecommendations();
  useDocumentCapture();

  // Surface document parsing prominently as a toast — the panel can be below the
  // fold, so this guarantees the caller sees "Reading your document…" / done.
  const lastParseRef = React.useRef<string>('');
  React.useEffect(() => {
    const latest = documentParseEvents[0];
    if (!latest) return;
    const key = `${latest.docType}:${latest.status}`;
    if (key === lastParseRef.current) return;
    lastParseRef.current = key;
    if (latest.status === 'parsing') {
      toast.loading('Reading your document…', { id: `doc-${latest.docType}` });
    } else if (latest.status === 'parsed') {
      toast.success('Document read', { id: `doc-${latest.docType}`, duration: 3000 });
    }
  }, [documentParseEvents]);

  const controls: AgentControlBarControls = {
    leave: true,
    microphone: true,
    chat: false,
    camera: supportsVideoInput,
    screenShare: supportsScreenShare,
  };

  const displayPreConnectMessage =
    agentState === 'connecting'
      ? 'Connecting — the first cloud start can take up to 30 seconds…'
      : preConnectMessage;

  return (
    <section
      ref={ref}
      className={cn(
        'bg-background relative z-10 flex h-full w-full flex-col overflow-hidden',
        className
      )}
      {...props}
    >
      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-2">
        <IntakeMediaPanel
          agentState={agentState}
          preConnectMessage={displayPreConnectMessage}
          showPreConnect={isPreConnectBufferEnabled && !ariaActive && messages.length === 0}
          audioVisualizerType={audioVisualizerType}
          audioVisualizerColor={audioVisualizerColor}
          audioVisualizerColorShift={audioVisualizerColorShift}
          audioVisualizerBarCount={audioVisualizerBarCount}
          audioVisualizerRadialBarCount={audioVisualizerRadialBarCount}
          audioVisualizerRadialRadius={audioVisualizerRadialRadius}
          audioVisualizerGridRowCount={audioVisualizerGridRowCount}
          audioVisualizerGridColumnCount={audioVisualizerGridColumnCount}
          audioVisualizerWaveLineWidth={audioVisualizerWaveLineWidth}
        />
        <IntakeIntelligencePanel
          agentState={agentState}
          messages={messages}
          mossEvents={mossEvents}
          documentParseEvents={documentParseEvents}
          firmRecommendations={firmRecommendations}
          showMoss={conversationStarted}
        />
      </div>

      <motion.div
        {...BOTTOM_VIEW_MOTION_PROPS}
        className="border-border shrink-0 border-t px-3 py-3 lg:px-8"
      >
        <div className="bg-background relative mx-auto w-full max-w-4xl">
          <AgentControlBar
            variant="livekit"
            controls={controls}
            isChatOpen={false}
            isConnected={session.isConnected}
            onDisconnect={session.end}
            onIsChatOpenChange={() => undefined}
          />
        </div>
      </motion.div>
    </section>
  );
}
