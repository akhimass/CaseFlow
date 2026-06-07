'use client';

import type { CaseRecord } from '@/hooks/useCaseflowEvents';

type VoiceBridge = {
  stt_provider?: string;
  stt_model?: string;
  detected_language?: string;
  language_switched?: boolean;
  tts_provider?: string;
  tts_model?: string;
  tts_voice?: string;
};

function langLabel(code?: string): string {
  if (!code) return '—';
  if (code.startsWith('es')) return 'Spanish (ES)';
  if (code.startsWith('en')) return 'English (EN)';
  return code.toUpperCase();
}

export function VoiceBridgePanel({ record }: { record: CaseRecord }) {
  const bridge = record.voice_bridge as VoiceBridge | undefined;

  if (!bridge) {
    return (
      <section className="border-border rounded-lg border border-dashed p-4">
        <h3 className="text-muted-foreground mb-1 text-xs font-semibold tracking-wide uppercase">
          Voice bridge · Deepgram → MiniMax
        </h3>
        <p className="text-muted-foreground text-sm">
          STT/TTS routing appears when the caller speaks.
        </p>
      </section>
    );
  }

  return (
    <section className="border-border rounded-lg border p-4">
      <h3 className="text-muted-foreground mb-3 text-xs font-semibold tracking-wide uppercase">
        Voice bridge · Deepgram → MiniMax
      </h3>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge
          label="STT"
          value={`${bridge.stt_provider ?? 'Deepgram'} ${bridge.stt_model ?? 'nova-3'}`}
        />
        <span className="text-muted-foreground">→</span>
        <Badge
          label={langLabel(bridge.detected_language)}
          value={bridge.language_switched ? 'language switched' : 'multilingual detect'}
          accent
        />
        <span className="text-muted-foreground">→</span>
        <Badge
          label="TTS"
          value={`${bridge.tts_provider ?? 'MiniMax'} ${bridge.tts_model ?? 'Speech 2.8 HD'}`}
        />
        {bridge.tts_voice && (
          <span className="text-muted-foreground font-mono text-xs">{bridge.tts_voice}</span>
        )}
      </div>
    </section>
  );
}

function Badge({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
        accent
          ? 'border-violet-500/40 bg-violet-500/10 text-violet-700 dark:text-violet-300'
          : 'border-border bg-muted/50'
      }`}
    >
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </span>
  );
}
