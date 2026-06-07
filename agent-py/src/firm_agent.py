"""Firm-side ambient briefing agent — "Caseflow Counsel".

A male-voiced LiveKit agent for the *firm dashboard*. When a lawyer opens a
matched lead's briefing room, this agent:

1. Hydrates the operational case record (Moss retrievals, the Qwen/MiniMax
   summaries, the consistency audit, firm matches) from the Next.js case store.
2. Narrates the case to the lawyer in clean, ordered segments — broadcasting a
   ``briefing_focus`` event before each segment so the dashboard reveals the
   matching card in sync (Claude-style showcase).
3. Stays in the room to answer the lawyer's follow-up questions, grounded in the
   same Moss indexes the intake agent used.

This persona is dispatched through the existing ``caseflow-agent`` worker: when
``ctx.job.metadata`` carries ``{"mode": "firm_briefing", "case_id": ...}`` the
entrypoint in :mod:`agent` hands off to :func:`run_firm_briefing_session` here
instead of running the Maria-Delgado intake flow.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import textwrap
from typing import Any

import httpx
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    function_tool,
    room_io,
)
from livekit.agents.llm.chat_context import Instructions
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from moss import MossClient

from case_broadcast import broadcast
from gateway import GatewayMetadata
from gateway import chat as gateway_chat
from llm_client import build_dialogue_llm
from minimax_voice import (
    LoggingSTT,
    VoiceSessionState,
    build_caseflow_voice,
)
from pii_redaction import RedactionSession
from privacy_context import bind_redaction_session
from redacting_llm import RedactingLLM
from retrieval import Retriever
from video_capture import parse_data_message

logger = logging.getLogger("agent.firm")

# Reliable, sincere male voice (MiniMax system voice — "Trustworthy Man"). Tuned
# for business narration, which is exactly the register a counsel briefing wants.
FIRM_VOICE_ID = os.getenv("MINIMAX_VOICE_ID_FIRM", "English_Trustworth_Man")
BRIEFING_MODEL = os.getenv(
    "FIRM_BRIEFING_MODEL", os.getenv("GATEWAY_MODEL", "gpt-4.1-mini")
)


FIRM_HOME_INSTRUCTIONS = textwrap.dedent(
    """\
    You are Caseflowy Counsel on the firm's home dashboard — the marketplace
    command center for a personal-injury law firm. You are speaking to an
    attorney who just signed in.

    Your job on the home screen:
    - Welcome them briefly and orient them to the dashboard.
    - Explain that matched leads are in the cases hub on the left; they can
      open any lead for the full dossier or start a voice briefing; your
      conversation transcript is on the right while you speak.
    - If they ask how sources, briefs, or the marketplace work, explain in
      plain terms without naming specific vendors or tools — invite them to ask
      you anything about how we gather sources and case briefs.
    - Answer questions about what to do while waiting for new intakes.
    - Do NOT brief a specific case unless they name one and you have context.
    - Never invent case facts, claimant names, or settlement amounts.

    Voice rules:
    - Plain spoken English. No markdown, bullets, or emojis.
    - Two or three sentences per turn unless they ask for more.
    - Calm, confident colleague tone — never speak to a claimant.
    """
)

FIRM_COUNSEL_INSTRUCTIONS = textwrap.dedent(
    """\
    You are Caseflowy Counsel, the firm-side briefing agent for a personal-injury
    law firm. You are speaking out loud to an attorney who is reviewing a new
    matched lead on their dashboard. Your job is to brief them like a sharp
    paralegal: confident, concise, and useful.

    Voice rules:
    - Plain spoken English. No markdown, no bullet characters, no emojis.
    - Keep answers to two or three sentences unless asked for more.
    - Never read citation markers, IDs, or URLs out loud.
    - Refer to retrieved law and settlements as grounded facts, never promises.

    You have the full case context (intake summary, the consistency audit, Moss
    retrievals, and firm-match reasoning) in your working memory. When the
    attorney asks something you can answer from that context, answer directly.
    When they ask about comparable settlements, jurisdictional law, or other
    firms, call the matching retrieval tool to pull fresh grounded results before
    answering.

    Always speak to the attorney as a trusted colleague — never to the claimant.
    """
)


# --------------------------------------------------------------------------- #
# Case hydration
# --------------------------------------------------------------------------- #
async def fetch_case_record(case_id: str) -> dict[str, Any]:
    """Pull the operational case record from the Next.js case store (SSE source)."""
    base = os.getenv("CASEFLOW_API_URL", "http://localhost:3000").rstrip("/")
    url = f"{base}/api/cases/{case_id}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                record = data.get("case") if isinstance(data, dict) else None
                if isinstance(record, dict):
                    return record
    except Exception:
        logger.exception("Failed to fetch case record for %s", case_id)
    return {"case_id": case_id}


# --------------------------------------------------------------------------- #
# Briefing segment construction
# --------------------------------------------------------------------------- #
def _snippets_for(record: dict[str, Any], namespace: str, limit: int = 3) -> list[str]:
    out: list[str] = []
    for ev in record.get("moss_retrievals") or []:
        if not isinstance(ev, dict) or ev.get("namespace") != namespace:
            continue
        for card in ev.get("snippets") or []:
            text = (card or {}).get("text") if isinstance(card, dict) else None
            if text:
                out.append(str(text))
    # De-dupe, preserve order, cap.
    seen: set[str] = set()
    deduped = [t for t in out if not (t in seen or seen.add(t))]
    return deduped[:limit]


def _case_context(record: dict[str, Any]) -> dict[str, Any]:
    """Compact, LLM-friendly view of the case for briefing generation."""
    matches = record.get("matches")
    matches = matches if isinstance(matches, list) else []
    audit = record.get("consistency_audit")
    audit = audit if isinstance(audit, dict) else {}
    decision = record.get("caseflow_decision")
    decision = decision if isinstance(decision, dict) else {}
    return {
        "caller": record.get("caller_id") or record.get("case_id"),
        "accident_type": record.get("accident_type"),
        "jurisdiction": record.get("state") or record.get("jurisdiction"),
        "location": record.get("caller_location") or record.get("location"),
        "injuries": record.get("injuries"),
        "fault_claim": record.get("fault_claim"),
        "language": record.get("language"),
        "case_strength": record.get("score") or record.get("case_strength"),
        "verbal_summary": record.get("verbal_summary"),
        "firm_brief": record.get("firm_brief"),
        "decision_synthesis": decision.get("synthesis"),
        "consistency": {
            "conflict": audit.get("conflict"),
            "conflict_type": audit.get("conflict_type"),
            "reason": audit.get("reason"),
            "clarifying_question": audit.get("clarifying_question"),
        }
        if audit
        else {},
        "state_law": _snippets_for(record, "state-law"),
        "comparables": _snippets_for(record, "settlements"),
        "procedures": _snippets_for(record, "procedures"),
        "firm_matches": [
            {
                "name": m.get("name"),
                "score": m.get("score"),
                "reasoning": m.get("reasoning"),
            }
            for m in matches
            if isinstance(m, dict)
        ][:3],
    }


# Ordered section blueprint: (section_id, dashboard title, requires-data check).
_SECTION_BLUEPRINT: list[tuple[str, str]] = [
    ("overview", "Case overview"),
    ("discrepancy", "Consistency audit"),
    ("law", "California law"),
    ("comparables", "Comparable settlements"),
    ("recommendation", "Recommended action"),
    ("closing", "Next step"),
]


def _section_available(section: str, ctx: dict[str, Any]) -> bool:
    if section == "overview":
        return True
    if section == "discrepancy":
        c = ctx.get("consistency") or {}
        return bool(c.get("conflict") or c.get("reason"))
    if section == "law":
        return bool(ctx.get("state_law"))
    if section == "comparables":
        return bool(ctx.get("comparables"))
    if section == "recommendation":
        return bool(ctx.get("firm_matches") or ctx.get("firm_brief"))
    return section == "closing"


def _deterministic_segments(ctx: dict[str, Any]) -> list[dict[str, str]]:
    """Template-built narration used when the LLM is unavailable or returns junk."""
    caller = ctx.get("caller") or "this caller"
    acc = (ctx.get("accident_type") or "personal injury").replace("_", " ")
    juris = ctx.get("jurisdiction") or "the listed jurisdiction"
    strength = ctx.get("case_strength")
    injuries = ctx.get("injuries")
    segs: dict[str, str] = {}

    overview = f"New matched lead: {caller}, a {acc} case in {juris}."
    if injuries:
        overview += f" Reported injuries include {injuries}."
    if strength:
        overview += f" Caseflowy scored the case strength at {strength} out of 100."
    segs["overview"] = overview

    c = ctx.get("consistency") or {}
    if c.get("reason") or c.get("conflict"):
        disc = "Heads up — the consistency audit flagged a discrepancy."
        if c.get("reason"):
            disc += f" {c['reason']}"
        if c.get("clarifying_question"):
            disc += f" The agent already asked the claimant to clarify: {c['clarifying_question']}"
        segs["discrepancy"] = disc

    if ctx.get("state_law"):
        segs["law"] = "On the law, " + " ".join(ctx["state_law"][:2])

    if ctx.get("comparables"):
        segs["comparables"] = (
            "For grounding the value, comparable settlements show "
            + " ".join(ctx["comparables"][:2])
        )

    rec_parts: list[str] = []
    if ctx.get("firm_matches"):
        top = ctx["firm_matches"][0]
        rec_parts.append(
            f"This lead was matched to your firm with a fit score of {top.get('score')}."
        )
        if top.get("reasoning"):
            rec_parts.append(str(top["reasoning"]))
    elif ctx.get("firm_brief"):
        rec_parts.append(str(ctx["firm_brief"]))
    if rec_parts:
        segs["recommendation"] = " ".join(rec_parts)

    segs["closing"] = (
        "That's the brief. Ask me anything about the law, comparable outcomes, or "
        "the claimant's account, and I'll pull it up."
    )

    return [
        {"section": s, "title": title, "body": segs[s]}
        for s, title in _SECTION_BLUEPRINT
        if s in segs and segs[s].strip()
    ]


async def generate_briefing_segments(record: dict[str, Any]) -> list[dict[str, str]]:
    """LLM-polished narration with a deterministic fallback.

    Returns an ordered list of ``{section, title, body}`` segments. ``body`` is
    plain spoken text (no markdown, no citation markers).
    """
    ctx = _case_context(record)
    available = [s for s, _ in _SECTION_BLUEPRINT if _section_available(s, ctx)]
    fallback = _deterministic_segments(ctx)

    system = (
        "You are Caseflowy Counsel briefing an attorney out loud about a new "
        "personal-injury lead. Convert the structured case context into a smooth "
        "spoken briefing. Write one to three sentences per requested section. "
        "Plain spoken English only: no markdown, no bullets, no citation markers, "
        "no IDs. Be specific and confident but never promise an outcome."
    )
    user = (
        "Case context (JSON):\n"
        + json.dumps(ctx, ensure_ascii=False, default=str)
        + "\n\nProduce narration for exactly these sections in this order: "
        + ", ".join(available)
        + ".\nReturn ONLY a JSON object shaped like "
        '{"segments":[{"section":"overview","body":"..."}]}. '
        "Use the section ids exactly as given."
    )

    try:
        response = await gateway_chat(
            BRIEFING_MODEL,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            timeout_s=18.0,
            metadata=GatewayMetadata(
                case_id=str(record.get("case_id") or ""),
                firm_id=str(record.get("firm_id") or ""),
                mode="firm_briefing",
            ),
        )
        content = (response.content or "").strip()
        # Tolerate ```json fences.
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            content = content[4:] if content.lower().startswith("json") else content
        parsed = json.loads(content)
        raw_segments = parsed.get("segments") if isinstance(parsed, dict) else None
        if not isinstance(raw_segments, list):
            raise ValueError("missing segments array")

        titles = dict(_SECTION_BLUEPRINT)
        body_by_section: dict[str, str] = {}
        for item in raw_segments:
            if not isinstance(item, dict):
                continue
            section = str(item.get("section") or "").strip()
            body = str(item.get("body") or "").strip()
            if section in titles and body:
                body_by_section[section] = body

        segments = [
            {"section": s, "title": titles[s], "body": body_by_section[s]}
            for s, _ in _SECTION_BLUEPRINT
            if s in body_by_section
        ]
        if segments:
            return segments
        logger.warning("Briefing LLM returned no usable segments; using fallback")
    except Exception:
        logger.exception("Briefing generation failed; using deterministic fallback")

    return fallback


# --------------------------------------------------------------------------- #
# Firm counsel agent
# --------------------------------------------------------------------------- #
class FirmCounselAssistant(Agent):
    """Male-voiced briefing agent with Moss-backed Q&A tools for the firm."""

    def __init__(
        self,
        *,
        room,
        case_id: str,
        record: dict[str, Any],
        redaction_session: RedactionSession,
    ) -> None:
        # Redact PII before it reaches any LLM provider; the streamed reply is
        # un-redacted again so the (authorized) attorney hears real names. Mirrors
        # the intake agent's posture so the firm path is held to the same bar.
        inner_llm = build_dialogue_llm(case_id=case_id)
        super().__init__(
            instructions=_instructions_with_context(record),
            llm=RedactingLLM(inner=inner_llm, session=redaction_session),
        )
        self._room = room
        self._case_id = case_id
        self._record = record
        self._moss = MossClient(
            os.getenv("MOSS_PROJECT_ID"), os.getenv("MOSS_PROJECT_KEY")
        )
        self._moss_cache: dict = {}
        self._retriever = Retriever(
            self._moss, on_result=self._on_moss_result, cache=self._moss_cache
        )

    async def _on_moss_result(self, event: dict) -> None:
        """Append the new retrieval card and broadcast it to the dashboard."""
        retrievals = self._record.get("moss_retrievals")
        if not isinstance(retrievals, list):
            retrievals = []
        retrievals = [*retrievals, event][-16:]
        self._record["moss_retrievals"] = retrievals
        with contextlib.suppress(Exception):
            await broadcast(
                self._room,
                self._case_id,
                "moss_retrieval",
                {"moss_retrieval": event, "moss_retrievals": retrievals},
            )

    @function_tool()
    async def retrieve_comparables(
        self,
        context: RunContext,
        accident_type: str,
        jurisdiction: str,
        severity: str = "medium",
        fault: str = "contested",
    ) -> str:
        """Pull comparable past settlements from the Moss settlements index.

        Args:
            accident_type: rear_end, t_bone, slip_fall, motorcycle, premises, dog_bite.
            jurisdiction: Two-letter state code (CA, TX, FL).
            severity: low, medium, or high.
            fault: clear, contested, or shared.
        """
        rows = await self._retriever.comparables(
            accident_type, jurisdiction, severity, fault
        )
        if not rows:
            return "No comparable settlements found."
        return "\n\n".join(r.summary() for r in rows)

    @function_tool()
    async def retrieve_state_law(
        self, context: RunContext, state: str, topic: str = "general"
    ) -> str:
        """Look up jurisdictional personal-injury law from the Moss state-law index.

        Args:
            state: Two-letter US state code (CA, TX, FL).
            topic: One of sol, negligence, damages, or general.
        """
        rows = await self._retriever.state_law(state, topic)
        if not rows:
            return "No state law found for that jurisdiction."
        return "\n\n".join(r.summary() for r in rows)

    @function_tool()
    async def retrieve_matching_firms(
        self, context: RunContext, caller_location: str = ""
    ) -> str:
        """Rank firms for this case from the Moss firms index."""
        rows = await self._retriever.firms(self._record, caller_location)
        if not rows:
            return "No matching firms found."
        return "\n\n".join(r.summary() for r in rows)


def _instructions_with_context(record: dict[str, Any]) -> str:
    """Stuff a compact case context into the system prompt for grounded Q&A."""
    ctx = _case_context(record)
    return (
        FIRM_COUNSEL_INSTRUCTIONS
        + "\n\n# Case context for this briefing (JSON)\n"
        + json.dumps(ctx, ensure_ascii=False, default=str)
    )


class _FirmVoiceState(VoiceSessionState):
    """English-only state pinned to the firm male voice."""

    def voice_id_for(self, lang: str | None = None) -> str:
        del lang
        return FIRM_VOICE_ID


class FirmHomeAssistant(Agent):
    """Ambient counsel on the firm home dashboard — welcome + pipeline Q&A."""

    def __init__(
        self,
        *,
        firm_id: str | None,
        firm_name: str | None,
        redaction_session: RedactionSession,
    ) -> None:
        inner_llm = build_dialogue_llm(case_id=firm_id or "firm-home")
        extra = ""
        if firm_name:
            extra = f"\n\n# Signed-in firm\n{firm_name}"
        super().__init__(
            instructions=FIRM_HOME_INSTRUCTIONS + extra,
            llm=RedactingLLM(inner=inner_llm, session=redaction_session),
        )
        self._firm_id = firm_id

    async def on_enter(self) -> None:
        if self.session is None:
            return
        await self.session.generate_reply(
            instructions=Instructions(
                audio=(
                    "The attorney just opened their Caseflowy firm home dashboard. "
                    "Greet them warmly in one or two short sentences. Tell them matched "
                    "leads are in the cases hub on the left, your conversation is on the "
                    "right, and they can open any lead or ask you how we gather sources "
                    "and case briefs. Do not name specific vendors. Do not brief a "
                    "specific case yet."
                ),
            ),
        )


# --------------------------------------------------------------------------- #
# Session entrypoints
# --------------------------------------------------------------------------- #
async def run_firm_home_session(
    ctx: JobContext, *, firm_id: str | None, firm_name: str | None = None
) -> None:
    """Firm home dashboard — ambient counsel without auto-opening a demo case."""
    ctx.log_context_fields = {"room": ctx.room.name, "mode": "firm_home"}
    logger.info("CASEFLOW_FIRM_HOME start firm_id=%s", firm_id)

    redaction_session = RedactionSession()
    bind_redaction_session(redaction_session)

    voice_state = _FirmVoiceState()
    voice_state.language_confirmed = True
    firm_tts, _inner = build_caseflow_voice(state=voice_state)

    session = AgentSession(
        stt=LoggingSTT(state=voice_state, tts=firm_tts),
        tts=firm_tts,
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    assistant = FirmHomeAssistant(
        firm_id=firm_id,
        firm_name=firm_name,
        redaction_session=redaction_session,
    )

    await session.start(
        agent=assistant,
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )


async def run_firm_briefing_session(
    ctx: JobContext, *, case_id: str, firm_id: str | None
) -> None:
    """Run the firm-side ambient briefing + Q&A session in ``ctx.room``."""
    ctx.log_context_fields = {"room": ctx.room.name, "mode": "firm_briefing"}
    logger.info("CASEFLOW_FIRM_BRIEF start case_id=%s firm_id=%s", case_id, firm_id)

    # Bind a fresh per-session redactor BEFORE any gateway call so briefing
    # generation (gateway_chat) and the dialogue LLM share one consistent map and
    # never inherit a stale session from a prior intake in this worker process.
    redaction_session = RedactionSession()
    bind_redaction_session(redaction_session)

    record = await fetch_case_record(case_id)

    voice_state = _FirmVoiceState()
    voice_state.language_confirmed = True
    firm_tts, _inner = build_caseflow_voice(state=voice_state)

    session = AgentSession(
        stt=LoggingSTT(state=voice_state, tts=firm_tts),
        tts=firm_tts,
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    assistant = FirmCounselAssistant(
        room=ctx.room,
        case_id=case_id,
        record=record,
        redaction_session=redaction_session,
    )

    narration_lock = asyncio.Lock()

    async def narrate() -> None:
        async with narration_lock:
            segments = await generate_briefing_segments(record)
            total = len(segments)
            await broadcast(
                ctx.room,
                case_id,
                "briefing_started",
                {
                    "briefing": {
                        "status": "speaking",
                        "total": total,
                        "voice_id": FIRM_VOICE_ID,
                        "sections": [s["section"] for s in segments],
                    }
                },
            )
            for index, seg in enumerate(segments):
                await broadcast(
                    ctx.room,
                    case_id,
                    "briefing_focus",
                    {
                        "briefing_focus": {
                            "section": seg["section"],
                            "title": seg["title"],
                            "caption": seg["body"],
                            "index": index,
                            "total": total,
                        }
                    },
                )
                with contextlib.suppress(Exception):
                    await session.say(seg["body"], allow_interruptions=True)
            await broadcast(
                ctx.room,
                case_id,
                "briefing_complete",
                {"briefing": {"status": "complete", "total": total}},
            )

    def _spawn_narration() -> None:
        task = asyncio.create_task(narrate())
        task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

    def _on_data(data_packet) -> None:
        raw = getattr(data_packet, "data", data_packet)
        message = parse_data_message(raw)
        if not message or message.get("type") != "briefing_control":
            return
        action = (message.get("data") or {}).get("action")
        if action == "replay":
            logger.info("CASEFLOW_FIRM_BRIEF replay requested")
            _spawn_narration()

    ctx.room.on("data_received", _on_data)

    await session.start(
        agent=assistant,
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )

    # Auto-narrate on connect (the "ambient" behaviour), then idle for Q&A.
    _spawn_narration()
