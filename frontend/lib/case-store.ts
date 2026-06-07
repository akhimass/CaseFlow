export type CaseUpdate = {
  case_id: string;
  event: string;
  payload: Record<string, unknown>;
  timestamp: number;
};

type Listener = (update: CaseUpdate) => void;

declare global {
  // eslint-disable-next-line no-var
  var __caseflowStore: CaseflowStore | undefined;
}

class CaseflowStore {
  private cases = new Map<string, Record<string, unknown>>();
  private listeners = new Set<Listener>();

  upsert(update: CaseUpdate) {
    const existing = this.cases.get(update.case_id) ?? { case_id: update.case_id };
    const merged = { ...existing, ...update.payload, last_event: update.event };
    this.cases.set(update.case_id, merged);
    this.listeners.forEach((listener) => listener(update));
  }

  list() {
    return Array.from(this.cases.values()).sort(
      (a, b) => Number(b.updated_at ?? b.timestamp ?? 0) - Number(a.updated_at ?? a.timestamp ?? 0)
    );
  }

  get(caseId: string) {
    return this.cases.get(caseId);
  }

  remove(caseId: string) {
    this.cases.delete(caseId);
  }

  subscribe(listener: Listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}

export function getCaseStore() {
  if (!globalThis.__caseflowStore) {
    globalThis.__caseflowStore = new CaseflowStore();
  }
  return globalThis.__caseflowStore;
}
