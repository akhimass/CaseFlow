'use client';

import { useCallback, useMemo, useState } from 'react';
import { MapPinIcon } from '@phosphor-icons/react/dist/ssr';
import { Button } from '@/components/ui/button';
import { getConsentRecord, setConsentRecord } from '@/lib/privacy-token';

const DEFAULT_LOCATION = 'San Francisco, CA';

const COPY = {
  en: {
    eyebrow: 'Step 2 of 2',
    title: 'Where are you located?',
    hint: 'We use your location to connect you with nearby participating firms. You can tell the agent where the accident happened during your consult.',
    placeholder: 'San Francisco, CA',
    useLocation: 'Use my location',
    confirm: 'Continue to intake',
    skip: 'Skip — use San Francisco, CA',
    locating: 'Finding location…',
    geoError: 'Could not detect location — enter your city below.',
    geoDenied: 'Location permission was blocked — enter your city below.',
    geoTimeout: 'Location is taking too long — enter your city below.',
    geoInsecure: 'Location needs a secure (https) connection — enter your city below.',
    disclaimer:
      'Caseflowy is not a law firm and does not provide legal advice. Your conversation helps match you with a participating personal injury firm.',
  },
  es: {
    eyebrow: 'Paso 2 de 2',
    title: '¿Dónde se encuentra?',
    hint: 'Usamos su ubicación para conectarle con bufetes participantes cercanos. Puede decirle al asistente dónde ocurrió el accidente durante su consulta.',
    placeholder: 'San Francisco, CA',
    useLocation: 'Usar mi ubicación',
    confirm: 'Continuar con la consulta',
    skip: 'Omitir — usar San Francisco, CA',
    locating: 'Buscando ubicación…',
    geoError: 'No pudimos detectar la ubicación — ingrese su ciudad abajo.',
    geoDenied: 'Se bloqueó el permiso de ubicación — ingrese su ciudad abajo.',
    geoTimeout: 'La ubicación está tardando demasiado — ingrese su ciudad abajo.',
    geoInsecure: 'La ubicación requiere una conexión segura (https) — ingrese su ciudad abajo.',
    disclaimer:
      'Caseflowy no es un bufete y no ofrece asesoría legal. Su conversación ayuda a conectarle con un bufete participante.',
  },
} as const;

function detectLanguage(): 'en' | 'es' {
  if (typeof navigator === 'undefined') return 'en';
  return navigator.language?.toLowerCase().startsWith('es') ? 'es' : 'en';
}

async function reverseGeocode(lat: number, lon: number): Promise<string | null> {
  try {
    const res = await fetch(`/api/geocode/reverse?lat=${lat}&lon=${lon}`, {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { label?: string | null };
    return data.label ?? null;
  } catch {
    return null;
  }
}

async function ipGeocode(): Promise<string | null> {
  try {
    const res = await fetch('/api/geocode/ip', { headers: { Accept: 'application/json' } });
    if (!res.ok) return null;
    const data = (await res.json()) as { label?: string | null };
    return data.label ?? null;
  } catch {
    return null;
  }
}

type Props = {
  onConfirmed: () => void;
};

export function LocationPromptPanel({ onConfirmed }: Props) {
  const lang = useMemo(() => detectLanguage(), []);
  const t = COPY[lang];
  const [location, setLocation] = useState(DEFAULT_LOCATION);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const confirm = useCallback(
    async (valueOverride?: string) => {
      const value = (valueOverride ?? location).trim() || DEFAULT_LOCATION;
      setBusy(true);
      try {
        const record = getConsentRecord();
        if (record) {
          setConsentRecord({ ...record, caller_location: value });
          await fetch('/api/cases/consent', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              case_id: record.case_id,
              consent_given_at: record.consent_given_at,
              caller_location: value,
            }),
          });
        }
      } catch {
        // local session still has location for agent metadata
      } finally {
        setBusy(false);
      }
      onConfirmed();
    },
    [location, onConfirmed]
  );

  // Last-resort IP lookup when browser GPS is blocked/slow/unavailable. Returns
  // true if it resolved + confirmed a city, false otherwise.
  const tryIpFallback = useCallback(async (): Promise<boolean> => {
    const label = await ipGeocode();
    if (label) {
      setLocation(label);
      await confirm(label);
      return true;
    }
    return false;
  }, [confirm]);

  const useMyLocation = useCallback(() => {
    setBusy(true);
    setError('');

    const fallback = async (message: string) => {
      if (await tryIpFallback()) return;
      setError(message);
      setBusy(false);
    };

    // Geolocation only works in a secure context (https or localhost); if it's
    // missing entirely, go straight to the IP-based fallback.
    const insecure = typeof window !== 'undefined' && !window.isSecureContext;
    if (insecure || !navigator.geolocation) {
      void fallback(insecure ? t.geoInsecure : t.geoError);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const label = await reverseGeocode(pos.coords.latitude, pos.coords.longitude);
        if (label) {
          setLocation(label);
          await confirm(label);
        } else {
          await fallback(t.geoError);
        }
      },
      (err) => {
        const message =
          err.code === err.PERMISSION_DENIED
            ? t.geoDenied
            : err.code === err.TIMEOUT
              ? t.geoTimeout
              : t.geoError;
        void fallback(message);
      },
      { timeout: 8000, maximumAge: 60_000 }
    );
  }, [confirm, tryIpFallback, t.geoError, t.geoDenied, t.geoTimeout, t.geoInsecure]);

  return (
    <section className="flex w-full flex-col items-center justify-center px-6 py-6 text-center">
      <div className="border-border bg-card w-full max-w-lg rounded-xl border p-8 text-left shadow-sm">
        <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
          {t.eyebrow}
        </p>
        <div className="mt-3 flex items-start gap-3">
          <div className="bg-primary/10 text-primary flex size-10 shrink-0 items-center justify-center rounded-full">
            <MapPinIcon className="size-5" weight="duotone" />
          </div>
          <div>
            <h1 className="text-xl font-semibold">{t.title}</h1>
            <p className="text-muted-foreground mt-1 text-sm leading-relaxed">{t.hint}</p>
          </div>
        </div>

        <input
          type="text"
          className="border-input bg-background mt-6 w-full rounded-md border px-3 py-2.5 text-sm"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder={t.placeholder}
          autoComplete="address-level2"
        />
        {error ? <p className="text-destructive mt-2 text-xs">{error}</p> : null}

        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <Button type="button" variant="outline" disabled={busy} onClick={useMyLocation}>
            {busy ? t.locating : t.useLocation}
          </Button>
          <Button
            type="button"
            className="flex-1"
            disabled={busy || !location.trim()}
            onClick={() => confirm()}
          >
            {t.confirm}
          </Button>
        </div>
        <Button
          type="button"
          variant="ghost"
          className="mt-2 w-full"
          size="sm"
          disabled={busy}
          onClick={() => confirm(DEFAULT_LOCATION)}
        >
          {t.skip}
        </Button>
      </div>

      <p className="text-muted-foreground mt-8 max-w-prose text-xs leading-5">{t.disclaimer}</p>
    </section>
  );
}
