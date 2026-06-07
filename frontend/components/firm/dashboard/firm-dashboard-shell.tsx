'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FirmSidebarWordmark } from '@/components/marketing/logo';
import { Button } from '@/components/ui/button';
import { type FirmSession } from '@/lib/firm-session';
import { cn } from '@/lib/shadcn/utils';

export type FirmDashboardView = 'home' | 'metrics' | 'firm' | 'overview';

const NAV: { id: FirmDashboardView; label: string }[] = [
  { id: 'home', label: 'Home' },
  { id: 'metrics', label: 'Metrics' },
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
      <aside className="border-border bg-background hidden w-56 shrink-0 flex-col border-r md:flex">
        <div className="border-border border-b px-4 py-4">
          <Link href="/firm" onClick={() => onViewChange('home')} className="block min-w-0">
            <FirmSidebarWordmark />
          </Link>
          <div className="bg-muted/50 mt-3 rounded-lg px-2.5 py-2">
            <p className="text-muted-foreground text-[10px] font-semibold tracking-wide uppercase">
              Your firm
            </p>
            <p className="mt-0.5 truncate text-xs font-semibold">{session.firm_name}</p>
            {session.city ? (
              <p className="text-muted-foreground mt-0.5 truncate text-[10px]">{session.city}</p>
            ) : null}
          </div>
        </div>
        <nav className="flex flex-col gap-0.5 p-3">
          {NAV.map((item) => {
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
        <div className="border-border mt-auto space-y-2 border-t p-3">
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
            {NAV.map((item) => (
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
          </nav>
        </header>
        <main className="flex-1 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
