'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import type { AppConfig } from '@/app-config';
import { App } from '@/components/app/app';
import { getConsentRecord } from '@/lib/privacy-token';

function IntakeLoadingShell() {
  return (
    <div className="bg-background flex min-h-svh items-center justify-center px-6">
      <p className="text-muted-foreground text-sm">Loading intake…</p>
    </div>
  );
}

export function IntakeApp({ appConfig }: { appConfig: AppConfig }) {
  const router = useRouter();
  const [consentOk, setConsentOk] = useState<boolean | null>(null);

  useEffect(() => {
    if (!getConsentRecord()) {
      router.replace('/intake/consent');
      return;
    }
    setConsentOk(true);
  }, [router]);

  if (consentOk !== true) {
    return <IntakeLoadingShell />;
  }

  return <App appConfig={appConfig} />;
}
