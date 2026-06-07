import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabase';

/**
 * Lawyer feedback on a Moss source (the learning loop). Stores a helpful /
 * not-helpful vote keyed by the cited source id (namespace:docid). The agent
 * loads aggregated scores at the next call and re-ranks retrieval accordingly.
 */
export async function POST(req: Request) {
  const body = (await req.json()) as {
    source_id?: string;
    namespace?: string;
    helpful?: boolean;
    case_id?: string;
    firm_id?: string;
    note?: string;
  };

  const sourceId = body.source_id?.trim();
  if (!sourceId || typeof body.helpful !== 'boolean') {
    return NextResponse.json({ error: 'source_id and helpful required' }, { status: 400 });
  }

  const admin = supabaseAdmin();
  if (admin) {
    const { error } = await admin.from('source_feedback').insert({
      source_id: sourceId,
      namespace: body.namespace ?? null,
      helpful: body.helpful,
      case_id: body.case_id ?? null,
      firm_id: body.firm_id ?? null,
      note: body.note ?? null,
    });
    // Table may not exist yet (migration 0007). Degrade gracefully — the loop
    // simply isn't recording until the migration is applied.
    if (error) {
      return NextResponse.json({ ok: false, error: error.message }, { status: 200 });
    }
  }

  return NextResponse.json({ ok: true });
}
