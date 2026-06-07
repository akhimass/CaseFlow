import { NextResponse } from 'next/server';
import { getCaseStore } from '@/lib/case-store';

export const dynamic = 'force-dynamic';

export async function GET() {
  const store = getCaseStore();
  return NextResponse.json({ cases: store.list() });
}

export async function POST(req: Request) {
  const body = await req.json();
  const case_id = body?.case_id;
  const event = body?.event;
  const payload = body?.payload;

  if (!case_id || !event || !payload) {
    return NextResponse.json({ error: 'Missing case_id, event, or payload' }, { status: 400 });
  }

  const store = getCaseStore();
  const update = {
    case_id,
    event,
    payload: { ...payload, updated_at: Date.now() },
    timestamp: Date.now(),
  };
  store.upsert(update);

  return NextResponse.json({ ok: true });
}
