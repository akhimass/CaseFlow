import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import { getAuditStore } from '@/lib/audit-store';
import { supabaseAdmin } from '@/lib/supabase';

const USER_COOKIE = 'lk_caseflow_user';

export async function POST(req: Request) {
  const body = (await req.json()) as {
    case_id?: string;
    consent_given_at?: string;
    caller_location?: string;
  };
  const caseId = body.case_id?.trim();
  const consentAt = body.consent_given_at?.trim();
  const callerLocation = body.caller_location?.trim();
  if (!caseId || !consentAt) {
    return NextResponse.json({ error: 'case_id and consent_given_at required' }, { status: 400 });
  }

  const cookieStore = await cookies();
  const callerId = cookieStore.get(USER_COOKIE)?.value ?? 'anonymous';

  const admin = supabaseAdmin();
  if (admin) {
    await admin.from('cases').upsert(
      {
        id: caseId,
        caller_id: callerId,
        consent_given_at: consentAt,
        caller_location: callerLocation ?? null,
        status: 'consent',
        intake_json: callerLocation ? { location: callerLocation, state: 'CA' } : {},
        pii_redacted: true,
      },
      { onConflict: 'id' }
    );
    await admin.from('audit_log').insert({
      case_id: caseId,
      event_type: 'consent_given',
      actor: 'caller',
      payload: { consent_given_at: consentAt, caller_location: callerLocation ?? null },
    });
  }

  getAuditStore().append({
    audit_id: crypto.randomUUID(),
    event_type: 'consent_given',
    case_id: caseId,
    caller_id: callerId,
    timestamp: Date.now() / 1000,
    payload: { consent_given_at: consentAt },
  });

  return NextResponse.json({ ok: true, case_id: caseId });
}
