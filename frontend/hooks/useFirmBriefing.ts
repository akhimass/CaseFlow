import { useCallback, useEffect, useState } from 'react';
import { RoomEvent } from 'livekit-client';
import { useLocalParticipant, useRoomContext } from '@livekit/components-react';

const textDecoder = new TextDecoder();
const textEncoder = new TextEncoder();

export type BriefingStatus = 'idle' | 'speaking' | 'complete';

export type BriefingState = {
  status: BriefingStatus;
  activeSection: string | null;
  activeTitle: string | null;
  caption: string | null;
  index: number;
  total: number;
  /** Sections the agent has focused so far, in order. */
  visited: string[];
};

const INITIAL: BriefingState = {
  status: 'idle',
  activeSection: null,
  activeTitle: null,
  caption: null,
  index: 0,
  total: 0,
  visited: [],
};

/**
 * Subscribes to the firm-briefing agent's `caseflow_update` data messages and
 * exposes the live narration state (which section is being spoken, the caption,
 * progress). Also returns a `replay` action that asks the agent to re-narrate.
 *
 * Must be used within a RoomContext (AgentSessionProvider / SessionProvider).
 */
export function useFirmBriefing(caseId: string) {
  const room = useRoomContext();
  const { localParticipant } = useLocalParticipant();
  const [state, setState] = useState<BriefingState>(INITIAL);

  useEffect(() => {
    if (!room) return;

    const handleData = (payload: Uint8Array) => {
      let message: unknown;
      try {
        message = JSON.parse(textDecoder.decode(payload));
      } catch {
        return;
      }
      if (!message || typeof message !== 'object') return;
      const envelope = message as { type?: string; data?: Record<string, unknown> };
      if (envelope.type !== 'caseflow_update' || !envelope.data) return;

      const {
        case_id,
        event,
        payload: p,
      } = envelope.data as {
        case_id?: string;
        event?: string;
        payload?: Record<string, unknown>;
      };
      if (case_id && caseId && case_id !== caseId) return;
      if (!event || !p) return;

      if (event === 'briefing_started') {
        const briefing = (p.briefing ?? {}) as { total?: number };
        setState({
          ...INITIAL,
          status: 'speaking',
          total: Number(briefing.total ?? 0),
        });
      } else if (event === 'briefing_focus') {
        const focus = (p.briefing_focus ?? {}) as {
          section?: string;
          title?: string;
          caption?: string;
          index?: number;
          total?: number;
        };
        setState((prev) => ({
          status: 'speaking',
          activeSection: focus.section ?? null,
          activeTitle: focus.title ?? null,
          caption: focus.caption ?? null,
          index: Number(focus.index ?? prev.index),
          total: Number(focus.total ?? prev.total),
          visited: focus.section
            ? prev.visited.includes(focus.section)
              ? prev.visited
              : [...prev.visited, focus.section]
            : prev.visited,
        }));
      } else if (event === 'briefing_complete') {
        setState((prev) => ({ ...prev, status: 'complete', activeSection: null }));
      }
    };

    room.on(RoomEvent.DataReceived, handleData);
    return () => {
      room.off(RoomEvent.DataReceived, handleData);
    };
  }, [room, caseId]);

  const replay = useCallback(async () => {
    if (!localParticipant) return;
    setState({ ...INITIAL, status: 'speaking' });
    const message = textEncoder.encode(
      JSON.stringify({ type: 'briefing_control', data: { action: 'replay' } })
    );
    try {
      await localParticipant.publishData(message, { reliable: true });
    } catch {
      // best-effort
    }
  }, [localParticipant]);

  return { briefing: state, replay };
}
