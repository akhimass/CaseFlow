'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import type { AppConfig } from '@/app-config';
import { App } from '@/components/app/app';
import { LocationPromptDialog } from '@/components/app/location-prompt-dialog';
import { getConsentRecord, hasCallerLocation } from '@/lib/privacy-token';

export function IntakeApp({ appConfig }: { appConfig: AppConfig }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [showLocation, setShowLocation] = useState(false);

  useEffect(() => {
    if (!getConsentRecord()) {
      router.replace('/intake/consent');
      return;
    }
    if (hasCallerLocation()) {
      setReady(true);
    } else {
      setShowLocation(true);
    }
  }, [router]);

  if (!ready) {
    return (
      <LocationPromptDialog
        open={showLocation}
        onConfirmed={() => {
          setShowLocation(false);
          setReady(true);
        }}
      />
    );
  }

  return <App appConfig={appConfig} />;
}
