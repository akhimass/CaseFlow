'use client';

import type { CaseRecord } from '@/hooks/useCaseflowEvents';

type TranscriptLine = {
  speaker?: string;
  text?: string;
  language?: string;
  turn?: number;
};

export function LiveTranscriptPanel({ record }: { record: CaseRecord }) {
  const lines = (record.transcript_lines as TranscriptLine[] | undefined) ?? [];
  const latest = record.transcript_line as TranscriptLine | undefined;

  const allLines = lines.length > 0 ? lines : latest?.text ? [latest] : [];

  return (
    <section className="border-border rounded-lg border p-4">
      <h3 className="text-muted-foreground mb-3 text-xs font-semibold tracking-wide uppercase">
        Live transcript
      </h3>
      {allLines.length === 0 ? (
        <p className="text-muted-foreground text-sm">Waiting for caller audio…</p>
      ) : (
        <ul className="max-h-64 space-y-2 overflow-y-auto text-sm">
          {allLines.map((line, idx) => (
            <li key={`${line.turn ?? idx}-${line.speaker}`} className="flex gap-2">
              <span className="text-muted-foreground w-16 shrink-0 capitalize">
                {line.speaker ?? 'caller'}
              </span>
              <span>{line.text}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
