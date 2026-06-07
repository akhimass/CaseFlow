'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';

type DemoFirm = {
  firm_id: string;
  name: string;
  city?: string;
  demo_email?: string;
};

export default function FirmLoginPage() {
  const router = useRouter();
  const [firms, setFirms] = useState<DemoFirm[]>([]);
  const [firmId, setFirmId] = useState('');
  const [pin, setPin] = useState('caseflow');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch('/api/firm/firms')
      .then((res) => res.json())
      .then((data) => {
        const list = (data.firms ?? []) as DemoFirm[];
        setFirms(list);
        if (list[0]) setFirmId(list[0].firm_id);
      })
      .catch(() => setError('Could not load demo firms'));
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const res = await fetch('/api/firm/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ firm_id: firmId, pin }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? 'Sign in failed');
        return;
      }
      router.push('/firm');
      router.refresh();
    } catch {
      setError('Sign in failed');
    } finally {
      setBusy(false);
    }
  }

  const selected = firms.find((f) => f.firm_id === firmId);

  return (
    <div className="bg-background flex min-h-svh flex-col items-center justify-center px-6">
      <div className="border-border bg-card w-full max-w-md rounded-xl border p-8 shadow-sm">
        <p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
          Firm dashboard
        </p>
        <h1 className="mt-2 text-2xl font-semibold">Sign in to your firm</h1>
        <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
          Demo sign-in for participating San Francisco law firms. After you sign in, open this
          dashboard in another tab, then run a client intake — matched cases appear here in real
          time.
        </p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <div>
            <label className="text-muted-foreground mb-1 block text-xs font-semibold uppercase">
              Law firm
            </label>
            <select
              className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
              value={firmId}
              onChange={(e) => setFirmId(e.target.value)}
            >
              {firms.map((firm) => (
                <option key={firm.firm_id} value={firm.firm_id}>
                  {firm.name}
                  {firm.city ? ` · ${firm.city}` : ''}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-muted-foreground mb-1 block text-xs font-semibold uppercase">
              Demo PIN
            </label>
            <input
              type="password"
              className="border-input bg-background w-full rounded-md border px-3 py-2 text-sm"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              autoComplete="current-password"
            />
            {selected?.demo_email ? (
              <p className="text-muted-foreground mt-1 text-xs">
                Demo account: {selected.demo_email}
              </p>
            ) : null}
          </div>

          {error ? <p className="text-destructive text-sm">{error}</p> : null}

          <Button className="w-full" size="lg" type="submit" disabled={busy || !firmId}>
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        <Button asChild variant="ghost" className="mt-3 w-full" size="sm">
          <Link href="/">Back to home</Link>
        </Button>
      </div>
    </div>
  );
}
