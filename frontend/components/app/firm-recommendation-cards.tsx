'use client';

import type { FirmRecommendation } from '@/hooks/useFirmRecommendations';

/**
 * Matched-firm cards shown to the caller at the recommendation moment. Each is
 * backed by Moss semantic search over enriched firm profiles, parsed case facts,
 * and comparable settlements — so the caller sees the phone number, how the firm
 * fits their case, and can choose one. The top match is highlighted.
 */

const LANG_LABEL: Record<string, string> = {
  en: 'English',
  es: 'Spanish',
  zh: 'Mandarin',
  hi: 'Hindi',
};

function telHref(phone?: string): string | undefined {
  if (!phone) return undefined;
  const digits = phone.replace(/[^\d+]/g, '');
  return digits ? `tel:${digits}` : undefined;
}

export function FirmRecommendationCards({ firms }: { firms: FirmRecommendation[] }) {
  if (!firms || firms.length === 0) return null;

  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
          Recommended firms
        </h3>
        <span className="text-muted-foreground text-[10px]">matched by Moss semantic search</span>
      </div>

      <ol className="space-y-2">
        {firms.map((firm, i) => {
          const href = telHref(firm.phone);
          return (
            <li
              key={firm.firm_id ?? i}
              className={`rounded-xl border p-3 ${
                i === 0 ? 'border-emerald-500/50 bg-emerald-500/5' : 'border-border'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    {i === 0 && (
                      <span className="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-semibold tracking-wide text-emerald-600 uppercase">
                        Recommended
                      </span>
                    )}
                    <span className="truncate text-sm font-semibold">{firm.name}</span>
                  </div>
                  {firm.specialties && firm.specialties.length > 0 && (
                    <div className="text-muted-foreground mt-0.5 truncate text-xs">
                      {firm.specialties.slice(0, 3).join(' · ').replace(/_/g, ' ')}
                    </div>
                  )}
                </div>
                {typeof firm.score === 'number' && (
                  <div className="flex shrink-0 flex-col items-end">
                    <span className="text-base font-bold text-emerald-600 tabular-nums">
                      {Math.round(firm.score)}
                    </span>
                    <span className="text-muted-foreground/60 text-[9px]">case fit</span>
                  </div>
                )}
              </div>

              {/* Credentials */}
              <div className="text-muted-foreground/80 mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] tabular-nums">
                {firm.rating && <span>★ {firm.rating}</span>}
                {firm.years_experience && <span>{firm.years_experience} yrs</span>}
                {firm.response_time_hours && <span>~{firm.response_time_hours}h callback</span>}
                {firm.languages && firm.languages.length > 0 && (
                  <span>{firm.languages.map((l) => LANG_LABEL[l] ?? l).join(', ')}</span>
                )}
              </div>

              {/* How they fit this case (Moss-grounded reasons) */}
              {firm.match_reasons && firm.match_reasons.length > 0 && (
                <ul className="mt-2 flex flex-wrap gap-1">
                  {firm.match_reasons.slice(0, 4).map((reason, j) => (
                    <li
                      key={j}
                      className="bg-muted text-muted-foreground rounded-full px-2 py-0.5 text-[10px]"
                    >
                      {reason}
                    </li>
                  ))}
                </ul>
              )}

              {firm.comparable_range && (
                <p className="text-muted-foreground/80 mt-2 text-[11px]">
                  Comparable case outcomes:{' '}
                  <span className="font-medium tabular-nums">{firm.comparable_range}</span>
                </p>
              )}

              {/* Phone — the call to action */}
              {firm.phone && (
                <div className="mt-2">
                  {href ? (
                    <a
                      href={href}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/40 px-2.5 py-1 text-xs font-semibold text-emerald-600 transition-colors hover:bg-emerald-500/10"
                    >
                      <span aria-hidden>📞</span>
                      {firm.phone}
                    </a>
                  ) : (
                    <span className="text-sm font-medium tabular-nums">{firm.phone}</span>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
