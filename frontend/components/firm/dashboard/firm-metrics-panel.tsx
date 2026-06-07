'use client';

import { useEffect, useState } from 'react';

type MetricsPayload = {
  metrics?: {
    totalCalls: number;
    totalModelCalls?: number;
    totalFailovers: number;
    totalCostUsd: number;
    qualityChecks: number;
    latencyByModel: Record<string, { count: number; avgLatencyMs: number }>;
    byProvider?: Record<string, number>;
    failovers: Array<Record<string, unknown>>;
    recent: Array<Record<string, unknown>>;
  };
};

function MetricCard({ title, value }: { title: string; value: string | number }) {
  return (
    <div className="border-border bg-background rounded-xl border p-4">
      <div className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
        {title}
      </div>
      <div className="mt-1 text-3xl font-bold tabular-nums">{value}</div>
    </div>
  );
}

export function FirmMetricsPanel() {
  const [data, setData] = useState<MetricsPayload | null>(null);

  useEffect(() => {
    const load = () =>
      fetch('/api/audit')
        .then((r) => r.json())
        .then(setData)
        .catch(() => setData(null));
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, []);

  const m = data?.metrics;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Gateway metrics</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          TrueFoundry gateway calls, model fleet usage, and audit events for this deployment.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard title="Gateway calls" value={m?.totalCalls ?? 0} />
        <MetricCard title="Model calls" value={m?.totalModelCalls ?? m?.totalCalls ?? 0} />
        <MetricCard title="Failovers" value={m?.totalFailovers ?? 0} />
        <MetricCard title="Quality checks" value={m?.qualityChecks ?? 0} />
      </div>

      <section className="border-border bg-background rounded-xl border p-4">
        <h2 className="mb-3 text-sm font-semibold">Model fleet by provider</h2>
        {m?.byProvider && Object.keys(m.byProvider).length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {Object.entries(m.byProvider).map(([provider, count]) => (
              <span
                key={provider}
                className="border-border rounded-full border px-3 py-1 text-sm tabular-nums"
              >
                <span className="font-medium">{provider}</span>{' '}
                <span className="text-muted-foreground">· {count}</span>
              </span>
            ))}
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">No model calls recorded yet.</p>
        )}
      </section>

      <section className="border-border bg-background rounded-xl border p-4">
        <h2 className="mb-3 text-sm font-semibold">Latency by model</h2>
        <pre className="text-muted-foreground overflow-x-auto text-xs">
          {JSON.stringify(m?.latencyByModel ?? {}, null, 2)}
        </pre>
      </section>

      <section className="border-border bg-background rounded-xl border p-4">
        <h2 className="mb-3 text-sm font-semibold">Recent audit events</h2>
        <pre className="text-muted-foreground max-h-96 overflow-auto text-xs">
          {JSON.stringify(m?.recent ?? [], null, 2)}
        </pre>
      </section>
    </div>
  );
}
