'use client';

import { Track } from 'livekit-client';
import { AnimatePresence, motion } from 'motion/react';
import {
  type AgentState,
  VideoTrack,
  useTracks,
  useVoiceAssistant,
} from '@livekit/components-react';
import { Shimmer } from '@/components/ai-elements/shimmer';
import { cn } from '@/lib/shadcn/utils';
import { AudioVisualizer } from './audio-visualizer';
import { useLocalTrackRef } from './tile-view';

const AGENT_STATE_LABEL: Record<string, string> = {
  connecting: 'Connecting…',
  initializing: 'Starting Aria…',
  listening: 'Aria is listening',
  thinking: 'Aria is thinking',
  speaking: 'Aria is speaking',
  disconnected: 'Disconnected',
};

interface IntakeMediaPanelProps {
  agentState: AgentState;
  preConnectMessage?: string;
  showPreConnect?: boolean;
  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerBarCount?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerWaveLineWidth?: number;
}

export function IntakeMediaPanel({
  agentState,
  preConnectMessage = 'Waiting for Aria to join…',
  showPreConnect = false,
  audioVisualizerType,
  audioVisualizerColor,
  audioVisualizerColorShift,
  audioVisualizerBarCount,
  audioVisualizerGridRowCount,
  audioVisualizerGridColumnCount,
  audioVisualizerRadialBarCount,
  audioVisualizerRadialRadius,
  audioVisualizerWaveLineWidth,
}: IntakeMediaPanelProps) {
  const { videoTrack: agentVideoTrack } = useVoiceAssistant();
  const [screenShareTrack] = useTracks([Track.Source.ScreenShare]);
  const cameraTrack = useLocalTrackRef(Track.Source.Camera);

  const isCameraEnabled = cameraTrack && !cameraTrack.publication.isMuted;
  const isScreenShareEnabled = screenShareTrack && !screenShareTrack.publication.isMuted;
  const secondaryTrack = isScreenShareEnabled
    ? screenShareTrack
    : isCameraEnabled
      ? cameraTrack
      : undefined;
  const isAvatar = agentVideoTrack !== undefined;
  const statusLabel = AGENT_STATE_LABEL[agentState] ?? 'Aria';

  return (
    <div className="border-border flex h-full min-h-0 flex-col border-b lg:border-r lg:border-b-0">
      <div className="flex min-h-0 flex-1 flex-col gap-4 p-4 pt-6 lg:p-6">
        <div className="bg-muted/40 relative min-h-[180px] flex-1 overflow-hidden rounded-2xl border">
          <AnimatePresence mode="wait">
            {secondaryTrack ? (
              <motion.div
                key="camera"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0"
              >
                <VideoTrack
                  trackRef={secondaryTrack}
                  width={secondaryTrack.publication.dimensions?.width ?? 0}
                  height={secondaryTrack.publication.dimensions?.height ?? 0}
                  className="h-full w-full object-cover"
                />
              </motion.div>
            ) : (
              <motion.div
                key="camera-placeholder"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-muted-foreground absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center text-sm"
              >
                <span className="font-medium">Your camera</span>
                <span className="text-xs">Turn on video to show documents to Aria</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="flex flex-col items-center gap-3 py-2">
          {isAvatar ? (
            <div className="bg-muted aspect-square w-full max-w-[220px] overflow-hidden rounded-3xl border">
              <VideoTrack
                trackRef={agentVideoTrack}
                width={agentVideoTrack.publication.dimensions?.width ?? 0}
                height={agentVideoTrack.publication.dimensions?.height ?? 0}
                className="h-full w-full object-cover"
              />
            </div>
          ) : (
            <div className="relative flex h-[120px] w-full max-w-[280px] items-center justify-center">
              <AudioVisualizer
                isChatOpen={false}
                audioVisualizerType={audioVisualizerType}
                audioVisualizerColor={audioVisualizerColor}
                audioVisualizerColorShift={audioVisualizerColorShift}
                audioVisualizerBarCount={audioVisualizerBarCount}
                audioVisualizerRadialBarCount={audioVisualizerRadialBarCount}
                audioVisualizerRadialRadius={audioVisualizerRadialRadius}
                audioVisualizerGridRowCount={audioVisualizerGridRowCount}
                audioVisualizerGridColumnCount={audioVisualizerGridColumnCount}
                audioVisualizerWaveLineWidth={audioVisualizerWaveLineWidth}
                className={cn(
                  'bg-background rounded-[50px] border border-transparent',
                  'absolute top-1/2 left-1/2 size-[120px] -translate-x-1/2 -translate-y-1/2'
                )}
                style={{ color: audioVisualizerColor }}
              />
            </div>
          )}

          {showPreConnect ? (
            <Shimmer className="text-center text-sm font-semibold">{preConnectMessage}</Shimmer>
          ) : (
            <p className="text-foreground text-center text-sm font-medium">{statusLabel}</p>
          )}
        </div>
      </div>

      <div className="text-muted-foreground hidden flex-wrap items-center justify-center gap-2 px-4 pb-4 text-[10px] font-medium lg:flex">
        <span>LiveKit video</span>
        <span>·</span>
        <span>Deepgram nova-3 STT</span>
        <span>·</span>
        <span>MiniMax Speech 2.8 HD</span>
      </div>
    </div>
  );
}
