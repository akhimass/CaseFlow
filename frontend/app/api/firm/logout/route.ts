import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import { FIRM_SESSION_COOKIE } from '@/lib/firm-session';

export async function POST() {
  const cookieStore = await cookies();
  cookieStore.delete(FIRM_SESSION_COOKIE);
  return NextResponse.json({ ok: true });
}
