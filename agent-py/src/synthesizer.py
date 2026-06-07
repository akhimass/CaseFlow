"""Cross-namespace synthesis — the "Caseflow Decision" memo (Part 3).

After the orchestrator fans out all four Moss streams, :func:`synthesize_decision`
weaves them into one short, citation-grounded paragraph that reads like a senior
paralegal's case memo. It runs through the same TrueFoundry gateway pathway as the
consistency layer (Qwen, low temperature), and falls back to a deterministic
template so the Decision card always populates even if the LLM is unavailable.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from citations import CITE_RE
from gateway import GATEWAY_MODEL, GatewayMetadata, chat, gateway_configured

logger = logging.getLogger("synthesizer")

SYNTHESIS_MODEL = GATEWAY_MODEL
MAX_TOKENS = 250  # hard budget; we truncate to stay under it

SYSTEM_PROMPT = (
    "You are the Caseflowy synthesis engine. Given the case state and four retrieval "
    "streams, write a 3-5 sentence synthesis in the caller's language that:\n"
    "1. Names the strongest applicable state law fact and cites its ID\n"
    "2. References the comparable settlement range and cites the closest match's ID\n"
    "3. Names the top-matched firm and explains why in one clause, citing the firm ID\n"
    "4. Mentions one procedural action the caller should take, citing the procedure ID\n"
    "Use the same [cite:<id>] format as the conversational agent. Be specific. Don't "
    "hedge. The synthesis appears on the firm dashboard as a 'Caseflowy Decision' "
    "summary card — it should read like a senior paralegal's case memo, not a chatbot."
)


@dataclass
class CaseflowDecision:
    synthesis: str
    confidence: int
    language: str
    citations: list[str] = field(default_factory=list)
    source: str = "gateway"  # gateway | fallback | error
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "synthesis": self.synthesis,
            "confidence": self.confidence,
            "language": self.language,
            "citations": self.citations,
            "source": self.source,
            "model": self.model,
        }


def _get(row: Any, attr: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(attr, default)
    return getattr(row, attr, default)


def _top(retrievals: dict[str, Any], key: str) -> Any | None:
    rows = retrievals.get(key) or []
    return rows[0] if rows else None


def _truncate_tokens(text: str, limit: int = MAX_TOKENS) -> str:
    """Keep the synthesis under the token budget, trimming at a sentence boundary."""
    tokens = text.split()
    if len(tokens) <= limit:
        return text
    clipped = " ".join(tokens[:limit])
    # Prefer to end on the last complete sentence.
    last_stop = max(clipped.rfind("."), clipped.rfind("。"), clipped.rfind("!"))
    return clipped[: last_stop + 1] if last_stop > 40 else clipped


def _confidence(retrievals: dict[str, Any]) -> int:
    """0-100 from stream coverage, firm match quality, and comparables presence."""
    present = [k for k in ("state_law", "comparables", "firms", "procedures") if retrievals.get(k)]
    coverage = len(present) / 4
    firm = _top(retrievals, "firms")
    firm_score = (_get(firm, "score", 0) or 0) / 100 if firm else 0.0
    comparables_present = 1.0 if retrievals.get("comparables") else 0.0
    raw = 0.5 * coverage + 0.3 * firm_score + 0.2 * comparables_present
    return max(0, min(100, round(raw * 100)))


def _context_block(retrievals: dict[str, Any]) -> str:
    """Compact, ID-tagged context the model must cite from."""
    lines: list[str] = []
    law = _top(retrievals, "state_law")
    if law:
        lines.append(
            f"STATE LAW [id={_get(law, 'id')}]: {_get(law, 'citation', '')} — "
            f"{_get(law, 'text', '')}"
        )
    comp = _top(retrievals, "comparables")
    if comp:
        lines.append(
            f"COMPARABLE [id={_get(comp, 'id')}]: {_get(comp, 'jurisdiction', '')} "
            f"{_get(comp, 'accident_type', '')}, {_get(comp, 'severity', '')} severity, "
            f"${_get(comp, 'amount_low', 0):,}-${_get(comp, 'amount_high', 0):,}"
        )
    firm = _top(retrievals, "firms")
    if firm:
        reasons = _get(firm, "match_reasons", []) or []
        lines.append(
            f"TOP FIRM [id={_get(firm, 'id')}]: {_get(firm, 'name', '')} "
            f"(score {_get(firm, 'score', 0)}) — {'; '.join(reasons)}"
        )
    proc = _top(retrievals, "procedures")
    if proc:
        lines.append(
            f"PROCEDURE [id={_get(proc, 'id')}]: "
            f"{str(_get(proc, 'scenario', '')).replace('_', ' ')} — {_get(proc, 'text', '')}"
        )
    return "\n".join(lines)


def _fallback(retrievals: dict[str, Any], language: str, state: str) -> str:
    """Deterministic memo so the Decision card always renders."""
    law = _top(retrievals, "state_law")
    comp = _top(retrievals, "comparables")
    firm = _top(retrievals, "firms")
    proc = _top(retrievals, "procedures")
    es = language.startswith("es")
    parts: list[str] = []

    if law:
        cite = _get(law, "citation", "") or "la ley estatal"
        parts.append(
            f"Conforme a {cite}, aplica el plazo de presentación en {state} "
            f"[cite:{_get(law, 'id')}]."
            if es
            else f"Under {cite}, the {state} filing window applies [cite:{_get(law, 'id')}]."
        )
    if comp:
        lo, hi = _get(comp, "amount_low", 0), _get(comp, "amount_high", 0)
        parts.append(
            f"Casos comparables se han resuelto entre ${lo:,} y ${hi:,} "
            f"[cite:{_get(comp, 'id')}]."
            if es
            else f"Comparable cases have settled between ${lo:,} and ${hi:,} "
            f"[cite:{_get(comp, 'id')}]."
        )
    if firm:
        reasons = _get(firm, "match_reasons", []) or []
        reason = reasons[0] if reasons else ("buena cobertura" if es else "strong coverage")
        parts.append(
            f"{_get(firm, 'name', '')} es la mejor coincidencia ({reason}) "
            f"[cite:{_get(firm, 'id')}]."
            if es
            else f"{_get(firm, 'name', '')} is the strongest match ({reason}) "
            f"[cite:{_get(firm, 'id')}]."
        )
    if proc:
        scen = str(_get(proc, "scenario", "")).replace("_", " ")
        parts.append(
            f"Próximo paso recomendado: {scen} [cite:{_get(proc, 'id')}]."
            if es
            else f"Recommended next step: {scen} [cite:{_get(proc, 'id')}]."
        )
    return " ".join(parts)


async def synthesize_decision(
    case_state: dict[str, Any],
    retrievals: dict[str, Any],
    language: str = "en",
    *,
    case_id: str = "",
    caller_id: str = "",
) -> CaseflowDecision:
    """Weave the four retrieval streams into one cited Caseflow Decision memo."""
    state = str(case_state.get("state") or "CA").strip().upper()[:2]
    confidence = _confidence(retrievals)
    lang_label = "Spanish" if language.startswith("es") else "English"

    if gateway_configured():
        user = (
            f"Caller language: {lang_label}. Case state: jurisdiction={state}, "
            f"accident_type={case_state.get('accident_type', 'unknown')}, "
            f"severity={case_state.get('severity', 'unknown')}, "
            f"fault={case_state.get('fault', 'unknown')}.\n\n"
            f"Retrieval streams (cite the bracketed ids):\n{_context_block(retrievals)}\n\n"
            f"Write the synthesis in {lang_label}."
        )
        try:
            response = await chat(
                SYNTHESIS_MODEL,
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
                metadata=GatewayMetadata(case_id=case_id, turn=0, caller_id=caller_id),
            )
            text = _truncate_tokens(response.content.strip())
            citations = CITE_RE.findall(text)
            if citations:  # a usable, grounded synthesis
                return CaseflowDecision(
                    synthesis=text,
                    confidence=confidence,
                    language=language,
                    citations=citations,
                    source="gateway",
                    model=getattr(response, "model_id", "") or SYNTHESIS_MODEL,
                )
            logger.warning("synthesis returned no citations; using fallback")
        except Exception:
            logger.exception("gateway synthesis failed; using fallback template")

    text = _truncate_tokens(_fallback(retrievals, language, state))
    return CaseflowDecision(
        synthesis=text,
        confidence=confidence,
        language=language,
        citations=CITE_RE.findall(text),
        source="fallback",
    )


def token_count(text: str) -> int:
    """Whitespace token count — the budget the tests assert against."""
    return len(re.findall(r"\S+", text))
