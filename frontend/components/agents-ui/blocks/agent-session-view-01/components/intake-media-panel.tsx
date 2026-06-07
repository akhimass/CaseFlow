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
  initializing: 'Connecting…',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
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
  preConnectMessage = 'Connecting you to the Caseflow specialist…',
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
  const statusLabel = AGENT_STATE_LABEL[agentState] ?? 'Caseflow';

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
                <span className="text-xs">Turn on video to show your documents</span>
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
            <div className="relative flex h-[220px] w-full items-center justify-center">
              {/* Outermost ambient ring — always visible */}
              <div
                className="absolute size-[210px] rounded-full"
                style={{
                  background: `radial-gradient(circle, ${audioVisualizerColor ?? '#2563EB'}18 0%, transparent 70%)`,
                }}
              />
              {/* Pulse ring — faster when speaking */}
              <div
                className={cn(
                  'absolute rounded-full border transition-all duration-700',
                  agentState === 'speaking'
                    ? 'size-[200px] animate-ping opacity-60'
                    : agentState === 'thinking'
                      ? 'size-[188px] animate-pulse opacity-40'
                      : 'size-[180px] opacity-20'
                )}
                style={{ borderColor: `${audioVisualizerColor ?? '#2563EB'}60` }}
              />
              {/* Inner glow ring */}
              <div
                className={cn(
                  'absolute rounded-full border-2 transition-all duration-500',
                  agentState === 'speaking' ? 'size-[162px] opacity-70' : 'size-[154px] opacity-30'
                )}
                style={{ borderColor: `${audioVisualizerColor ?? '#2563EB'}90` }}
              />
              {/* Aura canvas */}
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
                className="size-[148px] rounded-full"
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
