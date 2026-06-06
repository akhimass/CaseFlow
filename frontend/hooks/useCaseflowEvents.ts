import { useEffect, useState } from 'react';

export type CaseRecord = Record<string, unknown> & { case_id?: string };

export function useCaseflowEvents() {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const source = new EventSource('/api/cases/events');

    source.onopen = () => setConnected(true);
    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'snapshot') {
          setCases(data.cases ?? []);
        }
        if (data.type === 'update') {
          const { case_id, payload } = data;
          setCases((prev) => {
            const idx = prev.findIndex((c) => c.case_id === case_id);
            const next = [...prev];
            const merged = { case_id, ...payload };
            if (idx >= 0) next[idx] = { ...next[idx], ...merged };
            else next.unshift(merged);
            return next;
          });
        }
      } catch {
        // ignore malformed events
      }
    };

    source.onerror = () => setConnected(false);

    return () => source.close();
  }, []);

  return { cases, connected };
}
