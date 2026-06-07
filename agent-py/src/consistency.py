"""Consistency layer — Qwen via TrueFoundry gateway, rules + LiveKit Inference fallback."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from gateway import GATEWAY_MODEL, GatewayMetadata, chat, gateway_configured

logger = logging.getLogger("consistency")

CONSISTENCY_MODEL = GATEWAY_MODEL


def _parse_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            parsed = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _rules_check(
    field_name: str,
    verbal_claim: str,
    parsed_value: str,
    language: str = "en",
) -> dict[str, Any]:
    verbal = verbal_claim.lower()
    parsed = parsed_value.lower()
    conflict = False
    reason = ""

    if (
        field_name == "fault_claim"
        and (
            "red light" in verbal
            or "luz roja" in verbal
            or "pasó la luz" in verbal
            or "paso la luz" in verbal
            or "semáforo" in verbal
        )
        and ("undetermined" in parsed or "undetermin" in parsed)
    ):
        conflict = True
        reason = "Caller claims clear fault; police report lists fault as undetermined."

    if not conflict:
        return {
            "conflict": False,
            "clarifying_question": None,
            "reason": None,
            "source": "rules",
        }

    if language.startswith("es"):
        question = (
            "Gracias por explicarme lo que pasó. En el reporte policial aparece que "
            "la culpa quedó sin determinar, aunque usted mencionó que el otro conductor "
            "pasó en rojo. ¿Pudo ver usted directamente que se pasó el semáforo, o lo "
            "supone por cómo ocurrió el choque?"
        )
    else:
        question = (
            "Thank you for explaining what happened. The police report lists fault as "
            "undetermined, though you mentioned the other driver ran the red light. "
            "Did you personally see them run the light, or are you inferring that from "
            "how the crash happened?"
        )

    return {
        "conflict": True,
        "clarifying_question": question,
        "reason": reason,
        "source": "rules",
    }


async def check_consistency(
    field_name: str,
    verbal_claim: str,
    parsed_value: str,
    language: str = "en",
    *,
    case_id: str = "",
    turn: int = 0,
    caller_id: str = "",
    case_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare verbal claims to parsed documents using Qwen (gateway) with rules fallback."""
    metadata = GatewayMetadata(case_id=case_id, turn=turn, caller_id=caller_id)
    lang_label = "Spanish" if language.startswith("es") else "English"

    system = (
        "You are a PI intake consistency auditor. Compare the caller's verbal claim "
        "to parsed document evidence. Return JSON only with keys: conflict (boolean), "
        "conflict_type (string or null), reason (string or null), clarifying_question "
        f"(string or null in {lang_label}, gentle, never accusatory), language (string)."
    )
    user_payload = {
        "field_name": field_name,
        "verbal_claim": verbal_claim,
        "parsed_value": parsed_value,
        "language": language,
        "case_state": case_state or {},
    }

    try:
        response = await chat(
            CONSISTENCY_MODEL,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
            temperature=0.1,
            metadata=metadata,
        )
        parsed = _parse_json_object(response.content)
        if parsed and "conflict" in parsed:
            return {
                "conflict": bool(parsed.get("conflict")),
                "conflict_type": parsed.get("conflict_type"),
                "clarifying_question": parsed.get("clarifying_question"),
                "reason": parsed.get("reason"),
                "language": parsed.get("language", language),
                "source": "gateway",
                "llm_provider": response.provider,
                "llm_model": response.model_id,
                "failover": response.failover,
            }
    except Exception:
        logger.exception("Gateway consistency check failed; using rules fallback")

    return _rules_check(field_name, verbal_claim, parsed_value, language)


# --------------------------------------------------------------------------- #
# Part 5 — Moss-backed consistency layer
#
# Beyond the verbal-vs-document fault check above, the consistency layer cross-
# references the caller's claims against (1) parsed documents, (2) jurisdictional
# law retrieved from Moss, and (3) comparable settlements retrieved from Moss.
# Any conflict with confidence > 0.7 yields a gentle clarifying question in the
# caller's language.
# --------------------------------------------------------------------------- #
CLAIM_CONFIDENCE_THRESHOLD = 0.7

# claim_type values the downstream checks understand.
_FILING_TYPES = {"filing_window", "sol", "statute_of_limitations", "deadline"}
_AMOUNT_TYPES = {"expected_amount", "settlement_expectation", "expectation", "amount"}
_FAULT_TYPES = {"fault", "fault_claim", "liability"}


def _snippet_text(snippet: Any) -> str:
    """Pull display text from a LawSnippet/Settlement dataclass, dict, or str."""
    if isinstance(snippet, str):
        return snippet
    text = getattr(snippet, "text", None)
    if text is None and isinstance(snippet, dict):
        text = snippet.get("text", "")
    return str(text or "")


def _to_years(value: Any) -> int | None:
    """Parse a number of years from a claim value like '5 years' or 'cinco años'."""
    text = str(value).lower()
    words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "uno": 1,
        "un": 1,
        "dos": 2,
        "tres": 3,
        "cuatro": 4,
        "cinco": 5,
        "seis": 6,
    }
    match = re.search(r"(\d+)", text)
    if match:
        return int(match.group(1))
    for word, num in words.items():
        if re.search(rf"\b{word}\b", text):
            return num
    return None


