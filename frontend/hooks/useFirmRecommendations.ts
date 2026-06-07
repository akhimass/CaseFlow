import { useEffect, useState } from 'react';
import { RoomEvent } from 'livekit-client';
import { useRoomContext } from '@livekit/components-react';

const textDecoder = new TextDecoder();

export type FirmRecommendation = {
  firm_id?: string;
  name?: string;
  phone?: string;
  languages?: string[];
  specialties?: string[];
  score?: number;
  match_reasons?: string[];
  rating?: string;
  years_experience?: string;
  response_time_hours?: string;
  comparable_range?: string;
  track_settlement_low?: number;
  track_settlement_high?: number;
};

/**
 * Subscribes to the agent's `firm_recommendations` data message and returns the
 * Moss-backed matched firms (top first) for the caller to review and choose.
 */
export function useFirmRecommendations(): FirmRecommendation[] {
  const room = useRoomContext();
  const [firms, setFirms] = useState<FirmRecommendation[]>([]);

  useEffect(() => {
    if (!room) return;

    const handleData = (payload: Uint8Array) => {
      try {
        const message = JSON.parse(textDecoder.decode(payload)) as {
          type?: string;
          data?: { firms?: FirmRecommendation[] };
        };
        if (message.type !== 'firm_recommendations') return;
        const list = message.data?.firms;
        if (Array.isArray(list) && list.length > 0) {
          setFirms(list);
        }
      } catch {
        // ignore malformed packets
      }
    };

    room.on(RoomEvent.DataReceived, handleData);
    return () => {
      room.off(RoomEvent.DataReceived, handleData);
    };
  }, [room]);

  return firms;
}
