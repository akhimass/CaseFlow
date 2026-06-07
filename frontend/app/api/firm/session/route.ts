import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import { FIRM_SESSION_COOKIE, parseFirmSessionCookie } from '@/lib/firm-session';

export const dynamic = 'force-dynamic';

export async function GET() {
  const cookieStore = await cookies();
  const raw = cookieStore.get(FIRM_SESSION_COOKIE)?.value;
  const session = parseFirmSessionCookie(raw);
  if (!session) {
    return NextResponse.json({ session: null }, { status: 401 });
  }
  return NextResponse.json({ session });
}
