export type AuditRecord = {
  audit_id?: string;
  event_type: string;
  actor?: string;
  model_id?: string;
  resolved_model?: string;
  provider?: string;
  case_id?: string;
  turn?: number;
  caller_id?: string;
  input_chars?: number;
  output_chars?: number;
  latency_ms?: number;
  cost_usd?: number;
  failover?: boolean;
  failover_reason?: string | null;
  payload?: Record<string, unknown>;
  timestamp?: number;
};

type Listener = (record: AuditRecord) => void;

declare global {
  // eslint-disable-next-line no-var
  var __caseflowAuditStore: AuditStore | undefined;
}

class AuditStore {
  private records: AuditRecord[] = [];
  private listeners = new Set<Listener>();

  append(record: AuditRecord) {
    this.records.push({ ...record, timestamp: record.timestamp ?? Date.now() });
    if (this.records.length > 1000) {
      this.records = this.records.slice(-1000);
    }
    this.listeners.forEach((l) => l(record));
  }

  list(limit = 200) {
    return this.records.slice(-limit);
  }

  metrics() {
    const calls = this.records.filter(
      (r) => r.event_type === 'gateway_call' || r.event_type === 'tts_pass_through'
    );
    const failovers = calls.filter((r) => r.failover);

    // The full model fleet — every model-touching call, gateway-routed or not —
    // so the dashboard reflects that all model calls are audited (not just the
    // TrueFoundry-routed ones).
    const MODEL_EVENTS = new Set([
      'gateway_call',
      'tts_pass_through',
      'second_opinion',
      'comprehend_medical',
    ]);
    const modelCalls = this.records.filter((r) => MODEL_EVENTS.has(r.event_type));
    const providerCounts = new Map<string, number>();
    for (const call of modelCalls) {
      const key = call.provider ?? 'unknown';
      providerCounts.set(key, (providerCounts.get(key) ?? 0) + 1);
    }
    const byProvider = Object.fromEntries(
      [...providerCounts.entries()].sort((a, b) => b[1] - a[1])
    );
    const ttsCalls = this.records.filter((r) => r.event_type === 'tts_pass_through');
    const byModel = new Map<string, { count: number; latencySum: number }>();

    for (const call of calls) {
      const key = call.model_id ?? 'unknown';
      const entry = byModel.get(key) ?? { count: 0, latencySum: 0 };
      entry.count += 1;
      entry.latencySum += call.latency_ms ?? 0;
      byModel.set(key, entry);
    }

    const latencyByModel = Object.fromEntries(
      [...byModel.entries()].map(([model, v]) => [
        model,
        { count: v.count, avgLatencyMs: v.count ? Math.round(v.latencySum / v.count) : 0 },
      ])
    );

    const validatorScores = this.records.filter((r) => r.event_type === 'validator_score');

    return {
      totalCalls: calls.length,
      totalModelCalls: modelCalls.length,
      totalFailovers: failovers.length,
      totalTtsAudits: ttsCalls.length,
      totalCostUsd: calls.reduce((sum, r) => sum + (r.cost_usd ?? 0), 0),
      latencyByModel,
      byProvider,
      qualityChecks: validatorScores.length,
      failovers: failovers.slice(-20),
      recent: this.list(50),
    };
  }

  subscribe(listener: Listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }
}

export function getAuditStore() {
  if (!globalThis.__caseflowAuditStore) {
    globalThis.__caseflowAuditStore = new AuditStore();
  }
  return globalThis.__caseflowAuditStore;
}
