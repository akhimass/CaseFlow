import { NextResponse } from 'next/server';
import { checkS3Bucket, s3Configured } from '@/lib/aws-s3';
import { bedrockConfigured } from '@/lib/bedrock';
import { gatewayConfigured } from '@/lib/gateway';

export const revalidate = 0;

export async function GET() {
  const livekit = {
    configured: Boolean(
      process.env.LIVEKIT_URL && process.env.LIVEKIT_API_KEY && process.env.LIVEKIT_API_SECRET
    ),
    url: process.env.LIVEKIT_URL ?? null,
    agentName: process.env.AGENT_NAME ?? null,
  };

  const truefoundry = {
    configured: gatewayConfigured(),
    gatewayUrl: process.env.TRUEFOUNDRY_GATEWAY_URL ?? null,
    bedrockFallback: bedrockConfigured(),
    bedrockModel: process.env.BEDROCK_FALLBACK_MODEL ?? null,
  };

  const supabase = {
    configured: Boolean(
      process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY
    ),
    url: process.env.NEXT_PUBLIC_SUPABASE_URL ?? null,
  };

  const s3Status = s3Configured() ? await checkS3Bucket() : { ok: false, bucket: '', region: '' };
  const aws = {
    configured: s3Configured(),
    reachable: s3Status.ok,
    bucket: s3Status.bucket || process.env.AWS_S3_BUCKET || null,
    region: s3Status.region || process.env.AWS_REGION || null,
  };

  const ok = livekit.configured;

  return NextResponse.json(
    { status: ok ? 'ok' : 'degraded', livekit, truefoundry, supabase, aws },
    { status: ok ? 200 : 503, headers: { 'Cache-Control': 'no-store' } }
  );
}
