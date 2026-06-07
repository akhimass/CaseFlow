'use client';

import { useEffect, useState } from 'react';

type Metrics = {
  totalCalls: number;
  totalFailovers: number;
  totalCostUsd: number;
  qualityChecks: number;
  latencyByModel: Record<string, { count: number; avgLatencyMs: number }>;
};

export function GatewayMetricsPanel({ collapsed = true }: { collapsed?: boolean }) {
  const [open, setOpen] = useState(!collapsed);
  const [metrics, setMetrics] = useState<Metrics | null>(null);

  useEffect(() => {
    const load = () => {
      fetch('/api/audit')
        .then((r) => r.json())
        .then((data) => setMetrics(data.metrics ?? null))
        .catch(() => setMetrics(null));
    };
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="border-border rounded-lg border p-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-left"
      >
        <h3 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
          TrueFoundry metrics
        </h3>
        <span className="text-muted-foreground text-xs">{open ? 'Hide' : 'Show'}</span>
      </button>
      {open && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Gateway calls" value={metrics?.totalCalls ?? 0} />
          <MetricCard label="Failovers" value={metrics?.totalFailovers ?? 0} />
          <MetricCard label="Est. cost (USD)" value={(metrics?.totalCostUsd ?? 0).toFixed(4)} />
          <MetricCard label="Quality checks" value={metrics?.qualityChecks ?? 0} />
          {metrics?.latencyByModel &&
            Object.entries(metrics.latencyByModel).map(([model, stats]) => (
              <MetricCard
                key={model}
                label={`${model} avg ms`}
                value={stats.avgLatencyMs}
                className="sm:col-span-2"
              />
            ))}
        </div>
      )}
    </section>
  );
}

function MetricCard({
  label,
  value,
  className = '',
}: {
  label: string;
  value: string | number;
  className?: string;
}) {
  return (
    <div className={`border-border rounded border p-3 ${className}`}>
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}
