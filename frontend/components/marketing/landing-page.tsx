import Link from 'next/link';
import { FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FEATURES, MOCK_ROWS, STATS } from '@/lib/marketing';

const TABLE_COLS =
  'grid-cols-[minmax(7rem,1.15fr)_minmax(5rem,0.85fr)_minmax(5.5rem,0.9fr)_2.5rem_minmax(3.5rem,0.65fr)_minmax(5.5rem,0.85fr)]';

export function LandingPage() {
  return (
    <div className="min-h-svh bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
          <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/caseflow-mark.svg" alt="" className="size-8 rounded-md" />
            Caseflow
          </Link>
          <nav className="hidden items-center gap-6 text-sm text-muted-foreground md:flex">
            <Link href="/intake" className="hover:text-foreground">
              Start intake
            </Link>
            <Link href="/dashboard" className="hover:text-foreground">
              Firm dashboard
            </Link>
          </nav>
          <Button asChild>
            <Link href="/intake">Start intake</Link>
          </Button>
        </div>
      </header>

      <section className="mx-auto max-w-7xl px-6 pb-6 pt-10">
        <div className="grid items-center gap-8 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] lg:gap-10">
          <div className="text-center lg:text-left">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-3 py-1 text-sm text-muted-foreground">
              <span className="size-2 rounded-full bg-emerald-500" />
              Spanish + English · Live video intake
            </div>
            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl lg:text-6xl">
              Caseflow
            </h1>
            <p className="mt-4 text-lg text-muted-foreground md:text-xl">
              Multilingual video intake for personal injury cases. Aria qualifies callers,
              parses documents live, retrieves comparables, and matches firms — in under 90
              seconds.
            </p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3 lg:justify-start">
              <Button asChild size="lg">
                <Link href="/intake">Start intake</Link>
              </Button>
              <Button asChild variant="outline" size="lg">
                <Link href="/dashboard">Firm dashboard</Link>
              </Button>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-border bg-card shadow-lg">
            <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-4 py-3">
              <span className="size-3 rounded-full bg-[#ff5f57]" />
              <span className="size-3 rounded-full bg-[#febc2e]" />
              <span className="size-3 rounded-full bg-[#28c840]" />
            </div>
            <div className="p-4">
              <div className="mb-3 grid gap-2 sm:grid-cols-3">
                {[
                  { label: 'Cases today', value: '12' },
                  { label: 'Qualified', value: '8', accent: true },
                  { label: 'Live intakes', value: '3' },
                ].map(({ label, value, accent }) => (
                  <div key={label} className="rounded-lg border border-border p-3">
                    <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                      {label}
                    </div>
                    <div
                      className={`mt-1 text-2xl font-bold tracking-tight ${accent ? 'text-primary' : ''}`}
                    >
                      {value}
                    </div>
                  </div>
                ))}
              </div>
              <div className="overflow-x-auto rounded-lg border border-border">
                <div className="min-w-[36rem]">
                  <div
                    className={`grid ${TABLE_COLS} gap-2 border-b border-border bg-muted/40 px-3 py-2 text-[9px] font-semibold uppercase tracking-wide text-muted-foreground sm:text-[10px]`}
                  >
                    <span>Caller</span>
                    <span>Case type</span>
                    <span>Disposition</span>
                    <span>Score</span>
                    <span>Comparable</span>
                    <span>Summary</span>
                  </div>
                  {MOCK_ROWS.map((row) => (
                    <div
                      key={row.caller}
                      className={`grid ${TABLE_COLS} gap-2 border-b border-border px-3 py-2 text-xs last:border-b-0 sm:text-sm`}
                    >
                      <span className="truncate">{row.caller}</span>
                      <span className="truncate text-muted-foreground">{row.type}</span>
                      <span>
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium sm:text-xs ${
                            row.ok ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {row.disposition}
                        </span>
                      </span>
                      <span>{row.score}</span>
                      <span className="font-medium tabular-nums">{row.caseValue}</span>
                      <span>
                        {row.summary === '—' ? (
                          <span className="text-muted-foreground">—</span>
                        ) : (
                          <span className="inline-flex max-w-full items-center gap-1 truncate text-primary">
                            <FileText className="size-3 shrink-0" />
                            <span className="truncate underline decoration-primary/40 underline-offset-2">
                              {row.summary}
                            </span>
                          </span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-y border-border bg-muted/20">
        <div className="mx-auto grid max-w-6xl gap-6 px-6 py-8 sm:grid-cols-2 lg:grid-cols-4">
          {STATS.map(({ value, label }) => (
            <div key={label}>
              <div className="text-3xl font-bold tracking-tight md:text-4xl">{value}</div>
              <p className="mt-2 text-sm text-muted-foreground">{label}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-12">
        <p className="text-sm font-semibold uppercase tracking-widest text-primary">Features</p>
        <h2 className="mt-3 text-3xl font-semibold tracking-tight md:text-4xl">
          Built for PI video intake.
        </h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ title, body }) => (
            <div key={title} className="rounded-xl border border-border bg-card p-6">
              <h3 className="text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-border bg-muted/20 px-6 py-10">
        <blockquote className="mx-auto max-w-3xl text-center">
          <p className="text-xl font-medium leading-relaxed md:text-2xl">
            &ldquo;Caseflow caught the fault discrepancy live — in Spanish — and matched Maria to
            the right OC firm before she hung up.&rdquo;
          </p>
          <footer className="mt-6 text-sm text-muted-foreground">
            <strong className="text-foreground">Demo flow</strong> · YC Conversational AI Hackathon
          </footer>
        </blockquote>
      </section>

      <footer className="border-t border-border px-6 py-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground">
            © 2026 Caseflow · Built at YC Conversational AI Hackathon
          </p>
          <p className="text-sm text-muted-foreground">
            LiveKit · Moss · Unsiloed · MiniMax · Qwen
          </p>
        </div>
      </footer>
    </div>
  );
}
