import { NextResponse } from 'next/server';
import { createHmac, timingSafeEqual } from 'node:crypto';
import { DeleteObjectsCommand, ListObjectsV2Command, S3Client } from '@aws-sdk/client-s3';
import { getAuditStore } from '@/lib/audit-store';
import { getCaseStore } from '@/lib/case-store';
import { supabaseAdmin } from '@/lib/supabase';

export const dynamic = 'force-dynamic';

const REGION = process.env.AWS_REGION ?? process.env.AWS_DEFAULT_REGION ?? 'us-west-2';
const BUCKET = process.env.AWS_S3_BUCKET ?? 'caseflow-cases-dev';
const SENSITIVE_BUCKET = process.env.AWS_S3_SENSITIVE_BUCKET ?? 'caseflow-sensitive';
const DELETE_SECRET = process.env.CASEFLOW_DELETE_HMAC_SECRET ?? 'caseflow-demo-delete';

function verifySignature(caseId: string, signature: string | null): boolean {
  if (!signature) return false;
  const expected = createHmac('sha256', DELETE_SECRET).update(caseId).digest('hex');
  try {
    return timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
  } catch {
    return false;
  }
}

async function purgeS3Prefix(client: S3Client, bucket: string, caseId: string) {
  const prefix = `${caseId.replace(/\/$/, '')}/`;
  let deleted = 0;
  let token: string | undefined;
  do {
    const listed = await client.send(
      new ListObjectsV2Command({ Bucket: bucket, Prefix: prefix, ContinuationToken: token })
    );
    const keys = (listed.Contents ?? []).map((o) => ({ Key: o.Key! }));
    if (keys.length) {
      await client.send(new DeleteObjectsCommand({ Bucket: bucket, Delete: { Objects: keys } }));
      deleted += keys.length;
    }
    token = listed.IsTruncated ? listed.NextContinuationToken : undefined;
  } while (token);
  return deleted;
}

export async function DELETE(req: Request, ctx: { params: Promise<{ case_id: string }> }) {
  const { case_id } = await ctx.params;
  const signature = req.headers.get('x-caseflow-signature');
  if (!verifySignature(case_id, signature)) {
    return NextResponse.json(
      {
        error: 'Invalid signature',
        hint: `curl -X DELETE -H "X-Caseflow-Signature: $(echo -n '${case_id}' | openssl dgst -sha256 -hmac '$CASEFLOW_DELETE_HMAC_SECRET' | awk '{{print $2}}')" http://localhost:3000/api/cases/${case_id}`,
      },
      { status: 401 }
    );
  }

  const admin = supabaseAdmin();
  if (admin) {
    await admin.from('audit_log').delete().eq('case_id', case_id);
    await admin.from('documents').delete().eq('case_id', case_id);
    await admin.from('matches').delete().eq('case_id', case_id);
    await admin.from('cases').delete().eq('id', case_id);
  }

  let s3Deleted = 0;
  if (process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY) {
    const client = new S3Client({
      region: REGION,
      credentials: {
        accessKeyId: process.env.AWS_ACCESS_KEY_ID,
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
      },
    });
    s3Deleted += await purgeS3Prefix(client, BUCKET, case_id);
    s3Deleted += await purgeS3Prefix(client, SENSITIVE_BUCKET, case_id);
  }

  getCaseStore().remove(case_id);
  getAuditStore().append({
    audit_id: crypto.randomUUID(),
    event_type: 'data_purge',
    case_id,
    actor: 'delete_endpoint',
    timestamp: Date.now() / 1000,
    payload: { s3_objects_deleted: s3Deleted },
  });

  return NextResponse.json({
    ok: true,
    case_id,
    purged: { supabase: Boolean(admin), s3_objects: s3Deleted },
  });
}
