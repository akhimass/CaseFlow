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

  seed(records: AuditRecord[]) {
    for (const r of records) this.records.push({ ...r, timestamp: r.timestamp ?? Date.now() });
  }
}

// Seed a realistic gateway-metrics baseline so the Metrics tab is populated for
// the demo (live agent calls append over this). Mirrors the model fleet:
// TrueFoundry-routed dialogue, MiniMax voice/dialogue, Bedrock second-opinion,
// AWS Comprehend Medical, plus a couple of failovers and quality checks.
function demoAuditRecords(): AuditRecord[] {
  const now = Date.now();
  const out: AuditRecord[] = [];
  const dialogue = [
    { provider: 'truefoundry', model: 'gpt-4.1-mini', lat: [620, 740, 580, 910, 690] },
    { provider: 'minimax', model: 'MiniMax-Text-01', lat: [820, 760, 880, 700] },
    { provider: 'openai-direct', model: 'gpt-4.1-mini', lat: [510, 470, 560] },
  ];
  let i = 0;
  for (const d of dialogue) {
    for (const lat of d.lat) {
      out.push({
        event_type: 'gateway_call',
        provider: d.provider,
        model_id: d.model,
        latency_ms: lat,
        failover: false,
        timestamp: now - (i + 1) * 9000,
      });
      i++;
    }
  }
  // Two failovers (primary slow → next provider).
  out.push({
    event_type: 'gateway_call',
    provider: 'bedrock',
    model_id: 'us.amazon.nova-lite-v1:0',
    latency_ms: 1480,
    failover: true,
    failover_reason: 'primary timeout',
    timestamp: now - 30000,
  });
  out.push({
    event_type: 'gateway_call',
    provider: 'openai-direct',
    model_id: 'gpt-4.1-mini',
    latency_ms: 1120,
    failover: true,
    failover_reason: 'gateway 5xx',
    timestamp: now - 47000,
  });
  // Bedrock second-opinion on the discrepancy.
  for (let k = 0; k < 3; k++)
    out.push({
      event_type: 'second_opinion',
      provider: 'bedrock',
      model_id: 'anthropic.claude-3-5-sonnet',
      latency_ms: 1400 + k * 120,
      timestamp: now - 22000 - k * 8000,
    });
  // Comprehend Medical ICD-10 coding.
  for (let k = 0; k < 4; k++)
    out.push({
      event_type: 'comprehend_medical',
      provider: 'aws-comprehend-medical',
      model_id: 'comprehend-medical-icd10',
      latency_ms: 300 + k * 40,
      timestamp: now - 18000 - k * 7000,
    });
  // MiniMax TTS pass-throughs.
  for (let k = 0; k < 6; k++)
    out.push({
      event_type: 'tts_pass_through',
      provider: 'minimax',
      model_id: 'minimax-speech-2.8-hd',
      latency_ms: 0,
      timestamp: now - 5000 - k * 4000,
    });
  // Async validator quality checks.
  for (let k = 0; k < 5; k++)
    out.push({
      event_type: 'validator_score',
      provider: 'truefoundry',
      model_id: 'gpt-4.1-mini',
      timestamp: now - 12000 - k * 11000,
    });
  return out;
}

export function getAuditStore() {
  if (!globalThis.__caseflowAuditStore) {
    const store = new AuditStore();
    if (process.env.CASEFLOW_DISABLE_DEMO_CASES !== '1') {
      store.seed(demoAuditRecords());
    }
    globalThis.__caseflowAuditStore = store;
  }
  return globalThis.__caseflowAuditStore;
}
