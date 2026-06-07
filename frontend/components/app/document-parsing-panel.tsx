'use client';

import type { DocumentParseEvent } from '@/hooks/useDocumentParseEvents';

function formatDocType(docType: string): string {
  return docType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function DocumentParsingPanel({ events }: { events: DocumentParseEvent[] }) {
  if (events.length === 0) return null;

  return (
    <div className="space-y-2">
      <h3 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
        Unsiloed · live parsing
      </h3>
      {events.map((event) => (
        <div
          key={event.id}
          className="border-border bg-card/95 rounded-lg border p-3 shadow-sm backdrop-blur-sm"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold">{formatDocType(event.docType)}</span>
            {event.status === 'parsing' ? (
              <span className="animate-pulse text-xs font-medium text-amber-600">
                Reading your document…
              </span>
            ) : (
              <span className="text-xs font-medium text-emerald-600">
                {Object.keys(event.fields).length} fields
              </span>
            )}
          </div>
          {event.status === 'parsed' && Object.keys(event.fields).length > 0 && (
            <dl className="mt-2 space-y-1 text-xs">
              {Object.entries(event.fields)
                .slice(0, 4)
                .map(([key, value]) => (
                  <div key={key} className="flex justify-between gap-2">
                    <dt className="text-muted-foreground">{key}</dt>
                    <dd className="text-right font-medium">{String(value)}</dd>
                  </div>
                ))}
            </dl>
          )}
        </div>
      ))}
    </div>
  );
}
