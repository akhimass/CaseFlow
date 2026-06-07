import { headers } from 'next/headers';
import { IntakeApp } from '@/components/app/intake-app';
import { getAppConfig } from '@/lib/utils';

export default async function IntakePage() {
  const hdrs = await headers();
  const appConfig = await getAppConfig(hdrs);

  return <IntakeApp appConfig={appConfig} />;
}
