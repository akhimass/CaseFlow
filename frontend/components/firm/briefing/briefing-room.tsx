'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ConnectionState } from 'livekit-client';
import { AnimatePresence, motion } from 'motion/react';
import { useConnectionState, useVoiceAssistant } from '@livekit/components-react';
import {
  ArrowClockwiseIcon,
  ArrowLeftIcon,
  PauseIcon,
  PlayIcon,
} from '@phosphor-icons/react/dist/ssr';
import { AudioVisualizer } from '@/components/agents-ui/blocks/agent-session-view-01/components/audio-visualizer';
import { FirmCounselControls } from '@/components/firm/dashboard/firm-counsel-controls';
import { Button } from '@/components/ui/button';
import { type CaseRecord } from '@/hooks/useCaseflowEvents';
import { useFirmBriefing } from '@/hooks/useFirmBriefing';
import { cn } from '@/lib/shadcn/utils';

type SectionDef = {
  id: string;
  title: string;
  render: (record: CaseRecord) => React.ReactNode;
  available: (record: CaseRecord) => boolean;
};

function fieldText(record: CaseRecord, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = record[key];
    if (value !== undefined && value !== null && String(value).trim()) return String(value);
  }
  return undefined;
}

function snippetTexts(record: CaseRecord, namespace: string, limit = 4): string[] {
  const retrievals = (record.moss_retrievals as Array<Record<string, unknown>>) ?? [];
  const texts: string[] = [];
  for (const ev of retrievals) {
    if ((ev as { namespace?: string }).namespace !== namespace) continue;
    const snippets = ((ev as { snippets?: Array<Record<string, unknown>> }).snippets ??
      []) as Array<{
      text?: string;
    }>;
    for (const s of snippets) {
      if (s.text) texts.push(String(s.text));
    }
  }
  return Array.from(new Set(texts)).slice(0, limit);
}

const SECTIONS: SectionDef[] = [
  {
    id: 'overview',
    title: 'Case overview',
    available: () => true,
    render: (record) => {
      const fields = (
        [
          ['Caller', fieldText(record, 'caller_id', 'case_id')],
          ['Accident', fieldText(record, 'accident_type')?.replace(/_/g, ' ')],
          ['Jurisdiction', fieldText(record, 'state', 'jurisdiction')],
          ['Location', fieldText(record, 'caller_location', 'location')],
          ['Injuries', fieldText(record, 'injuries')],
          ['Fault claim', fieldText(record, 'fault_claim')],
          ['Language', fieldText(record, 'language')],
        ] as Array<[string, string | undefined]>
      ).filter(([, v]) => v);
      const score = Number(record.score ?? record.case_strength ?? 0);
      return (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <dl className="grid flex-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            {fields.map(([label, value]) => (
              <div key={label}>
                <dt className="text-muted-foreground text-xs">{label}</dt>
                <dd className="font-medium capitalize">{value}</dd>
              </div>
            ))}
          </dl>
          {score > 0 && (
            <div className="shrink-0 text-right">
              <div className="text-muted-foreground text-xs tracking-wide uppercase">Strength</div>
              <div
                className={cn(
                  'text-4xl font-bold tabular-nums',
                  score >= 70 ? 'text-emerald-600' : score >= 40 ? 'text-amber-600' : 'text-red-600'
                )}
              >
                {score}
                <span className="text-muted-foreground text-base font-normal">/100</span>
              </div>
            </div>
          )}
        </div>
      );
    },
  },
  {
    id: 'discrepancy',
    title: 'Consistency audit',
    available: (record) => {
      const audit = (record.consistency_audit ?? {}) as { conflict?: boolean; reason?: string };
      return Boolean(audit.conflict || audit.reason || record.last_event === 'discrepancy_found');
    },
    render: (record) => {
      const audit = (record.consistency_audit ?? {}) as {
        conflict_type?: string;
        reason?: string;
        clarifying_question?: string;
      };
      return (
        <div className="space-y-2 text-sm">
          {audit.conflict_type && (
            <p>
              <span className="font-medium">Type:</span> {audit.conflict_type}
            </p>
          )}
          {audit.reason && <p>{audit.reason}</p>}
          {audit.clarifying_question && (
            <p className="border-border bg-background/60 mt-2 rounded-md border p-3 italic">
              “{audit.clarifying_question}”
            </p>
          )}
        </div>
      );
    },
  },
  {
    id: 'law',
    title: 'Jurisdictional law',
    available: (record) => snippetTexts(record, 'state-law').length > 0,
    render: (record) => (
      <ul className="space-y-2 text-sm">
        {snippetTexts(record, 'state-law').map((t, i) => (
          <li key={i} className="text-muted-foreground">
            {t}
          </li>
        ))}
      </ul>
    ),
  },
  {
    id: 'comparables',
    title: 'Comparable settlements',
    available: (record) => snippetTexts(record, 'settlements').length > 0,
    render: (record) => (
      <ul className="space-y-2 text-sm">
        {snippetTexts(record, 'settlements').map((t, i) => (
          <li key={i} className="text-muted-foreground">
            {t}
          </li>
        ))}
      </ul>
    ),
  },
  {
    id: 'recommendation',
    title: 'Recommended action',
    available: (record) => {
      const matches = (record.matches as unknown[]) ?? [];
      return matches.length > 0 || Boolean(record.firm_brief) || Boolean(record.verbal_summary);
    },
    render: (record) => {
      const matches = (record.matches as Array<Record<string, unknown>>) ?? [];
      const verbal = fieldText(record, 'verbal_summary');
      return (
        <div className="space-y-3 text-sm">
          {verbal && <p>{verbal}</p>}
          {matches.slice(0, 3).map((m) => (
            <div key={String(m.firm_id)} className="border-border bg-card rounded-md border p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold">{String(m.name)}</span>
                <span className="text-primary tabular-nums">{String(m.score)}</span>
              </div>
              {Boolean(m.reasoning) && (
                <p className="text-muted-foreground mt-1">{String(m.reasoning)}</p>
              )}
            </div>
          ))}
        </div>
      );
    },
  },
];

