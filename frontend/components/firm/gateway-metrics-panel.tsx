'use client';

import { useEffect, useState } from 'react';

type AuditRecord = {
  event_type?: string;
  model_id?: string;
  provider?: string;
  latency_ms?: number;
  input_chars?: number;
  output_chars?: number;
  failover?: boolean;
  timestamp?: number;
};

type Metrics = {
  totalCalls: number;
  totalFailovers: number;
  totalTtsAudits?: number;
  totalCostUsd: number;
  qualityChecks: number;
  latencyByModel: Record<string, { count: number; avgLatencyMs: number }>;
  recent?: AuditRecord[];
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
        <>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="Gateway calls" value={metrics?.totalCalls ?? 0} />
            <MetricCard label="Failovers" value={metrics?.totalFailovers ?? 0} />
            <MetricCard label="MiniMax TTS audits" value={metrics?.totalTtsAudits ?? 0} />
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
          {metrics?.recent && metrics.recent.length > 0 && (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-muted-foreground border-border border-b">
                    <th className="py-1 pr-3 font-medium">Event</th>
                    <th className="py-1 pr-3 font-medium">Model</th>
                    <th className="py-1 pr-3 font-medium">Latency</th>
                    <th className="py-1 font-medium">Chars</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.recent
                    .slice(-8)
                    .reverse()
                    .map((row, i) => (
                      <tr key={`${row.timestamp}-${i}`} className="border-border/50 border-b">
                        <td className="py-1.5 pr-3 font-mono">{row.event_type}</td>
                        <td className="py-1.5 pr-3">{row.model_id ?? row.provider}</td>
                        <td className="py-1.5 pr-3 tabular-nums">{row.latency_ms ?? '—'} ms</td>
                        <td className="py-1.5 tabular-nums">
                          {row.input_chars ?? 0}→{row.output_chars ?? row.input_chars ?? 0}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </>
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
