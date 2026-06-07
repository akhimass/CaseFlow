'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { PRIVACY_COPY, detectConsumerLanguage } from '@/lib/privacy-copy';

export default function PrivacyPage() {
  const lang = useMemo(() => detectConsumerLanguage(), []);
  const t = PRIVACY_COPY[lang];

  return (
    <div className="bg-background flex min-h-svh flex-col items-center px-6 py-12">
      <div className="border-border bg-card w-full max-w-2xl rounded-xl border p-8 shadow-sm">
        <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
          Caseflowy
        </p>
        <h1 className="mt-2 text-2xl font-semibold">{t.title}</h1>
        <p className="text-muted-foreground mt-4 text-sm leading-relaxed">{t.summary}</p>

        <div className="mt-8 space-y-6">
          {t.sections.map((section) => (
            <section key={section.heading}>
              <h2 className="text-sm font-semibold">{section.heading}</h2>
              <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{section.body}</p>
            </section>
          ))}
        </div>

        <div className="mt-8 flex flex-col gap-2 sm:flex-row">
          <Button asChild variant="outline" className="flex-1">
            <Link href="/intake/consent">{t.back}</Link>
          </Button>
          <Button asChild variant="ghost" className="flex-1">
            <Link href="/">{t.home}</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