export function BriefingRoom({
  record,
  caseId,
  firmName,
  paused,
  onTogglePause,
}: {
  record: CaseRecord;
  caseId: string;
  firmName?: string;
  paused: boolean;
  onTogglePause: () => void;
}) {
  const router = useRouter();
  const connectionState = useConnectionState();
  const connected = connectionState === ConnectionState.Connected;
  const { state: agentState } = useVoiceAssistant();
  const { briefing, replay } = useFirmBriefing(caseId);

  // Self-heal a stuck briefing. The agent auto-narrates the moment it connects,
  // but if those reliable data packets are sent before this client attaches its
  // DataReceived listener, LiveKit drops them and the briefing sits idle forever.
  // Once we're connected and listening, if nothing has arrived shortly, ask the
  // agent to (re)narrate — this fires while we're guaranteed to be listening.
  const recoveryRequested = useRef(false);
  useEffect(() => {
    if (!connected) return;
    if (briefing.status !== 'idle' || briefing.total > 0 || briefing.caption) return;
    if (recoveryRequested.current) return;
    const timer = setTimeout(() => {
      recoveryRequested.current = true;
      void replay();
    }, 2500);
    return () => clearTimeout(timer);
  }, [connected, briefing.status, briefing.total, briefing.caption, replay]);

  // After a longer grace period with no narration, surface an honest, actionable
  // message instead of an indefinite "Preparing your briefing…".
  const [stalled, setStalled] = useState(false);
  useEffect(() => {
    if (briefing.caption || briefing.status === 'complete') {
      setStalled(false);
      return;
    }
    const timer = setTimeout(() => setStalled(true), 14000);
    return () => clearTimeout(timer);
  }, [briefing.caption, briefing.status]);

  const leave = useCallback(() => {
    recoveryRequested.current = true;
    router.push('/firm');
  }, [router]);

  const handleReplay = useCallback(() => {
    recoveryRequested.current = true;
    setStalled(false);
    void replay();
  }, [replay]);

  const sections = useMemo(() => SECTIONS.filter((s) => s.available(record)), [record]);
  const title = fieldText(record, 'caller_id', 'case_id') ?? 'New lead';
  const subtitle = [
    fieldText(record, 'accident_type')?.replace(/_/g, ' '),
    fieldText(record, 'state', 'jurisdiction'),
  ]
    .filter(Boolean)
    .join(' · ');

  const connecting = agentState === 'connecting' || agentState === 'initializing';

  return (
    <div className="bg-background flex min-h-svh flex-col">
      {/* Header */}
      <header className="border-border bg-background/80 sticky top-0 z-10 border-b px-6 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Button type="button" variant="ghost" size="sm" onClick={leave}>
              <ArrowLeftIcon weight="bold" /> Back
            </Button>
            <div>
              <div className="font-semibold capitalize">{title}</div>
              {subtitle && (
                <div className="text-muted-foreground text-xs capitalize">{subtitle}</div>
              )}
            </div>
          </div>
          <div className="text-muted-foreground flex items-center gap-2 text-xs">
            <span
              className={cn(
                'size-2 rounded-full',
                agentState === 'speaking'
                  ? 'animate-pulse bg-sky-500'
                  : connecting
                    ? 'bg-amber-500'
                    : 'bg-emerald-500'
              )}
            />
            Caseflowy Counsel · {firmName ?? 'firm'}
          </div>
        </div>
      </header>

      {/* Hero — voice + live caption */}
      <div className="mx-auto flex w-full max-w-5xl flex-col items-center px-6 pt-8 pb-4 text-center">
        <div className="relative flex h-44 w-full items-center justify-center">
          <AudioVisualizer
            isChatOpen={false}
            audioVisualizerType="aura"
            audioVisualizerColor="#2563EB"
            className="!size-44"
          />
        </div>
        <div className="mt-2 min-h-[5.5rem] max-w-2xl">
          <AnimatePresence mode="wait">
            <motion.p
              key={briefing.caption ?? agentState}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.25 }}
              className="text-lg leading-relaxed text-balance"
            >
              {briefing.caption ??
                (connecting
                  ? 'Connecting to Caseflowy Counsel…'
                  : briefing.status === 'complete'
                    ? 'Briefing complete. Ask me anything about this case.'
                    : stalled
                      ? 'Couldn’t reach Caseflowy Counsel. Tap “Replay briefing”, or go back to your leads.'
                      : 'Preparing your briefing…')}
            </motion.p>
          </AnimatePresence>
        </div>
        {briefing.total > 0 && (
          <div className="mt-3 flex items-center gap-1.5">
            {Array.from({ length: briefing.total }).map((_, i) => (
              <span
                key={i}
                className={cn(
                  'h-1 rounded-full transition-all',
                  i <= briefing.index && briefing.status !== 'idle'
                    ? 'bg-primary w-6'
                    : 'bg-border w-3'
                )}
              />
            ))}
          </div>
        )}
      </div>

      {/* Section cards */}
      <main className="mx-auto w-full max-w-5xl flex-1 space-y-3 px-6 pb-32">
        {sections.map((section) => {
          const isActive = briefing.activeSection === section.id;
          const isVisited = briefing.visited.includes(section.id);
          const dim = briefing.status !== 'idle' && !isActive && !isVisited;
          return (
            <motion.section
              key={section.id}
              layout
              animate={{ opacity: dim ? 0.45 : 1, scale: isActive ? 1.0 : 1 }}
              transition={{ duration: 0.3 }}
              className={cn(
                'rounded-xl border p-5 transition-colors',
                isActive
                  ? 'border-primary/50 bg-primary/5 shadow-sm'
                  : section.id === 'discrepancy'
                    ? 'border-amber-500/40 bg-amber-500/5'
                    : 'border-border bg-card'
              )}
            >
              <div className="mb-3 flex items-center gap-2">
                <h2 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
                  {section.title}
                </h2>
                {isActive && (
                  <span className="text-primary inline-flex items-center gap-1 text-xs font-medium">
                    <span className="bg-primary size-1.5 animate-pulse rounded-full" /> Speaking
                  </span>
                )}
              </div>
              {section.render(record)}
            </motion.section>
          );
        })}
      </main>

      {/* Control bar — mic + end match client intake; pause/replay for briefing */}
      <div className="border-border bg-background/90 pointer-events-auto fixed inset-x-0 bottom-0 z-30 border-t pb-[env(safe-area-inset-bottom)] backdrop-blur">
        <div className="mx-auto max-w-5xl px-6 py-3">
          <FirmCounselControls
            leaveLabel="END BRIEFING"
            onLeave={leave}
            extraControls={
              <>
                <Button type="button" variant="outline" size="sm" onClick={onTogglePause}>
                  {paused ? <PlayIcon weight="fill" /> : <PauseIcon weight="fill" />}
                  {paused ? 'Resume' : 'Pause'}
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={handleReplay}>
                  <ArrowClockwiseIcon weight="bold" /> Replay briefing
                </Button>
              </>
            }
          />
        </div>
      </div>
    </div>
  );
}
