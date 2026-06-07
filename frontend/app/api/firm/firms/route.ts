import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabase';

export const dynamic = 'force-dynamic';

export async function GET() {
  const admin = supabaseAdmin();
  if (!admin) {
    return NextResponse.json({ firms: [] });
  }

  const { data, error } = await admin
    .from('firms')
    .select('id, name, city, county, demo_email')
    .not('demo_pin', 'is', null)
    .order('name');

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({
    firms: (data ?? []).map((firm) => ({
      firm_id: firm.id,
      name: firm.name,
      city: firm.city,
      county: firm.county,
      demo_email: firm.demo_email,
    })),
  });
}
