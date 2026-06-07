import { NextResponse } from 'next/server';
import { getAuditStore } from '@/lib/audit-store';
import { supabaseAdmin } from '@/lib/supabase';

export const dynamic = 'force-dynamic';

export async function GET(_req: Request, ctx: { params: Promise<{ case_id: string }> }) {
  const { case_id } = await ctx.params;
  let auditCount = 0;

  const admin = supabaseAdmin();
  if (admin) {
    const { count } = await admin
      .from('audit_log')
      .select('*', { count: 'exact', head: true })
      .eq('case_id', case_id);
    auditCount = count ?? 0;
  } else {
    auditCount = getAuditStore()
      .list()
      .filter((r) => r.case_id === case_id).length;
  }

  return NextResponse.json({ case_id, audit_count: auditCount });
}
