import { HeadBucketCommand, PutObjectCommand, S3Client } from '@aws-sdk/client-s3';

const region = () => process.env.AWS_REGION ?? process.env.AWS_DEFAULT_REGION ?? 'us-west-2';
const bucket = () => process.env.AWS_S3_BUCKET ?? 'caseflow-cases-dev';

export type CaseArtifactKind =
  | 'transcript'
  | 'parsed'
  | 'audio'
  | 'match'
  | 'brief'
  | 'audit'
  | 'snapshot';

export function s3Configured(): boolean {
  return Boolean(process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY);
}

function client(): S3Client {
  return new S3Client({
    region: region(),
    credentials: {
      accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
      secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!,
    },
  });
}

export function caseArtifactKey(caseId: string, kind: CaseArtifactKind, name: string): string {
  const base = `${caseId.replace(/^\/+|\/+$/g, '')}/`;
  switch (kind) {
    case 'transcript':
      return `${base}transcript.jsonl`;
    case 'parsed':
      return `${base}parsed/${name}.json`;
    case 'audio':
      return `${base}audio/${name}.wav`;
    case 'match':
      return `${base}match/result.json`;
    case 'brief':
      return `${base}brief/firm_brief.txt`;
    case 'audit':
      return `${base}audit/${name}.json`;
    case 'snapshot':
      return `${base}case/snapshot.json`;
    default:
      return `${base}${name}`;
  }
}

export function caseS3Uri(key: string): string {
  return `s3://${bucket()}/${key}`;
}

export async function checkS3Bucket(): Promise<{ ok: boolean; bucket: string; region: string }> {
  if (!s3Configured()) {
    return { ok: false, bucket: bucket(), region: region() };
  }
  try {
    await client().send(new HeadBucketCommand({ Bucket: bucket() }));
    return { ok: true, bucket: bucket(), region: region() };
  } catch {
    return { ok: false, bucket: bucket(), region: region() };
  }
}

export async function putCaseArtifact(
  caseId: string,
  kind: CaseArtifactKind,
  name: string,
  body: string,
  contentType?: string
): Promise<{ key: string; uri: string }> {
  const key = caseArtifactKey(caseId, kind, name);
  const type =
    contentType ??
    (key.endsWith('.json') || key.endsWith('.jsonl')
      ? 'application/json'
      : key.endsWith('.txt')
        ? 'text/plain; charset=utf-8'
        : 'application/octet-stream');

  await client().send(
    new PutObjectCommand({
      Bucket: bucket(),
      Key: key,
      Body: body,
      ContentType: type,
    })
  );

  return { key, uri: caseS3Uri(key) };
}
