'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import type { AppConfig } from '@/app-config';
import { App } from '@/components/app/app';
import { getConsentRecord } from '@/lib/privacy-token';

export function IntakeApp({ appConfig }: { appConfig: AppConfig }) {
  const router = useRouter();

  useEffect(() => {
    if (!getConsentRecord()) {
      router.replace('/intake/consent');
    }
  }, [router]);

  return <App appConfig={appConfig} />;
}
