'use client';

import { Camera, Mic, PhoneOff, Video } from 'lucide-react';
import { FirmSidebarWordmark } from '@/components/marketing/logo';
import { PREVIEW_FIRM, PREVIEW_LEADS } from '@/lib/marketing';
import { cn } from '@/lib/shadcn/utils';

const SIDEBAR_NAV = ['Home', 'Metrics', 'Firm', 'Overview'] as const;

const INTAKE_TRANSCRIPT = [
  {
    role: 'agent',
    text: 'Welcome to Caseflowy — take a breath, I’m here to help. Can you tell me what happened?',
  },
  {
    role: 'caller',
    text: 'Me chocaron por atrás en un semáforo… el otro conductor se pasó la luz roja.',
  },
  {
    role: 'agent',
    text: 'Lo siento mucho. ¿Tiene el reporte policial? Puede mostrarlo a la cámara.',
  },
  { role: 'system', text: 'Document parsed · Police report · Fault: undetermined' },
  {
    role: 'agent',
    text: 'Veo una diferencia — usted mencionó la luz roja, pero el reporte no lo confirma. ¿Había testigos?',
  },
] as const;

const COUNSEL_TRANSCRIPT = [
  {
    role: 'agent',
    text: 'Welcome back to Bay Counsel. Matched leads are in the cases hub below — I’m on the left and our conversation is on the right.',
  },
  {
    role: 'agent',
    text: 'Open any lead for the full dossier, or ask me how we gather sources and case briefs.',
  },
] as const;

function WindowChrome({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cn('border-border bg-card overflow-hidden rounded-xl border shadow-lg', className)}
    >
      <div className="border-border bg-muted/40 flex items-center gap-2 border-b px-4 py-3">
        <span className="size-3 rounded-full bg-[#ff5f57]" />
        <span className="size-3 rounded-full bg-[#febc2e]" />
        <span className="size-3 rounded-full bg-[#28c840]" />
      </div>
      {children}
    </div>
  );
}

function PreviewAura({ className }: { className?: string }) {
  return (
    <div className={cn('relative flex items-center justify-center', className)}>
      <div
        className="absolute size-[88%] rounded-full"
        style={{ background: 'radial-gradient(circle, #2563EB22 0%, transparent 70%)' }}
      />
      <div
        className="absolute size-[74%] animate-pulse rounded-full border opacity-40"
        style={{ borderColor: '#2563EB60' }}
      />
      <div
        className="absolute size-[62%] rounded-full border-2 opacity-50"
        style={{ borderColor: '#2563EB90' }}
      />
      <div className="bg-primary/25 size-[48%] rounded-full blur-[1px]" />
    </div>
  );
}

function PreviewControlBar({ withCamera = false }: { withCamera?: boolean }) {
  return (
    <div className="bg-muted/40 flex items-center justify-center gap-2 rounded-full px-2 py-1.5">
      <span className="bg-background border-border flex size-8 items-center justify-center rounded-full border">
        <Mic className="size-3.5" strokeWidth={2.2} />
      </span>
      {withCamera ? (
        <span className="bg-background border-border flex size-8 items-center justify-center rounded-full border">
          <Video className="size-3.5" strokeWidth={2.2} />
        </span>
      ) : null}
      <span className="bg-destructive/10 text-destructive inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[10px] font-bold tracking-wider">
        <PhoneOff className="size-3" strokeWidth={2.5} />
        END CALL
      </span>
    </div>
  );
}

function TranscriptLines({
  lines,
  loop = false,
  className,
}: {
  lines: ReadonlyArray<{ role: string; text: string }>;
  loop?: boolean;
  className?: string;
}) {
  const rendered = loop ? [...lines, ...lines] : lines;

  return (
    <div className={cn('flex flex-col gap-2', loop && 'animate-caseflow-transcript', className)}>
      {rendered.map((line, i) => (
        <div
          key={`${line.role}-${i}`}
          className={cn(
            'rounded-lg px-2.5 py-2 text-[11px] leading-relaxed',
            line.role === 'agent' && 'bg-muted text-foreground',
            line.role === 'caller' && 'bg-background border-border border',
            line.role === 'system' &&
              'bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200'
          )}
        >
          <span className="mb-0.5 block text-[9px] font-semibold tracking-wide uppercase opacity-60">
            {line.role === 'agent' ? 'Counsel' : line.role === 'caller' ? 'Caller' : 'Caseflowy'}
          </span>
          {line.text}
        </div>
      ))}
    </div>
  );
}

