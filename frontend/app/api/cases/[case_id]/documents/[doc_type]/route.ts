import { NextResponse } from 'next/server';
import { GetObjectCommand, S3Client } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

export const dynamic = 'force-dynamic';

const REGION = process.env.AWS_REGION ?? process.env.AWS_DEFAULT_REGION ?? 'us-west-2';
const BUCKET = process.env.AWS_S3_BUCKET ?? 'caseflow-cases-dev';

const FILENAMES: Record<string, string> = {
  intake_summary: 'intake_summary',
  demand_letter: 'demand_letter',
  action_sheet: 'action_sheet',
};

function s3() {
  return new S3Client({
    region: REGION,
    credentials: {
      accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
      secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!,
    },
  });
}

export async function GET(
  req: Request,
  ctx: { params: Promise<{ case_id: string; doc_type: string }> }
) {
  const { case_id, doc_type } = await ctx.params;
  const filename = FILENAMES[doc_type];
  if (!filename) {
    return NextResponse.json({ error: 'Unknown document type' }, { status: 400 });
  }

  if (!process.env.AWS_ACCESS_KEY_ID || !process.env.AWS_SECRET_ACCESS_KEY) {
    return NextResponse.json({ error: 'S3 not configured' }, { status: 503 });
  }

  const { searchParams } = new URL(req.url);
  const format = searchParams.get('format') ?? 'pdf';
  const ext = format === 'md' ? 'md' : 'pdf';
  const key = `${case_id.replace(/\/$/, '')}/docs/${filename}.${ext}`;

  if (format === 'pdf') {
    const url = await getSignedUrl(s3(), new GetObjectCommand({ Bucket: BUCKET, Key: key }), {
      expiresIn: 86400,
    });
    return NextResponse.json({ case_id, doc_type, url, key });
  }

  try {
    const obj = await s3().send(new GetObjectCommand({ Bucket: BUCKET, Key: key }));
    const content = await obj.Body?.transformToString('utf-8');
    return NextResponse.json({ case_id, doc_type, content: content ?? '', key });
  } catch {
    return NextResponse.json({ error: 'Document not found' }, { status: 404 });
  }
}