def _to_amount(value: Any) -> int | None:
    """Parse a dollar amount from '$500k', '500,000', 'half a million', etc."""
    text = str(value).lower().replace(",", "").strip()
    match = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*([km])?", text)
    if not match:
        if "million" in text or "millón" in text or "millon" in text:
            return 1_000_000
        return None
    amount = float(match.group(1))
    suffix = match.group(2)
    if suffix == "k":
        amount *= 1_000
    elif suffix == "m" or "million" in text or "millón" in text or "millon" in text:
        amount *= 1_000_000
    return int(amount)


def _settlement_ceiling(comparables: list[Any]) -> int | None:
    """Highest settlement high-end across the comparable set."""
    highs: list[int] = []
    for comp in comparables:
        high = getattr(comp, "amount_high", None)
        if high is None and isinstance(comp, dict):
            high = comp.get("amount_high")
        try:
            if high is not None:
                highs.append(int(high))
        except (TypeError, ValueError):
            continue
    return max(highs) if highs else None


def _rules_extract_claims(utterance: str) -> list[dict[str, Any]]:
    """Heuristic claim extraction used when the gateway is unavailable."""
    text = utterance.lower()
    claims: list[dict[str, Any]] = []

    # Filing-window claim: "I have 5 years to file", "tengo cinco años".
    if any(
        k in text
        for k in ("year", "año", "anos", "file", "demanda", "plazo", "sue", "claim")
    ):
        years = _to_years(text)
        if years and any(
            k in text
            for k in ("file", "demanda", "plazo", "sue", "claim", "year", "año")
        ):
            claims.append(
                {
                    "claim_type": "filing_window",
                    "claim_value": f"{years} years",
                    "confidence": 0.85,
                }
            )

    # Expectation claim: "I expect $500K", "espero 500 mil".
    if any(
        k in text
        for k in ("$", "expect", "espero", "want", "quiero", "settle", "worth", "vale")
    ):
        amount = _to_amount(text)
        if amount and amount >= 1000:
            claims.append(
                {
                    "claim_type": "expected_amount",
                    "claim_value": f"${amount}",
                    "confidence": 0.8,
                }
            )

    # Fault claim: ran the red light / clear fault.
    if any(
        k in text
        for k in (
            "red light",
            "luz roja",
            "pasó la luz",
            "paso la luz",
            "semáforo",
            "ran the",
        )
    ):
        claims.append(
            {
                "claim_type": "fault",
                "claim_value": "other driver clearly at fault",
                "confidence": 0.8,
            }
        )

    return claims


def _parse_json_list(text: str) -> list[Any] | None:
    parsed = _parse_json_object(text)
    if isinstance(parsed, dict):
        for key in ("claims", "items", "results"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
    stripped = text.strip()
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start != -1 and end > start:
        try:
            value = json.loads(stripped[start : end + 1])
            if isinstance(value, list):
                return value
        except json.JSONDecodeError:
            return None
    return None


async def extract_claims(
    utterance: str,
    language: str = "en",
    *,
    case_id: str = "",
    turn: int = 0,
    caller_id: str = "",
) -> list[dict[str, Any]]:
    """Extract structured claims {claim_type, claim_value, confidence} from an utterance.

    Uses Qwen via the TrueFoundry gateway; falls back to heuristics when the
    gateway is not configured or errors.
    """
    if not utterance.strip():
        return []

    if gateway_configured():
        metadata = GatewayMetadata(case_id=case_id, turn=turn, caller_id=caller_id)
        system = (
            "Extract factual claims a personal-injury caller makes. Return JSON only: "
            'a list of objects {"claim_type", "claim_value", "confidence"}. '
            "claim_type is one of: fault, filing_window, expected_amount, injury, "
            "treatment, other. confidence is 0..1. Return [] if there are no claims."
        )
        try:
            response = await chat(
                CONSISTENCY_MODEL,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": utterance},
                ],
                temperature=0.1,
                metadata=metadata,
            )
            items = _parse_json_list(response.content)
            if items is not None:
                claims: list[dict[str, Any]] = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    claims.append(
                        {
                            "claim_type": str(item.get("claim_type", "other")).lower(),
                            "claim_value": str(item.get("claim_value", "")),
                            "confidence": float(item.get("confidence", 0.7) or 0.7),
                        }
                    )
                return claims
        except Exception:
            logger.exception("Gateway claim extraction failed; using rules fallback")

    return _rules_extract_claims(utterance)


