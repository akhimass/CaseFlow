import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import { FIRM_SESSION_COOKIE } from '@/lib/firm-session';
import { supabaseAdmin } from '@/lib/supabase';

const SESSION_MAX_AGE = 60 * 60 * 24 * 7;

export async function POST(req: Request) {
  const body = (await req.json()) as { firm_id?: string; pin?: string };
  const firmId = body.firm_id?.trim();
  const pin = body.pin?.trim();
  if (!firmId || !pin) {
    return NextResponse.json({ error: 'firm_id and pin required' }, { status: 400 });
  }

  const admin = supabaseAdmin();
  if (!admin) {
    return NextResponse.json({ error: 'Supabase not configured' }, { status: 503 });
  }

  const { data: firm, error } = await admin
    .from('firms')
    .select('id, name, city, demo_pin')
    .eq('id', firmId)
    .maybeSingle();

  if (error || !firm) {
    return NextResponse.json({ error: 'Firm not found' }, { status: 404 });
  }
  if (!firm.demo_pin || firm.demo_pin !== pin) {
    return NextResponse.json({ error: 'Invalid PIN' }, { status: 401 });
  }

  const session = {
    firm_id: firm.id,
    firm_name: firm.name,
    city: firm.city ?? undefined,
  };

  const cookieStore = await cookies();
  cookieStore.set(FIRM_SESSION_COOKIE, JSON.stringify(session), {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    maxAge: SESSION_MAX_AGE,
  });

  return NextResponse.json({ ok: true, session });
}
