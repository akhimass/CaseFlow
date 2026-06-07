'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

type MetricsPayload = {
  metrics?: {
    totalCalls: number;
    totalFailovers: number;
    totalCostUsd: number;
    qualityChecks: number;
    latencyByModel: Record<string, { count: number; avgLatencyMs: number }>;
    failovers: Array<Record<string, unknown>>;
    recent: Array<Record<string, unknown>>;
  };
};

export default function AdminMetricsPage() {
  const [data, setData] = useState<MetricsPayload | null>(null);
  const isDev = process.env.NODE_ENV !== 'production';

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

  if (!isDev) {
    return (
      <main className="p-8">
        <p>Admin metrics are dev-only.</p>
      </main>
    );
  }

  return (
    <main className="bg-background min-h-svh p-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">TrueFoundry gateway metrics</h1>
            <p className="text-muted-foreground text-sm">Dev-only · current session</p>
          </div>
          <Link href="/firm/login" className="text-primary text-sm underline">
            Firm dashboard
          </Link>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card title="Total calls" value={m?.totalCalls ?? 0} />
          <Card title="Failovers" value={m?.totalFailovers ?? 0} />
          <Card title="Cost (USD)" value={(m?.totalCostUsd ?? 0).toFixed(4)} />
          <Card title="Quality checks" value={m?.qualityChecks ?? 0} />
        </div>

        <section className="border-border rounded-lg border p-4">
          <h2 className="mb-3 font-medium">Latency by model</h2>
          <pre className="text-muted-foreground overflow-x-auto text-xs">
            {JSON.stringify(m?.latencyByModel ?? {}, null, 2)}
          </pre>
        </section>

        <section className="border-border rounded-lg border p-4">
          <h2 className="mb-3 font-medium">Recent audit events</h2>
          <pre className="text-muted-foreground max-h-96 overflow-auto text-xs">
            {JSON.stringify(m?.recent ?? [], null, 2)}
          </pre>
        </section>
      </div>
    </main>
  );
}

function Card({ title, value }: { title: string; value: string | number }) {
  return (
    <div className="border-border rounded-lg border p-4">
      <div className="text-muted-foreground text-xs uppercase">{title}</div>
      <div className="text-3xl font-bold tabular-nums">{value}</div>
    </div>
  );
}
