"""AWS Comprehend Medical — ICD-10-CM coding of ER-discharge text.

Runs the parsed ER-discharge narrative through AWS Comprehend Medical's
``InferICD10CM`` to extract billable ICD-10-CM codes, which refine injury
severity and sharpen the Moss comparable-settlement query (a coded "S13.4XXA
whiplash, moderate" is a stronger retrieval key than free text).

Design mirrors the rest of the stack — a real sponsor call with a deterministic
fallback so the feature always produces value:

* **Primary** — AWS Comprehend Medical ``infer_icd10_cm`` (us-west-2).
* **Fallback** — a curated keyword→ICD-10 map over the same canonical injury
  vocabulary used by the consistency layer, when Comprehend Medical is not
  configured or not subscribed on the account.

Fail-open: never raises into the ingest path; returns a structured result tagged
with its ``source`` so the firm dashboard can show provenance.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

logger = logging.getLogger("comprehend_medical")

# Canonical injury term -> (ICD-10-CM code, description, severity hint). The terms
# match consistency.extract_injury_keywords so AWS and the fallback speak the same
# vocabulary as the rest of the agent.
_ICD10_BY_INJURY: dict[str, tuple[str, str, str]] = {
    "whiplash": (
        "S13.4XXA",
        "Sprain of ligaments of cervical spine, initial encounter",
        "medium",
    ),
    "cervical sprain": (
        "S13.4XXA",
        "Sprain of ligaments of cervical spine, initial encounter",
        "medium",
    ),
    "disc herniation": (
        "M51.26",
        "Intervertebral disc displacement, lumbar region",
        "high",
    ),
    "concussion": (
        "S06.0X0A",
        "Concussion without loss of consciousness, initial encounter",
        "high",
    ),
    "fracture": (
        "T14.8XXA",
        "Other injury (fracture noted), initial encounter",
        "high",
    ),
    "shoulder injury": (
        "S43.40XA",
        "Sprain of unspecified shoulder joint, initial encounter",
        "medium",
    ),
    "back injury": (
        "S39.012A",
        "Strain of muscle, fascia and tendon of lower back, initial encounter",
        "medium",
    ),
    "sprain": ("T14.8XXA", "Sprain, unspecified site, initial encounter", "low"),
    "laceration": (
        "S01.90XA",
        "Laceration, unspecified part of head, initial encounter",
        "low",
    ),
}

# Word-boundary triggers per canonical injury term. Deliberately NOT substring
# matching — "disc" must not fire on "discharged" (every ER discharge says it),
# which would emit a spurious disc-herniation code on every document.
_INJURY_TRIGGERS: dict[str, re.Pattern[str]] = {
    "whiplash": re.compile(r"\b(whiplash|latigazo)\b", re.IGNORECASE),
    "cervical sprain": re.compile(r"\b(cervical|neck|cuello)\b", re.IGNORECASE),
    "disc herniation": re.compile(
        r"\b(disc|disco)\b|\bhernia(t|ted|tion)?\b", re.IGNORECASE
    ),
    "concussion": re.compile(r"\b(concussion|tbi)\b", re.IGNORECASE),
    "fracture": re.compile(r"\b(fracture|fractura|broken)\b", re.IGNORECASE),
    "shoulder injury": re.compile(r"\b(shoulder|hombro)\b", re.IGNORECASE),
    "back injury": re.compile(r"\b(back|lumbar|espalda)\b", re.IGNORECASE),
    "sprain": re.compile(r"\b(sprain|sprained|esguince)\b", re.IGNORECASE),
    "laceration": re.compile(r"\b(laceration|laceraci[oó]n)\b", re.IGNORECASE),
}

_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
_ICD10_SCORE_THRESHOLD = float(os.getenv("COMPREHEND_ICD10_THRESHOLD", "0.4"))


def comprehend_configured() -> bool:
    return bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))


def _comprehend_region() -> str:
    # Comprehend Medical is available in a subset of regions; honor AWS_REGION but
    # fall back to a supported one.
    return os.getenv("COMPREHEND_REGION") or os.getenv("AWS_REGION") or "us-west-2"


def _roll_up_severity(codes: list[dict[str, Any]]) -> str | None:
    ranks = [_SEVERITY_RANK.get(str(c.get("severity") or "").lower(), 0) for c in codes]
    top = max(ranks) if ranks else 0
    for label, rank in _SEVERITY_RANK.items():
        if rank == top:
            return label
    return None


def _injury_terms(text: str) -> list[str]:
    """Canonical injury terms present in text, by word-boundary trigger."""
    return [term for term, pat in _INJURY_TRIGGERS.items() if pat.search(text or "")]


def _severity_for_text(text: str) -> str:
    best = "low"
    for term in _injury_terms(text):
        severity = _ICD10_BY_INJURY[term][2]
        if _SEVERITY_RANK[severity] > _SEVERITY_RANK[best]:
            best = severity
    return best


def local_icd10(text: str) -> list[dict[str, Any]]:
    """Deterministic ICD-10-CM coding from the curated injury map."""
    codes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for term in _injury_terms(text):
        code, description, severity = _ICD10_BY_INJURY[term]
        if code in seen:
            continue
        seen.add(code)
        codes.append(
            {
                "code": code,
                "description": description,
                "text": term,
                "score": 0.75,
                "severity": severity,
            }
        )
    return codes


def _infer_icd10_sync(text: str) -> list[dict[str, Any]]:
    import boto3

    client = boto3.client(
        "comprehendmedical",
        region_name=_comprehend_region(),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
    response = client.infer_icd10_cm(Text=text[:20000])
    codes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entity in response.get("Entities", []):
        concepts = entity.get("ICD10CMConcepts") or []
        if not concepts:
            continue
        top = concepts[0]
        code = str(top.get("Code") or "")
        if (
            not code
            or code in seen
            or float(top.get("Score", 0) or 0) < _ICD10_SCORE_THRESHOLD
        ):
            continue
        seen.add(code)
        entity_text = str(entity.get("Text") or "")
        codes.append(
            {
                "code": code,
                "description": str(top.get("Description") or ""),
                "text": entity_text,
                "score": round(float(top.get("Score", 0) or 0), 3),
                "severity": _severity_for_text(
                    entity_text + " " + str(top.get("Description") or "")
                ),
            }
        )
    return codes


async def extract_icd10_codes(text: str) -> dict[str, Any]:
    """Code ER-discharge text to ICD-10-CM. Returns codes + rolled-up severity.

    ``{"codes": [...], "severity": "low|medium|high"|None, "source": str}``.
    Source is ``comprehend_medical`` when the AWS call succeeds, ``local`` when it
    falls back, or ``none`` when there is no text.
    """
    if not text or not text.strip():
        return {"codes": [], "severity": None, "source": "none"}

    if comprehend_configured():
        try:
            codes = await asyncio.to_thread(_infer_icd10_sync, text)
            if codes:
                return {
                    "codes": codes,
                    "severity": _roll_up_severity(codes),
                    "source": "comprehend_medical",
                }
            # AWS returned no codes — fall through to the curated map.
        except Exception as exc:
            logger.info(
                "Comprehend Medical unavailable, using local map: %s", str(exc)[:160]
            )

    codes = local_icd10(text)
    return {
        "codes": codes,
        "severity": _roll_up_severity(codes),
        "source": "local" if codes else "none",
    }
