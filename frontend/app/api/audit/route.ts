import { NextResponse } from 'next/server';
import { type AuditRecord, getAuditStore } from '@/lib/audit-store';

export const dynamic = 'force-dynamic';

export async function GET() {
  const store = getAuditStore();
  return NextResponse.json({ records: store.list(), metrics: store.metrics() });
}

export async function POST(req: Request) {
  const body = (await req.json()) as AuditRecord;
  if (!body?.event_type) {
    return NextResponse.json({ error: 'event_type required' }, { status: 400 });
  }

  getAuditStore().append(body);
  return NextResponse.json({ ok: true });
}
