'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FirmSidebarWordmark } from '@/components/marketing/logo';
import { Button } from '@/components/ui/button';
import { type FirmSession } from '@/lib/firm-session';
import { cn } from '@/lib/shadcn/utils';

export type FirmDashboardView = 'home' | 'metrics' | 'cases' | 'firm' | 'overview';

const NAV: { id: FirmDashboardView; label: string; href?: string }[] = [
  { id: 'home', label: 'Home' },
  { id: 'metrics', label: 'Metrics', href: '/admin/metrics' },
  { id: 'cases', label: 'Cases' },
  { id: 'firm', label: 'Firm' },
  { id: 'overview', label: 'Overview' },
];

export function FirmDashboardShell({
  session,
  connected,
  view,
  onViewChange,
  autoBrief,
  onToggleAutoBrief,
  children,
}: {
  session: FirmSession;
  connected: boolean;
  view: FirmDashboardView;
  onViewChange: (view: FirmDashboardView) => void;
  autoBrief: boolean;
  onToggleAutoBrief: () => void;
  children: React.ReactNode;
}) {
  const router = useRouter();

  return (
    <div className="bg-muted/20 flex min-h-svh">
      <aside className="border-border bg-background hidden w-52 shrink-0 flex-col border-r md:flex">
        <div className="border-border border-b px-4 py-4">
          <Link href="/firm" onClick={() => onViewChange('home')} className="block min-w-0">
            <FirmSidebarWordmark />
          </Link>
        </div>
        <nav className="flex flex-1 flex-col gap-0.5 p-3">
          {NAV.map((item) => {
            if (item.href) {
              return (
                <Link
                  key={item.id}
                  href={item.href}
                  className="text-muted-foreground hover:bg-muted/60 rounded-lg px-3 py-2 text-sm font-medium transition-colors"
                >
                  {item.label}
                </Link>
              );
            }
            const active = view === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onViewChange(item.id)}
                className={cn(
                  'rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors',
                  active
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground hover:bg-muted/60'
                )}
              >
                {item.label}
              </button>
            );
          })}
        </nav>
        <div className="border-border space-y-2 border-t p-3">
          <div className="text-muted-foreground flex items-center gap-2 px-1 text-xs">
            <span
              className={cn(
                'size-2 rounded-full',
                connected ? 'animate-pulse bg-emerald-500' : 'bg-amber-500'
              )}
            />
            {connected ? 'Live feed' : 'Reconnecting…'}
          </div>
          <Button
            variant={autoBrief ? 'default' : 'outline'}
            size="sm"
            className="w-full"
            aria-pressed={autoBrief}
            onClick={onToggleAutoBrief}
          >
            {autoBrief ? 'Auto-brief on' : 'Auto-brief off'}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="w-full"
            onClick={async () => {
              await fetch('/api/firm/logout', { method: 'POST' });
              router.replace('/firm/login');
            }}
          >
            Sign out
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-border bg-background border-b md:hidden">
          <div className="flex items-center justify-between gap-3 px-4 py-3">
            <FirmSidebarWordmark />
            <span className="text-muted-foreground truncate text-xs">{session.firm_name}</span>
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-3">
            {NAV.filter((item) => !item.href).map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onViewChange(item.id)}
                className={cn(
                  'shrink-0 rounded-full px-3 py-1.5 text-xs font-medium',
                  view === item.id
                    ? 'bg-accent text-accent-foreground'
                    : 'bg-muted text-muted-foreground'
                )}
              >
                {item.label}
              </button>
            ))}
            <Link
              href="/admin/metrics"
              className="bg-muted text-muted-foreground shrink-0 rounded-full px-3 py-1.5 text-xs font-medium"
            >
              Metrics
            </Link>
          </nav>
        </header>
        <main className="flex-1 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
