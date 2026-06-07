"""AWS S3 case artifact storage — async buffered writes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("aws_s3")

REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-west-2"))
BUCKET = os.getenv("AWS_S3_BUCKET", os.getenv("S3_BUCKET_CASES", "caseflow-cases-dev"))
SENSITIVE_BUCKET = os.getenv(
    "AWS_S3_SENSITIVE_BUCKET", os.getenv("S3_BUCKET_SENSITIVE", "caseflow-sensitive")
)
KMS_KEY_ID = os.getenv("AWS_KMS_KEY_ID", "")


def s3_configured() -> bool:
    return bool(
        os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")
    )


def case_prefix(case_id: str) -> str:
    return f"{case_id.strip('/')}/"


def artifact_key(case_id: str, relative_path: str) -> str:
    return f"{case_prefix(case_id)}{relative_path.lstrip('/')}"


def _client():
    import boto3

    return boto3.client(
        "s3",
        region_name=REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def _ensure_bucket_sync() -> None:
    from botocore.exceptions import ClientError

    client = _client()
    try:
        client.head_bucket(Bucket=BUCKET)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in {"404", "NoSuchBucket", "403", "NotFound"}:
            raise
        if REGION == "us-east-1":
            client.create_bucket(Bucket=BUCKET)
        else:
            client.create_bucket(
                Bucket=BUCKET,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        logger.info("Created S3 bucket %s in %s", BUCKET, REGION)


async def ensure_bucket() -> None:
    if not s3_configured():
        return
    await asyncio.to_thread(_ensure_bucket_sync)


async def put_text(case_id: str, relative_path: str, body: str) -> str | None:
    if not s3_configured():
        logger.debug("S3 not configured — skip put %s", relative_path)
        return None
    key = artifact_key(case_id, relative_path)

    def _put() -> str:
        _ensure_bucket_sync()
        _client().put_object(
            Bucket=BUCKET,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType=_content_type(relative_path),
            **_encryption_extra(),
        )
        return key

    try:
        return await asyncio.to_thread(_put)
    except Exception:
        logger.exception("S3 put failed for %s", key)
        return None


async def put_json(case_id: str, relative_path: str, data: Any) -> str | None:
    return await put_text(case_id, relative_path, json.dumps(data, default=str, indent=2))


async def append_transcript_jsonl(case_id: str, lines: list[dict[str, Any]]) -> str | None:
    if not lines:
        return None
    key = artifact_key(case_id, "transcript.jsonl")

    def _append() -> str:
        _ensure_bucket_sync()
        client = _client()
        try:
            obj = client.get_object(Bucket=BUCKET, Key=key)
            existing_local = obj["Body"].read().decode("utf-8")
        except Exception:
            existing_local = ""
        chunk = "".join(json.dumps(line, default=str) + "\n" for line in lines)
        body = (existing_local + chunk).encode("utf-8")
        client.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=body,
            ContentType="application/x-ndjson",
            **_encryption_extra(),
        )
        return key

    try:
        return await asyncio.to_thread(_append)
    except Exception:
        logger.exception("S3 transcript append failed for %s", case_id)
        return None


async def save_parsed_document(
    case_id: str, doc_type: str, parsed: dict[str, Any]
) -> str | None:
    return await put_json(case_id, f"parsed/{doc_type}.json", parsed)


async def save_match_result(case_id: str, result: dict[str, Any]) -> str | None:
    return await put_json(case_id, "match/result.json", result)


async def save_firm_brief(case_id: str, brief: str) -> str | None:
    return await put_text(case_id, "brief/firm_brief.txt", brief)


async def save_consistency_audit(case_id: str, audit: dict[str, Any]) -> str | None:
    return await put_json(case_id, "audit/consistency.json", audit)


async def save_case_snapshot(case_id: str, snapshot: dict[str, Any]) -> str | None:
    return await put_json(case_id, "case/snapshot.json", snapshot)


async def save_intake_structured(case_id: str, data: dict[str, Any]) -> str | None:
    return await put_json(case_id, "intake_structured.json", data)


async def save_verbal_summary(case_id: str, summary: str) -> str | None:
    return await put_text(case_id, "verbal_summary.md", summary)


async def put_bytes(
    case_id: str,
    relative_path: str,
    body: bytes,
    content_type: str = "application/octet-stream",
) -> str | None:
    if not s3_configured():
        return None
    key = artifact_key(case_id, relative_path)

    def _put() -> str:
        _ensure_bucket_sync()
        _client().put_object(
            Bucket=BUCKET,
            Key=key,
            Body=body,
            ContentType=content_type,
            **_encryption_extra(),
        )
        return key

    try:
        return await asyncio.to_thread(_put)
    except Exception:
        logger.exception("S3 binary put failed for %s", key)
        return None


async def save_generated_document(
    case_id: str,
    filename: str,
    markdown: str,
    *,
    pdf_bytes: bytes | None = None,
) -> dict[str, str | None]:
    """Write docs/{filename}.md and optional .pdf to operational bucket."""
    md_key = await put_text(case_id, f"docs/{filename}.md", markdown)
    pdf_key = None
    if pdf_bytes:
        pdf_key = await put_bytes(
            case_id,
            f"docs/{filename}.pdf",
            pdf_bytes,
            content_type="application/pdf",
        )
    return {"md": md_key, "pdf": pdf_key}


def presigned_url(key: str, *, expires_s: int = 86400) -> str | None:
    if not s3_configured() or not key:
        return None
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=expires_s,
        )
    except Exception:
        logger.exception("Presigned URL failed for %s", key)
        return None


async def presigned_url_async(key: str, *, expires_s: int = 86400) -> str | None:
    if not s3_configured() or not key:
        return None

    def _sign() -> str:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=expires_s,
        )

    try:
        return await asyncio.to_thread(_sign)
    except Exception:
        logger.exception("Presigned URL failed for %s", key)
        return None


async def save_document_frame(
    case_id: str, *, turn: int, doc_type: str, image_base64: str
) -> str | None:
    """Raw document images — sensitive bucket only (never operational)."""
    if not s3_configured():
        return None
    raw = image_base64.split(",", 1)[-1]
    key = artifact_key(case_id, f"frames/turn_{turn}_{doc_type}.jpg")

    def _put() -> str:
        import base64

        _ensure_sensitive_bucket_sync()
        _client().put_object(
            Bucket=SENSITIVE_BUCKET,
            Key=key,
            Body=base64.b64decode(raw),
            ContentType="image/jpeg",
            **_encryption_extra(),
        )
        return key

    try:
        return await asyncio.to_thread(_put)
    except Exception:
        logger.exception("Sensitive S3 frame save failed for %s", key)
        return None


def s3_uri(key: str, *, bucket: str | None = None) -> str:
    return f"s3://{bucket or BUCKET}/{key}"


def sensitive_uri(key: str) -> str:
    return f"s3://{SENSITIVE_BUCKET}/{key}"


def _encryption_extra() -> dict[str, str]:
    if KMS_KEY_ID:
        return {
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY_ID,
        }
    return {"ServerSideEncryption": "aws:kms"}


async def put_sensitive_json(case_id: str, relative_path: str, data: Any) -> str | None:
    """Write unredacted payload + mapping to the restricted sensitive bucket."""
    if not s3_configured():
        return None
    key = artifact_key(case_id, relative_path)

    def _put() -> str:
        _ensure_sensitive_bucket_sync()
        body = json.dumps(data, default=str, indent=2).encode("utf-8")
        _client().put_object(
            Bucket=SENSITIVE_BUCKET,
            Key=key,
            Body=body,
            ContentType="application/json",
            **_encryption_extra(),
        )
        return key

    try:
        return await asyncio.to_thread(_put)
    except Exception:
        logger.exception("Sensitive S3 put failed for %s", key)
        return None


async def save_sensitive_case_blob(case_id: str, payload: dict[str, Any]) -> str | None:
    key = await put_sensitive_json(case_id, "sensitive/case_blob.json", payload)
    return sensitive_uri(key) if key else None


def _ensure_sensitive_bucket_sync() -> None:
    from botocore.exceptions import ClientError

    client = _client()
    try:
        client.head_bucket(Bucket=SENSITIVE_BUCKET)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in {"404", "NoSuchBucket", "403", "NotFound"}:
            raise
        if REGION == "us-east-1":
            client.create_bucket(Bucket=SENSITIVE_BUCKET)
        else:
            client.create_bucket(
                Bucket=SENSITIVE_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        logger.info("Created sensitive S3 bucket %s in %s", SENSITIVE_BUCKET, REGION)


async def delete_case_prefix(case_id: str, *, bucket: str) -> int:
    """Delete all objects under case_id/ in bucket. Returns deleted count."""
    if not s3_configured():
        return 0
    prefix = case_prefix(case_id)

    def _delete() -> int:
        client = _client()
        deleted = 0
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            resp = client.list_objects_v2(**kwargs)
            contents = resp.get("Contents") or []
            if not contents:
                break
            client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in contents]},
            )
            deleted += len(contents)
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return deleted

    try:
        return await asyncio.to_thread(_delete)
    except Exception:
        logger.exception("S3 delete failed for %s in %s", case_id, bucket)
        return 0


def _content_type(path: str) -> str:
    if path.endswith(".json") or path.endswith(".jsonl"):
        return "application/json"
    if path.endswith(".txt") or path.endswith(".md"):
        return "text/plain; charset=utf-8"
    if path.endswith(".pdf"):
        return "application/pdf"
    if path.endswith(".wav"):
        return "audio/wav"
    return "application/octet-stream"


class S3TranscriptBuffer:
    """Buffer transcript lines; flush to S3 every N seconds (non-blocking)."""

    def __init__(self, case_id: str, flush_interval_s: float = 5.0) -> None:
        self.case_id = case_id
        self.flush_interval_s = flush_interval_s
        self._lines: list[dict[str, Any]] = []
        self._last_flush = datetime.now(timezone.utc).timestamp()
        self.last_key: str | None = None

    def add(self, speaker: str, text: str, language: str = "en", turn: int = 0) -> None:
        self._lines.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "speaker": speaker,
                "text": text,
                "language": language,
                "turn": turn,
            }
        )

    async def maybe_flush(self) -> str | None:
        now = datetime.now(timezone.utc).timestamp()
        if now - self._last_flush < self.flush_interval_s:
            return self.last_key
        return await self.flush()

    async def flush(self) -> str | None:
        if not self._lines:
            return self.last_key
        batch = self._lines
        self._lines = []
        self._last_flush = datetime.now(timezone.utc).timestamp()
        self.last_key = await append_transcript_jsonl(self.case_id, batch)
        return self.last_key
