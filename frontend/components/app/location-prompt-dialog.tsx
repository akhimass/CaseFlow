'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { getConsentRecord, setConsentRecord } from '@/lib/privacy-token';

const DEFAULT_LOCATION = 'San Francisco, CA';

const COPY = {
  en: {
    title: 'Where did the accident happen?',
    hint: 'We use your city to match you with local participating firms.',
    placeholder: 'San Francisco, CA',
    useLocation: 'Use my location',
    confirm: 'Continue',
    skip: 'Skip — use San Francisco, CA',
    locating: 'Finding location…',
    geoError: 'Could not detect location — enter your city below.',
  },
  es: {
    title: '¿Dónde ocurrió el accidente?',
    hint: 'Usamos su ciudad para conectarle con bufetes locales participantes.',
    placeholder: 'San Francisco, CA',
    useLocation: 'Usar mi ubicación',
    confirm: 'Continuar',
    skip: 'Omitir — usar San Francisco, CA',
    locating: 'Buscando ubicación…',
    geoError: 'No pudimos detectar la ubicación — ingrese su ciudad abajo.',
  },
} as const;

function detectLanguage(): 'en' | 'es' {
  if (typeof navigator === 'undefined') return 'en';
  return navigator.language?.toLowerCase().startsWith('es') ? 'es' : 'en';
}

async function reverseGeocode(lat: number, lon: number): Promise<string | null> {
  try {
    const url = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`;
    const res = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!res.ok) return null;
    const data = (await res.json()) as {
      address?: { city?: string; town?: string; county?: string; state?: string };
    };
    const city = data.address?.city ?? data.address?.town ?? data.address?.county;
    const state = data.address?.state;
    if (city && state) return `${city}, ${state}`;
    if (city) return city;
    return null;
  } catch {
    return null;
  }
}

type Props = {
  open: boolean;
  onConfirmed: () => void;
};

export function LocationPromptDialog({ open, onConfirmed }: Props) {
  const lang = useMemo(() => detectLanguage(), []);
  const t = COPY[lang];
  const [location, setLocation] = useState(DEFAULT_LOCATION);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      setLocation(DEFAULT_LOCATION);
      setError('');
    }
  }, [open]);

  const confirm = useCallback(
    async (valueOverride?: string) => {
      const value = (valueOverride ?? location).trim() || DEFAULT_LOCATION;
      const record = getConsentRecord();
      if (!record) return;
      setBusy(true);
      setConsentRecord({ ...record, caller_location: value });
      try {
        await fetch('/api/cases/consent', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            case_id: record.case_id,
            consent_given_at: record.consent_given_at,
            caller_location: value,
          }),
        });
      } catch {
        // local session still has location for agent metadata
      }
      setBusy(false);
      onConfirmed();
    },
    [location, onConfirmed]
  );

  const useMyLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setError(t.geoError);
      return;
    }
    setBusy(true);
    setError('');
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const label = await reverseGeocode(pos.coords.latitude, pos.coords.longitude);
        if (label) setLocation(label);
        else setError(t.geoError);
        setBusy(false);
      },
      () => {
        setError(t.geoError);
        setBusy(false);
      },
      { timeout: 8000, maximumAge: 60_000 }
    );
  }, [t.geoError]);

  if (!open) return null;

  return (
    <dialog
      open
      className="bg-background/80 fixed inset-0 z-50 flex items-center justify-center p-6 backdrop-blur-sm"
      aria-labelledby="location-prompt-title"
    >
      <div className="border-border bg-card w-full max-w-md rounded-xl border p-6 shadow-lg">
        <h2 id="location-prompt-title" className="text-xl font-semibold">
          {t.title}
        </h2>
        <p className="text-muted-foreground mt-2 text-sm">{t.hint}</p>
        <input
          type="text"
          className="border-input bg-background mt-4 w-full rounded-md border px-3 py-2 text-sm"
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
    </dialog>
  );
}
