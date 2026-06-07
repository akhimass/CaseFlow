'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { CONSENT_COPY, detectConsumerLanguage } from '@/lib/privacy-copy';
import { setConsentRecord } from '@/lib/privacy-token';

export default function ConsentPage() {
  const router = useRouter();
  const lang = useMemo(() => detectConsumerLanguage(), []);
  const t = CONSENT_COPY[lang];
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onStart() {
    if (!checked) return;
    setBusy(true);
    const caseId = crypto.randomUUID();
    const consent_given_at = new Date().toISOString();
    setConsentRecord({ case_id: caseId, consent_given_at });
    try {
      await fetch('/api/cases/consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_id: caseId, consent_given_at }),
      });
    } catch {
      // consent still stored locally for demo
    }
    router.push('/intake');
  }

  return (
    <div className="bg-background flex min-h-svh flex-col items-center justify-center px-6">
      <div className="border-border bg-card w-full max-w-lg rounded-xl border p-8 shadow-sm">
        <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
          {lang === 'es' ? 'Paso 1 de 2 · Privacidad' : 'Step 1 of 2 · Privacy'}
        </p>
        <h1 className="mt-2 text-2xl font-semibold">{t.title}</h1>
        <p className="text-muted-foreground mt-4 text-sm leading-relaxed">{t.body}</p>
        <p className="text-muted-foreground mt-3 text-xs leading-relaxed">{t.sttNote}</p>
        <p className="mt-4 text-sm">
          <Link href="/privacy" className="text-primary font-medium underline underline-offset-4">
            {t.privacyLink}
          </Link>
        </p>
        <label className="mt-6 flex cursor-pointer items-start gap-3 text-sm">
          <input
            type="checkbox"
            className="mt-1 size-4 rounded border"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
          />
          <span>
            {lang === 'en' ? (
              <>
                I understand this intake will be recorded and processed under{' '}
                <Link href="/privacy" className="text-primary underline underline-offset-2">
                  Caseflow&apos;s privacy controls
                </Link>
                .
              </>
            ) : (
              <>
                Entiendo que esta intake será grabada y procesada bajo los{' '}
                <Link href="/privacy" className="text-primary underline underline-offset-2">
                  controles de privacidad de Caseflow
                </Link>
                .
              </>
            )}
          </span>
        </label>
        <Button className="mt-6 w-full" size="lg" disabled={!checked || busy} onClick={onStart}>
          {t.start}
        </Button>
        <Button asChild variant="ghost" className="mt-2 w-full" size="sm">
          <Link href="/">{t.back}</Link>
        </Button>
      </div>
    </div>
  );
}
