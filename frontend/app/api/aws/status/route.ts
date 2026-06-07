import { NextResponse } from 'next/server';
import { checkS3Bucket, s3Configured } from '@/lib/aws-s3';

export const dynamic = 'force-dynamic';

export async function GET() {
  const configured = s3Configured();
  const status = configured ? await checkS3Bucket() : { ok: false, bucket: '', region: '' };

  return NextResponse.json({
    configured,
    reachable: status.ok,
    bucket: status.bucket,
    region: status.region,
  });
}