def check_against_documents(
    claims: list[dict[str, Any]],
    parsed_docs: dict[str, Any] | None,
    language: str = "en",
) -> dict[str, Any] | None:
    """Flag a fault claim that contradicts the parsed police report."""
    if not parsed_docs:
        return None
    police = parsed_docs.get("police_report") or {}
    determination = str(police.get("fault_determination") or "").lower()
    if "undetermin" not in determination:
        return None
    for claim in claims:
        if (
            claim.get("claim_type") in _FAULT_TYPES
            and claim.get("confidence", 0) >= CLAIM_CONFIDENCE_THRESHOLD
        ):
            result = _rules_check(
                "fault_claim",
                str(claim.get("claim_value", "")) + " red light",
                "fault determination: undetermined",
                language,
            )
            if result.get("conflict"):
                result["conflict_type"] = "verbal_vs_document"
                result["confidence"] = 0.85
                return result
    return None


def check_against_state_law(
    claims: list[dict[str, Any]],
    law_snippets: list[Any],
    language: str = "en",
    state: str = "",
) -> dict[str, Any] | None:
    """Flag a filing-window claim that exceeds the jurisdiction's actual SoL."""
    text = " ".join(_snippet_text(s) for s in law_snippets).lower()
    if not text:
        return None
    sol_match = re.search(r"(\d+)\s*year", text)
    if not sol_match:
        return None
    law_years = int(sol_match.group(1))

    for claim in claims:
        if claim.get("claim_type") not in _FILING_TYPES:
            continue
        claimed = _to_years(claim.get("claim_value"))
        if claimed and claimed > law_years:
            confidence = float(claim.get("confidence", 0.8) or 0.8)
            state_label = (state or "your state").upper() if state else "your state"
            if language.startswith("es"):
                question = (
                    f"Solo para asegurarnos de no perder ningún plazo importante — en "
                    f"{state_label} la ventana para presentar un caso como el suyo suele "
                    f"ser de unos {law_years} años, no {claimed}. Quiero que actuemos a "
                    f"tiempo. ¿Coincide eso con lo que usted tenía entendido?"
                )
            else:
                question = (
                    f"Just so we don't miss any important deadline — in {state_label} the "
                    f"window to file a case like yours is usually about {law_years} years, "
                    f"not {claimed}. I want to make sure we act in time. Does that match "
                    f"what you understood?"
                )
            return {
                "conflict": True,
                "conflict_type": "claim_vs_state_law",
                "clarifying_question": question,
                "reason": (
                    f"Caller believes the filing window is {claimed} years; retrieved law "
                    f"indicates {law_years} years."
                ),
                "confidence": confidence,
                "language": language,
                "source": "moss_state_law",
            }
    return None


def check_against_comparables(
    claims: list[dict[str, Any]],
    comparables: list[Any],
    language: str = "en",
    *,
    over_factor: float = 2.0,
) -> dict[str, Any] | None:
    """Flag a settlement expectation far above the comparable ceiling."""
    ceiling = _settlement_ceiling(comparables)
    if not ceiling:
        return None
    for claim in claims:
        if claim.get("claim_type") not in _AMOUNT_TYPES:
            continue
        expected = _to_amount(claim.get("claim_value"))
        if expected and expected > ceiling * over_factor:
            confidence = float(claim.get("confidence", 0.8) or 0.8)
            if language.startswith("es"):
                question = (
                    "No puedo prometerle ninguna cantidad, pero casos parecidos al suyo "
                    f"se han resuelto bastante por debajo de ${expected:,}. Prefiero que "
                    "tengamos expectativas realistas desde ahora. ¿Le ayudaría si le "
                    "explico cómo se resolvieron casos comparables?"
                )
            else:
                question = (
                    "I can't promise any amount, but cases similar to yours have generally "
                    f"resolved well below ${expected:,}. I'd rather set realistic "
                    "expectations now. Would it help if I walk you through what comparable "
                    "cases looked like?"
                )
            return {
                "conflict": True,
                "conflict_type": "expectation_vs_comparables",
                "clarifying_question": question,
                "reason": (
                    f"Caller expects ${expected:,}; comparable settlements top out near "
                    f"${ceiling:,}."
                ),
                "confidence": confidence,
                "language": language,
                "source": "moss_comparables",
            }
    return None


async def audit_utterance(
    utterance: str,
    *,
    language: str = "en",
    parsed_docs: dict[str, Any] | None = None,
    law_snippets: list[Any] | None = None,
    comparables: list[Any] | None = None,
    state: str = "",
    case_id: str = "",
    turn: int = 0,
    caller_id: str = "",
) -> dict[str, Any]:
    """Full consistency pass: extract claims, then check docs, law, and comparables.

    Returns the first conflict found with confidence > 0.7, or a no-conflict result.
    """
    claims = await extract_claims(
        utterance, language, case_id=case_id, turn=turn, caller_id=caller_id
    )

    for check in (
        lambda: check_against_documents(claims, parsed_docs, language),
        lambda: check_against_state_law(claims, law_snippets or [], language, state),
        lambda: check_against_comparables(claims, comparables or [], language),
    ):
        conflict = check()
        if conflict and conflict.get("confidence", 0) > CLAIM_CONFIDENCE_THRESHOLD:
            conflict["claims"] = claims
            return conflict

    return {
        "conflict": False,
        "conflict_type": None,
        "clarifying_question": None,
        "reason": None,
        "confidence": 0.0,
        "language": language,
        "source": "audit",
        "claims": claims,
    }
