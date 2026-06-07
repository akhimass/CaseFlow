'use client';

import { useEffect, useState } from 'react';
import { RoomEvent } from 'livekit-client';
import { useRoomContext } from '@livekit/components-react';

export type DocumentParseEvent = {
  id: string;
  docType: string;
  status: 'parsing' | 'parsed';
  fields: Record<string, unknown>;
  timestamp?: number;
};

const textDecoder = new TextDecoder();

export function useDocumentParseEvents() {
  const room = useRoomContext();
  const [events, setEvents] = useState<DocumentParseEvent[]>([]);

  useEffect(() => {
    if (!room) return;

    const onData = (payload: Uint8Array) => {
      try {
        const msg = JSON.parse(textDecoder.decode(payload)) as {
          type?: string;
          data?: {
            doc_type?: string;
            status?: string;
            fields?: Record<string, unknown>;
            timestamp?: number;
          };
        };
        if (msg.type !== 'document_parse' || !msg.data?.doc_type) return;

        const status = msg.data.status === 'parsed' ? 'parsed' : 'parsing';
        const entry: DocumentParseEvent = {
          id: `${msg.data.doc_type}-${msg.data.timestamp ?? Date.now()}`,
          docType: msg.data.doc_type,
          status,
          fields: msg.data.fields ?? {},
          timestamp: msg.data.timestamp,
        };

        setEvents((prev) => {
          const without = prev.filter((e) => e.docType !== entry.docType);
          return [entry, ...without].slice(0, 4);
        });
      } catch {
        // ignore malformed packets
      }
    };

    room.on(RoomEvent.DataReceived, onData);
    return () => {
      room.off(RoomEvent.DataReceived, onData);
    };
  }, [room]);

  return events;
}