export function ClientIntakePreview({ className }: { className?: string }) {
  const loopLines = [...INTAKE_TRANSCRIPT, ...INTAKE_TRANSCRIPT];

  return (
    <div className={className}>
      <p className="text-muted-foreground mb-2 text-xs font-semibold tracking-widest uppercase">
        Client intake
      </p>
      <WindowChrome>
        <div className="flex min-h-[320px] flex-col">
          <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-2">
            {/* Left — matches IntakeMediaPanel */}
            <div className="border-border flex flex-col border-b p-3 md:border-r md:border-b-0 md:p-4">
              <div className="bg-muted/40 text-muted-foreground relative mb-3 flex min-h-[100px] flex-1 flex-col items-center justify-center gap-1 rounded-2xl border px-4 text-center">
                <Camera className="size-5 opacity-50" strokeWidth={1.8} />
                <span className="text-[11px] font-medium">Your camera</span>
                <span className="text-[10px]">Turn on video to show your documents</span>
              </div>
              <div className="flex flex-col items-center gap-2 py-1">
                <PreviewAura className="size-24" />
                <p className="text-[11px] font-medium">Speaking</p>
              </div>
            </div>

            {/* Right — matches IntakeIntelligencePanel */}
            <div className="flex min-h-0 flex-col">
              <div className="border-border shrink-0 border-b px-3 py-2">
                <h2 className="text-[11px] font-semibold tracking-tight">Conversation</h2>
                <p className="text-muted-foreground text-[10px]">
                  The specialist speaks aloud — transcript updates here
                </p>
              </div>
              <div className="relative min-h-[120px] flex-1 overflow-hidden mask-[linear-gradient(to_bottom,transparent,black_6%,black_94%,transparent)] px-2 py-2">
                <TranscriptLines lines={loopLines} loop className="text-xs" />
              </div>
              <div className="border-border max-h-[38%] shrink-0 space-y-2 overflow-hidden border-t px-3 py-2">
                <div>
                  <p className="text-muted-foreground mb-1 text-[9px] font-semibold tracking-wide uppercase">
                    Unsiloed · live parsing
                  </p>
                  <div className="border-border bg-card rounded-lg border p-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-semibold">Police Report</span>
                      <span className="text-[9px] font-medium text-emerald-600">4 fields</span>
                    </div>
                    <dl className="text-muted-foreground mt-1 space-y-0.5 text-[9px]">
                      <div className="flex justify-between gap-2">
                        <dt>Fault</dt>
                        <dd className="text-foreground font-medium">Undetermined</dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt>Injuries</dt>
                        <dd className="text-foreground font-medium">Whiplash</dd>
                      </div>
                    </dl>
                  </div>
                </div>
                <div>
                  <p className="text-muted-foreground mb-1 text-[9px] font-semibold tracking-wide uppercase">
                    Moss · retrieval
                  </p>
                  <div className="border-border bg-card flex items-start gap-2 rounded-lg border p-2">
                    <span className="mt-0.5 size-1.5 shrink-0 rounded-full bg-violet-500" />
                    <div className="min-w-0">
                      <p className="text-[10px] font-semibold">Comparable settlements</p>
                      <p className="text-muted-foreground text-[9px]">CA rear-end · $45K–$95K</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom — matches AgentControlBar row */}
          <div className="border-border shrink-0 border-t px-3 py-2">
            <PreviewControlBar withCamera />
          </div>
        </div>
      </WindowChrome>
    </div>
  );
}

function PreviewLeadCard({
  caller,
  type,
  score,
  value,
  qualified,
  summary,
}: (typeof PREVIEW_LEADS)[number]) {
  return (
    <div className="border-border bg-background flex flex-col rounded-xl border p-2.5 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-[11px] font-semibold">{caller}</p>
          <p className="text-muted-foreground truncate text-[10px]">{type}</p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-muted-foreground text-[8px] font-semibold tracking-wide uppercase">
            Case strength
          </p>
          <p className="text-primary text-base leading-none font-bold tabular-nums">{score}</p>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span
          className={cn(
            'inline-flex rounded-full px-1.5 py-0.5 text-[9px] font-medium',
            qualified ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
          )}
        >
          {qualified ? 'Qualified' : 'Declined'}
        </span>
        <span className="text-muted-foreground text-[10px]">
          Est. <span className="text-foreground font-semibold">{value}</span>
        </span>
      </div>
      <p className="text-muted-foreground mt-2 line-clamp-2 text-[9px] leading-relaxed">
        {summary}
      </p>
      <div className="mt-2 flex gap-1.5">
        <span className="bg-primary text-primary-foreground flex-1 rounded-md px-2 py-1 text-center text-[9px] font-medium">
          View dossier
        </span>
        <span className="border-border flex-1 rounded-md border px-2 py-1 text-center text-[9px] font-medium">
          Voice briefing
        </span>
      </div>
    </div>
  );
}

