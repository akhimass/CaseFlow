'use client';

import { useEffect, useMemo, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AnimatePresence, motion } from 'motion/react';
import { useLocalParticipant, useVoiceAssistant } from '@livekit/components-react';
import {
  ArrowClockwiseIcon,
  ArrowLeftIcon,
  MicrophoneIcon,
  MicrophoneSlashIcon,
  PauseIcon,
  PhoneDisconnectIcon,
  PlayIcon,
} from '@phosphor-icons/react/dist/ssr';
import { AudioVisualizer } from '@/components/agents-ui/blocks/agent-session-view-01/components/audio-visualizer';
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
  const { state: agentState } = useVoiceAssistant();
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const { briefing, replay } = useFirmBriefing(caseId);

  // Lawyer joins muted so the agent can narrate without picking up room noise;
  // the "Ask a question" button enables the mic on demand. Runs once on connect.
  const micInitialized = useRef(false);
  useEffect(() => {
    if (localParticipant && !micInitialized.current) {
      micInitialized.current = true;
      void localParticipant.setMicrophoneEnabled(false);
    }
  }, [localParticipant]);

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
            <Button asChild variant="ghost" size="sm">
              <Link href="/firm">
                <ArrowLeftIcon weight="bold" /> Back
              </Link>
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
            Caseflow Counsel · {firmName ?? 'firm'}
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
                  ? 'Connecting to Caseflow Counsel…'
                  : briefing.status === 'complete'
                    ? 'Briefing complete. Ask me anything about this case.'
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

      {/* Control bar */}
      <div className="border-border bg-background/90 fixed inset-x-0 bottom-0 z-20 border-t backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-center gap-2 px-6 py-3">
          <Button variant="outline" size="sm" onClick={onTogglePause}>
            {paused ? <PlayIcon weight="fill" /> : <PauseIcon weight="fill" />}
            {paused ? 'Resume' : 'Pause'}
          </Button>
          <Button variant="outline" size="sm" onClick={replay}>
            <ArrowClockwiseIcon weight="bold" /> Replay briefing
          </Button>
          <Button
            variant={isMicrophoneEnabled ? 'default' : 'outline'}
            size="sm"
            onClick={() => localParticipant?.setMicrophoneEnabled(!isMicrophoneEnabled)}
          >
            {isMicrophoneEnabled ? (
              <MicrophoneIcon weight="fill" />
            ) : (
              <MicrophoneSlashIcon weight="bold" />
            )}
            {isMicrophoneEnabled ? 'Listening' : 'Ask a question'}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-red-600 hover:text-red-700"
            onClick={() => router.push('/firm')}
          >
            <PhoneDisconnectIcon weight="bold" /> End
          </Button>
        </div>
      </div>
    </div>
  );
}
