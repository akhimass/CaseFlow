'use client';

import { Bot, FileText } from 'lucide-react';
import { FirmSidebarWordmark } from '@/components/marketing/logo';
import { MOCK_ROWS, PREVIEW_FIRM } from '@/lib/marketing';
import { cn } from '@/lib/shadcn/utils';

const TABLE_COLS =
  'grid-cols-[minmax(7rem,1.15fr)_minmax(5rem,0.85fr)_minmax(5.5rem,0.9fr)_2.5rem_minmax(3.5rem,0.65fr)_minmax(5.5rem,0.85fr)]';

const SIDEBAR_ITEMS = ['Home', 'Metrics', 'Firm', 'Overview'] as const;

const AGENT_TRANSCRIPT = [
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
    text: 'Veo una diferencia — usted mencionó la luz roja, pero el reporte no lo confirma. ¿Había testigos en el cruce?',
  },
  { role: 'agent', text: '¿Recibió atención médica o fue a urgencias?' },
  { role: 'system', text: 'Moss · Comparable settlements · CA rear-end · $45K–$95K' },
  { role: 'agent', text: 'Su caso califica. Un bufete lo contactará mañana por la mañana.' },
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

function WaveBars() {
  return (
    <div className="flex h-16 items-end justify-center gap-1">
      {[0.4, 0.7, 1, 0.6, 0.85, 0.5, 0.9, 0.65, 0.75, 0.55].map((h, i) => (
        <span
          key={i}
          className="bg-primary/80 w-1.5 rounded-full"
          style={{
            height: `${h * 100}%`,
            animation: `caseflow-wave 1.2s ease-in-out ${i * 0.08}s infinite alternate`,
          }}
        />
      ))}
    </div>
  );
}

export function ClientIntakePreview({ className }: { className?: string }) {
  const loopLines = [...AGENT_TRANSCRIPT, ...AGENT_TRANSCRIPT];

  return (
    <div className={className}>
      <p className="text-muted-foreground mb-2 text-xs font-semibold tracking-widest uppercase">
        Client intake
      </p>
      <WindowChrome>
        <div className="grid min-h-[280px] md:grid-cols-2">
          <div className="border-border flex flex-col items-center justify-center gap-4 border-b p-5 md:border-r md:border-b-0">
            <div className="relative">
              <div className="bg-muted flex size-24 items-center justify-center rounded-full ring-2 ring-emerald-500/30">
                <Bot className="text-primary size-12 stroke-[1.4]" aria-hidden />
              </div>
              <span className="absolute -right-1 -bottom-1 flex items-center gap-1 rounded-full bg-emerald-500 px-2 py-0.5 text-[10px] font-semibold text-white">
                <span className="size-1.5 animate-pulse rounded-full bg-white" />
                Live
              </span>
            </div>
            <div className="text-center">
              <p className="text-sm font-semibold">Caseflowy intake specialist</p>
              <p className="text-muted-foreground text-xs">Live video intake · EN / ES</p>
            </div>
            <WaveBars />
          </div>
          <div className="relative overflow-hidden p-3">
            <div className="text-muted-foreground mb-2 flex items-center justify-between text-[10px] font-semibold tracking-wide uppercase">
              <span>Agent output</span>
              <span className="text-emerald-600">Streaming</span>
            </div>
            <div className="relative h-[220px] overflow-hidden mask-[linear-gradient(to_bottom,transparent,black_8%,black_92%,transparent)]">
              <div className="animate-caseflow-transcript flex flex-col gap-2.5">
                {loopLines.map((line, i) => (
                  <div
                    key={`${line.role}-${i}`}
                    className={cn(
                      'rounded-lg px-2.5 py-2 text-xs leading-relaxed',
                      line.role === 'agent' && 'bg-muted text-foreground',
                      line.role === 'caller' && 'bg-background border-border border',
                      line.role === 'system' &&
                        'bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200'
                    )}
                  >
                    <span className="mb-0.5 block text-[10px] font-semibold tracking-wide uppercase opacity-60">
                      {line.role === 'agent'
                        ? 'Specialist'
                        : line.role === 'caller'
                          ? 'Caller'
                          : 'Caseflowy'}
                    </span>
                    {line.text}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </WindowChrome>
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
        <div className="grid md:grid-cols-[9.5rem_minmax(0,1fr)]">
          <aside className="border-border bg-muted/30 hidden border-r p-3 md:block">
            <div className="mb-3 min-w-0">
              <FirmSidebarWordmark />
              <div className="bg-muted/60 mt-3 rounded-lg px-2 py-1.5">
                <p className="text-muted-foreground text-[8px] font-semibold tracking-wide uppercase">
                  Your firm
                </p>
                <p className="mt-0.5 truncate text-[10px] leading-tight font-semibold">
                  {PREVIEW_FIRM.name}
                </p>
              </div>
            </div>
            {SIDEBAR_ITEMS.map((item) => (
              <div
                key={item}
                className={cn(
                  'mb-1 rounded-md px-2 py-1.5 text-sm',
                  item === 'Home'
                    ? 'bg-accent text-accent-foreground font-medium'
                    : 'text-muted-foreground'
                )}
              >
                {item}
              </div>
            ))}
          </aside>
          <div className="min-w-0 p-3 sm:p-4">
            <div className="mb-3 grid gap-2 sm:grid-cols-3">
              {[
                { label: 'Intakes today', value: '12' },
                { label: 'Qualified', value: '8', accent: true },
                { label: 'Live now', value: '3' },
              ].map(({ label, value, accent }) => (
                <div key={label} className="border-border rounded-lg border p-2.5">
                  <div className="text-muted-foreground text-[9px] font-semibold tracking-wide uppercase">
                    {label}
                  </div>
                  <div
                    className={cn(
                      'mt-1 text-xl font-bold tracking-tight',
                      accent && 'text-primary'
                    )}
                  >
                    {value}
                  </div>
                </div>
              ))}
            </div>
            <div className="border-border overflow-x-auto rounded-lg border">
              <div className="min-w-[28rem]">
                <div
                  className={cn(
                    'grid',
                    TABLE_COLS,
                    'border-border bg-muted/40 text-muted-foreground gap-1.5 border-b px-2 py-1.5 text-[8px] font-semibold tracking-wide uppercase sm:text-[9px]'
                  )}
                >
                  <span>Caller</span>
                  <span>Type</span>
                  <span>Disposition</span>
                  <span>Score</span>
                  <span>Value</span>
                  <span>Summary</span>
                </div>
                {MOCK_ROWS.slice(0, 4).map((row) => (
                  <div
                    key={row.caller}
                    className={cn(
                      'grid',
                      TABLE_COLS,
                      'border-border gap-1.5 border-b px-2 py-1.5 text-[10px] last:border-b-0 sm:text-xs'
                    )}
                  >
                    <span className="truncate">{row.caller}</span>
                    <span className="text-muted-foreground truncate">{row.type}</span>
                    <span>
                      <span
                        className={cn(
                          'inline-flex rounded-full px-1.5 py-0.5 text-[9px] font-medium',
                          row.ok ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
                        )}
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
                        <span className="text-primary inline-flex max-w-full items-center gap-0.5 truncate">
                          <FileText className="size-2.5 shrink-0" />
                          <span className="truncate underline underline-offset-2">
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
      </WindowChrome>
    </div>
  );
}
