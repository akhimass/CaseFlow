'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { setConsentRecord } from '@/lib/privacy-token';

function detectLanguage(): 'en' | 'es' {
  if (typeof navigator === 'undefined') return 'en';
  const lang = navigator.language?.toLowerCase() ?? 'en';
  return lang.startsWith('es') ? 'es' : 'en';
}

const COPY = {
  en: {
    title: 'Before we begin',
    body: 'Caseflow records this intake to match you with a participating personal injury firm. We redact names, phone numbers, and addresses before they reach firm dashboards or external AI models. Raw document images are stored in a separate encrypted bucket — never shown on the firm dashboard.',
    checkbox:
      'I understand this intake will be recorded and processed under Caseflow’s privacy controls.',
    locationLabel: 'Where did the accident happen?',
    locationHint: 'City and state — we use this to match you with local participating firms.',
    locationPlaceholder: 'San Francisco, CA',
    start: 'Start intake',
    back: 'Back to home',
    sttNote:
      'Note: live speech audio is not regex-redacted during the call (STT limitation). Production roadmap: on-device redaction.',
  },
  es: {
    title: 'Antes de comenzar',
    body: 'Caseflow registra esta intake para conectarle con un bufete participante. Redactamos nombres, teléfonos y direcciones antes de que lleguen al panel del bufete o a modelos de IA externos. Las imágenes de documentos se guardan en un bucket cifrado aparte — nunca se muestran en el panel.',
    checkbox:
      'Entiendo que esta intake será grabada y procesada bajo los controles de privacidad de Caseflow.',
    locationLabel: '¿Dónde ocurrió el accidente?',
    locationHint: 'Ciudad y estado — lo usamos para conectarle con bufetes locales participantes.',
    locationPlaceholder: 'San Francisco, CA',
    start: 'Iniciar intake',
    back: 'Volver al inicio',
    sttNote:
      'Nota: el audio en vivo no se redacta por regex durante la llamada (limitación de STT). Hoja de ruta: redacción en el dispositivo.',
  },
} as const;

export default function ConsentPage() {
  const router = useRouter();
  const lang = useMemo(() => detectLanguage(), []);
  const t = COPY[lang];
  const [checked, setChecked] = useState(false);
  const [location, setLocation] = useState('San Francisco, CA');
  const [busy, setBusy] = useState(false);

  async function onStart() {
    if (!checked || !location.trim()) return;
    setBusy(true);
    const caseId = crypto.randomUUID();
    const consent_given_at = new Date().toISOString();
    const caller_location = location.trim();
    setConsentRecord({ case_id: caseId, consent_given_at, caller_location });
    try {
      await fetch('/api/cases/consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_id: caseId, consent_given_at, caller_location }),
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
          {lang === 'es' ? 'Privacidad' : 'Privacy'}
        </p>
        <h1 className="mt-2 text-2xl font-semibold">{t.title}</h1>
        <p className="text-muted-foreground mt-4 text-sm leading-relaxed">{t.body}</p>
        <p className="text-muted-foreground mt-3 text-xs leading-relaxed">{t.sttNote}</p>
        <div className="mt-6">
          <label className="text-muted-foreground mb-1 block text-xs font-semibold uppercase">
            {t.locationLabel}
          </label>
          <input
            type="text"
            className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder={t.locationPlaceholder}
            autoComplete="address-level2"
          />
          <p className="text-muted-foreground mt-1 text-xs">{t.locationHint}</p>
        </div>
        <label className="mt-6 flex cursor-pointer items-start gap-3 text-sm">
          <input
            type="checkbox"
            className="mt-1 size-4 rounded border"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
          />
          <span>{t.checkbox}</span>
        </label>
        <Button
          className="mt-6 w-full"
          size="lg"
          disabled={!checked || !location.trim() || busy}
          onClick={onStart}
        >
          {t.start}
        </Button>
        <Button asChild variant="ghost" className="mt-2 w-full" size="sm">
          <Link href="/">{t.back}</Link>
        </Button>
      </div>
    </div>
  );
}