export function FirmDashboardPreview({ className }: { className?: string }) {
  return (
    <div className={className}>
      <p className="text-muted-foreground mb-2 text-xs font-semibold tracking-widest uppercase">
        Firm dashboard
      </p>
      <WindowChrome>
        <div className="bg-muted/20 flex min-h-[360px]">
          {/* Sidebar — matches FirmDashboardShell */}
          <aside className="border-border bg-background hidden w-[8.5rem] shrink-0 flex-col border-r p-2.5 sm:flex">
            <FirmSidebarWordmark className="origin-left scale-90" />
            <div className="bg-muted/50 mt-2 rounded-lg px-2 py-1.5">
              <p className="text-muted-foreground text-[7px] font-semibold tracking-wide uppercase">
                Your firm
              </p>
              <p className="mt-0.5 truncate text-[9px] leading-tight font-semibold">
                {PREVIEW_FIRM.name}
              </p>
            </div>
            <nav className="mt-2 flex flex-1 flex-col gap-0.5">
              {SIDEBAR_NAV.map((item) => (
                <div
                  key={item}
                  className={cn(
                    'rounded-md px-2 py-1 text-[10px] font-medium',
                    item === 'Home' ? 'bg-accent text-accent-foreground' : 'text-muted-foreground'
                  )}
                >
                  {item}
                </div>
              ))}
            </nav>
            <div className="border-border mt-auto space-y-1.5 border-t pt-2">
              <div className="text-muted-foreground flex items-center gap-1.5 text-[9px]">
                <span className="size-1.5 animate-pulse rounded-full bg-emerald-500" />
                Live feed
              </div>
              <span className="bg-primary text-primary-foreground block rounded-md px-2 py-1 text-center text-[9px] font-medium">
                Auto-brief on
              </span>
            </div>
          </aside>

          {/* Main — matches FirmHomeContent */}
          <div className="flex min-w-0 flex-1 flex-col gap-2 p-2.5 sm:p-3">
            <div className="grid min-h-[140px] flex-1 gap-2 sm:grid-cols-2">
              {/* Counsel visualizer */}
              <div className="border-border bg-background flex flex-col items-center justify-center rounded-2xl border px-3 py-4 text-center">
                <p className="text-muted-foreground text-[8px] font-semibold tracking-wide uppercase">
                  Caseflowy Counsel
                </p>
                <p className="mt-1 text-[11px] font-semibold">Your marketplace command center</p>
                <PreviewAura className="my-3 size-16" />
                <p className="text-muted-foreground text-[9px]">Counsel is speaking</p>
              </div>

              {/* Conversation panel */}
              <div className="border-border bg-background flex flex-col overflow-hidden rounded-2xl border">
                <div className="border-border shrink-0 border-b px-2.5 py-2">
                  <h2 className="text-[11px] font-semibold tracking-tight">Conversation</h2>
                  <p className="text-muted-foreground text-[9px]">
                    Turn your mic on to talk — transcript updates here live
                  </p>
                </div>
                <div className="min-h-0 flex-1 overflow-hidden px-2 py-1.5">
                  <TranscriptLines lines={COUNSEL_TRANSCRIPT} />
                </div>
                <div className="border-border shrink-0 border-t px-2 py-1.5">
                  <PreviewControlBar />
                </div>
              </div>
            </div>

            {/* Cases hub */}
            <section className="border-border bg-background shrink-0 rounded-2xl border p-2.5">
              <p className="text-muted-foreground text-[8px] font-semibold tracking-wide uppercase">
                Cases hub
              </p>
              <p className="mt-0.5 text-[10px] font-semibold">
                Matched leads for {PREVIEW_FIRM.name}
              </p>
              <div className="mt-2 grid grid-cols-3 gap-1.5">
                {[
                  { label: 'Intakes today', value: '12' },
                  { label: 'Qualified', value: '8', accent: true },
                  { label: 'Live now', value: '3' },
                ].map(({ label, value, accent }) => (
                  <div key={label} className="border-border rounded-lg border p-1.5">
                    <p className="text-muted-foreground text-[7px] font-semibold tracking-wide uppercase">
                      {label}
                    </p>
                    <p
                      className={cn(
                        'mt-0.5 text-sm font-bold tabular-nums',
                        accent && 'text-primary'
                      )}
                    >
                      {value}
                    </p>
                  </div>
                ))}
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {PREVIEW_LEADS.map((lead) => (
                  <PreviewLeadCard key={lead.caller} {...lead} />
                ))}
              </div>
            </section>
          </div>
        </div>
      </WindowChrome>
    </div>
  );
}
