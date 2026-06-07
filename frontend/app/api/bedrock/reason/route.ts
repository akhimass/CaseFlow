import { NextResponse } from 'next/server';
import { reason } from '@/lib/qwen';

/** @deprecated Use TrueFoundry gateway via /api/audit + qwen-max */
export async function POST(request: Request) {
  try {
    const body = (await request.json()) as { prompt?: string; context?: string };
    const prompt = body.prompt?.trim();
    if (!prompt) {
      return NextResponse.json({ error: 'prompt is required' }, { status: 400 });
    }
    const result = await reason(prompt, body.context ?? '');
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Gateway reason failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
