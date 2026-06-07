'use client';

/**
 * Shared presentational primitives for the firm "intelligence" dashboard.
 *
 * Design goal: structured, high-legibility panels a managing partner can scan
 * in seconds — large numbers, clear labels, restrained color. Reused across the
 * Moss / Unsiloed / TrueFoundry / Guardrails dashboards.
 */
import type { ReactNode } from 'react';
import type { CaseRecord } from '@/hooks/useCaseflowEvents';

export function formatUsd(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '—';
  if (value >= 1000) return `$${Math.round(value / 1000)}K`;
  return `$${Math.round(value)}`;
}

/** Best-effort estimated case value used for pipeline KPIs. */
export function estimatedValue(record: CaseRecord): number {
  // Prefer the value the agent computed from financials (medical bills + lost
  // wages × severity); fall back to a legacy field, then a score-based estimate.
  const explicit = Number(record.estimated_value ?? record.est_value ?? 0);
  if (explicit > 0) return explicit;
  const score = Number(record.score ?? record.case_strength ?? 0);
  return Math.round((score / 100) * 90000);
}

export function strengthTone(score: number): { text: string; bar: string; label: string } {
  if (score >= 70) return { text: 'text-emerald-600', bar: 'bg-emerald-500', label: 'Strong' };
  if (score >= 45) return { text: 'text-amber-600', bar: 'bg-amber-500', label: 'Moderate' };
  return { text: 'text-red-600', bar: 'bg-red-500', label: 'Developing' };
}

/** Uppercase eyebrow + title + optional description, with optional right slot. */
export function SectionHeader({
  eyebrow,
  title,
  description,
  right,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <div className="text-primary/70 font-mono text-[11px] font-semibold tracking-[0.14em] uppercase">
          {eyebrow}
        </div>
        <h2 className="mt-1 text-xl font-semibold tracking-tight">{title}</h2>
        {description ? (
          <p className="text-muted-foreground mt-1 max-w-prose text-sm">{description}</p>
        ) : null}
      </div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </div>
  );
}

/** A bordered dashboard section wrapper. */
export function DashboardSection({
  eyebrow,
  title,
  description,
  right,
  children,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  right?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="border-border bg-card rounded-2xl border p-5 sm:p-6">
      <SectionHeader eyebrow={eyebrow} title={title} description={description} right={right} />
      {children}
    </section>
  );
}

/** A single big-number KPI tile. */
export function StatTile({
  value,
  label,
  hint,
  tone = 'default',
}: {
  value: ReactNode;
  label: string;
  hint?: string;
  tone?: 'default' | 'good' | 'warn' | 'accent';
}) {
  const toneClass =
    tone === 'good'
      ? 'text-emerald-600'
      : tone === 'warn'
        ? 'text-amber-600'
        : tone === 'accent'
          ? 'text-primary'
          : 'text-foreground';
  return (
    <div className="border-border bg-background rounded-xl border p-4">
      <div className={`text-3xl leading-none font-semibold tabular-nums ${toneClass}`}>{value}</div>
      <div className="text-muted-foreground mt-2 text-xs font-medium tracking-wide uppercase">
        {label}
      </div>
      {hint ? <div className="text-muted-foreground/80 mt-1 text-xs">{hint}</div> : null}
    </div>
  );
}

/** A labeled horizontal meter (value / max). */
export function BarMeter({
  label,
  value,
  max,
  display,
  color = 'bg-primary',
}: {
  label: string;
  value: number;
  max: number;
  display?: string;
  color?: string;
}) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
        <span className="text-foreground">{label}</span>
        <span className="text-muted-foreground tabular-nums">{display ?? value}</span>
      </div>
      <div className="bg-muted h-2 overflow-hidden rounded-full">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/** A semicircular case-strength gauge with the score in the center. */
export function StrengthGauge({ score, size = 132 }: { score: number; size?: number }) {
  const clamped = Math.max(0, Math.min(100, score));
  const tone = strengthTone(clamped);
  const stroke = 12;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  // Semicircle: 180° sweep from left (180°) to right (0°).
  const arc = (frac: number) => {
    const angle = Math.PI * (1 - frac); // radians, left→right
    return { x: cx + r * Math.cos(angle), y: cy - r * Math.sin(angle) };
  };
  const start = arc(0);
  const end = arc(1);
  const value = arc(clamped / 100);
  const big = clamped / 100 > 0.5 ? 1 : 0;
  const strokeColor = clamped >= 70 ? '#10b981' : clamped >= 45 ? '#f59e0b' : '#ef4444';

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 2 + 8} viewBox={`0 0 ${size} ${size / 2 + 8}`}>
        <path
          d={`M ${start.x} ${start.y} A ${r} ${r} 0 0 1 ${end.x} ${end.y}`}
          fill="none"
          stroke="currentColor"
          className="text-muted"
          strokeWidth={stroke}
          strokeLinecap="round"
        />
        <path
          d={`M ${start.x} ${start.y} A ${r} ${r} 0 ${big} 1 ${value.x} ${value.y}`}
          fill="none"
          stroke={strokeColor}
          strokeWidth={stroke}
          strokeLinecap="round"
        />
      </svg>
      <div className="-mt-8 flex flex-col items-center">
        <div className={`text-4xl font-bold tabular-nums ${tone.text}`}>{Math.round(clamped)}</div>
        <div className="text-muted-foreground text-xs">/ 100 · {tone.label}</div>
      </div>
    </div>
  );
}

/** A small status chip (used by Guardrails tiles). */
export function StatusChip({
  state,
  children,
}: {
  state: 'pass' | 'warn' | 'fail' | 'idle';
  children: ReactNode;
}) {
  const cls =
    state === 'pass'
      ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'
      : state === 'warn'
        ? 'bg-amber-500/15 text-amber-700 dark:text-amber-400'
        : state === 'fail'
          ? 'bg-red-500/15 text-red-700 dark:text-red-400'
          : 'bg-muted text-muted-foreground';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${cls}`}
    >
      {children}
    </span>
  );
}
