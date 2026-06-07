import { DEMO_CASES } from './demo-cases';

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

  /**
   * Seed pre-built demo cases directly into the map (no listener fan-out).
   * Live agent updates merge over these by `case_id` via {@link upsert}, so a
   * real intake always wins; demo cases just guarantee every firm has leads.
   */
  seed(records: Array<Record<string, unknown>>) {
    for (const record of records) {
      const id = String(record.case_id ?? '');
      if (!id || this.cases.has(id)) continue;
      this.cases.set(id, { ...record });
    }
  }
}

export function getCaseStore() {
  if (!globalThis.__caseflowStore) {
    const store = new CaseflowStore();
    if (process.env.CASEFLOW_DISABLE_DEMO_CASES !== '1') {
      store.seed(DEMO_CASES);
    }
    globalThis.__caseflowStore = store;
  }
  return globalThis.__caseflowStore;
}
