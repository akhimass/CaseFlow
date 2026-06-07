import type { ReactNode } from 'react';
import Link from 'next/link';
import { Wordmark } from '@/components/marketing/logo';
import { Button } from '@/components/ui/button';
import { START_CASE_CTA } from '@/lib/consumer-copy';

export function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="bg-background text-foreground min-h-svh">
      <header className="border-border bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-50 border-b backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3">
          <Link href="/" className="shrink-0" aria-label="Caseflow home">
            <Wordmark />
          </Link>
          <div className="flex items-center gap-2">
            <Button asChild variant="ghost" className="hidden sm:inline-flex">
              <Link href="/firm/login">Log in as Firm</Link>
            </Button>
            <Button asChild>
              <Link href="/intake/consent">{START_CASE_CTA}</Link>
            </Button>
          </div>
        </div>
      </header>

      <main>{children}</main>

      <footer className="border-border border-t">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-6">
          <Link href="/" aria-label="Caseflow home">
            <Wordmark />
          </Link>
          <p className="text-muted-foreground text-sm">
            © 2026 Caseflow · Built at YC Conversational AI Hackathon
          </p>
          <div className="text-muted-foreground flex flex-wrap gap-5 text-sm">
            <Link href="/intake/consent" className="hover:text-foreground">
              Your case
            </Link>
            <Link href="/firm/login" className="hover:text-foreground">
              Dashboard
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
