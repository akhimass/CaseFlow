import { NextResponse } from 'next/server';
import { getAuditStore } from '@/lib/audit-store';
import { supabaseAdmin } from '@/lib/supabase';

export async function POST(_req: Request, ctx: { params: Promise<{ case_id: string }> }) {
  const { case_id } = await ctx.params;

  const record = {
    audit_id: crypto.randomUUID(),
    event_type: 'firm_reveal_requested',
    case_id,
    actor: 'firm_dashboard_demo',
    timestamp: Date.now() / 1000,
    payload: {
      note: 'Demo reveal — no firm auth. Production requires authenticated firm users.',
    },
  };

  getAuditStore().append(record);

  const admin = supabaseAdmin();
  if (admin) {
    await admin.from('audit_log').insert({
      case_id,
      event_type: 'firm_reveal_requested',
      actor: 'firm_dashboard_demo',
      payload: record.payload,
    });
  }

  return NextResponse.json({
    ok: true,
    message:
      'Reveal logged. In production, authenticated firm users would fetch unredacted data from the sensitive store.',
    sensitive_blob_url: null,
  });
}
