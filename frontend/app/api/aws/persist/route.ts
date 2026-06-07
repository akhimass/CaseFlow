import { NextResponse } from 'next/server';
import { type CaseArtifactKind, putCaseArtifact, s3Configured } from '@/lib/aws-s3';

export const dynamic = 'force-dynamic';

export async function POST(req: Request) {
  if (!s3Configured()) {
    return NextResponse.json({ error: 'AWS S3 is not configured' }, { status: 503 });
  }

  try {
    const body = (await req.json()) as {
      caseId?: string;
      kind?: CaseArtifactKind;
      name?: string;
      content?: string;
      body?: string;
    };

    const caseId = body.caseId?.trim();
    const kind = body.kind;
    const name = body.name ?? 'artifact';
    const payload = body.content ?? body.body ?? '';

    if (!caseId || !kind) {
      return NextResponse.json({ error: 'caseId and kind are required' }, { status: 400 });
    }

    const result = await putCaseArtifact(caseId, kind, name, payload);
    return NextResponse.json({ status: 'ok', ...result });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'S3 persist failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
