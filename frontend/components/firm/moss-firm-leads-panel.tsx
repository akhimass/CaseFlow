'use client';

import type { CaseRecord } from '@/hooks/useCaseflowEvents';

/**
 * Moss firm lead-gen. Each lead is produced by a single Moss multi-index call
 * that correlates the firms index with comparable settlements and the
 * jurisdiction filing rule — so every firm card carries its own grounding
 * evidence (track record, comparable range, why it fits this case).
 */

type FirmLead = {
  firm_id?: string;
  name?: string;
  phone?: string;
  languages?: string[];
  specialties?: string[];
  score?: number;
  match_reasons?: string[];
  rating?: string;
  years_experience?: string;
  response_time_hours?: string;
  track_settlement_low?: number;
  track_settlement_high?: number;
  comparable_range?: string;
  jurisdiction_note?: string;
  profile_excerpt?: string;
};

const LANG_LABEL: Record<string, string> = {
  en: 'English',
  es: 'Spanish',
  zh: 'Mandarin',
  hi: 'Hindi',
};

function money(n?: number): string {
  if (!n) return '';
  return `$${Math.round(n).toLocaleString()}`;
}

export function MossFirmLeadsPanel({ record }: { record: CaseRecord }) {
  const leads = (record.moss_firm_leads as FirmLead[] | undefined) ?? [];
  if (leads.length === 0) return null;

  return (
    <section className="border-border rounded-lg border p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
          Matched firms · Moss lead-gen
        </h3>
        <span className="text-muted-foreground/60 text-[10px]">
          correlated from firms × settlements × law
        </span>
      </div>

      <ol className="space-y-2.5">
        {leads.map((ld, i) => (
          <li
            key={ld.firm_id ?? i}
            className={`rounded-lg border p-3 ${
              i === 0 ? 'border-emerald-500/40 bg-emerald-500/5' : 'border-border'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  {i === 0 ? (
                    <span className="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-600">
                      TOP MATCH
                    </span>
                  ) : null}
                  <span className="truncate text-sm font-semibold">{ld.name}</span>
                </div>
                <div className="text-muted-foreground mt-0.5 truncate text-xs">
                  {(ld.specialties ?? []).slice(0, 3).join(' · ').replace(/_/g, ' ')}
                </div>
              </div>
              <div className="flex shrink-0 flex-col items-end">
                <span className="text-lg font-bold text-emerald-600 tabular-nums">{ld.score}</span>
                <span className="text-muted-foreground/60 text-[9px]">fit score</span>
              </div>
            </div>

            {/* Firm credentials */}
            <div className="text-muted-foreground/80 mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] tabular-nums">
              {ld.rating ? <span>★ {ld.rating}</span> : null}
              {ld.years_experience ? <span>{ld.years_experience} yrs</span> : null}
              {ld.response_time_hours ? <span>~{ld.response_time_hours}h callback</span> : null}
              {(ld.languages ?? []).length > 0 ? (
                <span>{(ld.languages ?? []).map((l) => LANG_LABEL[l] ?? l).join(', ')}</span>
              ) : null}
            </div>

            {/* Correlated evidence — the point of the multi-index call */}
            <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
              {ld.comparable_range ? (
                <div className="rounded border border-violet-500/20 bg-violet-500/5 px-2 py-1">
                  <div className="text-[9px] font-semibold text-violet-600/80 uppercase">
                    Comparable outcomes
                  </div>
                  <div className="text-xs font-medium tabular-nums">{ld.comparable_range}</div>
                </div>
              ) : null}
              {ld.track_settlement_low || ld.track_settlement_high ? (
                <div className="rounded border border-emerald-500/20 bg-emerald-500/5 px-2 py-1">
                  <div className="text-[9px] font-semibold text-emerald-600/80 uppercase">
                    Firm track record
                  </div>
                  <div className="text-xs font-medium tabular-nums">
                    {money(ld.track_settlement_low)}–{money(ld.track_settlement_high)}
                  </div>
                </div>
              ) : null}
            </div>

            {/* Why this firm fits */}
            {(ld.match_reasons ?? []).length > 0 ? (
              <ul className="mt-2 flex flex-wrap gap-1">
                {(ld.match_reasons ?? []).map((r, j) => (
                  <li
                    key={j}
                    className="bg-muted text-muted-foreground rounded-full px-2 py-0.5 text-[10px]"
                  >
                    {r}
                  </li>
                ))}
              </ul>
            ) : null}

            {ld.jurisdiction_note ? (
              <p className="text-muted-foreground/70 mt-2 text-[10px] italic">
                {ld.jurisdiction_note}
              </p>
            ) : null}

            {ld.phone ? (
              <div className="text-muted-foreground mt-2 text-[11px] tabular-nums">{ld.phone}</div>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
