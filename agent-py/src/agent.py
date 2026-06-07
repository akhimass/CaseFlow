import asyncio
import contextlib
import json
import logging
import os
import textwrap
import time
import uuid

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    UserInputTranscribedEvent,
    cli,
    function_tool,
    room_io,
)
from livekit.agents.llm import ChatMessage
from livekit.agents.llm.chat_context import Instructions
from livekit.plugins import ai_coustics, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from moss import DocumentInfo, MossClient, QueryOptions

from adaptive_retrieval import AdaptiveRetriever
from aws_s3 import s3_configured, save_document_frame
from bedrock_llm import bedrock_configured
from case_broadcast import broadcast
from case_completeness import case_completeness, completeness_crossed
from case_persistence import CasePersistence
from caseflow_userdata import CaseflowUserdata
from citations import filter_citation_stream
from consistency import audit_utterance, check_cross_document, extract_injury_keywords
from doc_intent import DocumentCaptureCoordinator, detect_document_intent
from doc_thumbnail import make_redacted_thumbnail
from document_generator import generate_intake_summary, generate_post_match_documents
from gateway import _record_audit, gateway_configured, llm_configured
from gateway import tts as gateway_tts
from geo import state_from_location
from llm_client import build_dialogue_llm, openai_direct_configured
from metrics import MetricsTracker
from minimax_voice import (
    LoggingSTT,
    VoiceSessionState,
    apply_tts_options,
    build_caseflow_voice,
    caseflow_stt_model,
    deepgram_configured,
    log_tts_request,
    normalize_lang,
    resolve_caller_language,
    select_emotion,
    sync_caller_language,
    voice_stt_payload,
    voice_tts_payload,
)
from openai_llm import openai_configured
from orchestrator import run_parallel_retrieval, synthesize_and_emit
from orchestrator import summarize as orchestrator_summarize
from pii_redaction import RedactionSession, moss_field_value
from post_call import build_post_call_package
from privacy_context import bind_redaction_session
from privacy_ops import build_operational_case
from pronunciation import register_pronunciation_terms, terms_from_parsed
from redacting_llm import RedactingLLM
from retrieval import ALL_KNOWLEDGE_INDEXES, Retriever
from slot_extraction import extract_slots, slots_above_threshold
from supabase_store import _configured as supabase_configured
from tools import (
    call_firm,
    check_consistency,
    check_sol,
    compute_case_strength,
    match_firm,
    send_sms,
)
from tools import (
    parse_document as parse_document_tool,
)
from validator import maybe_validate_turn
from video_capture import (
    request_document_capture,
    request_enable_video,
    setup_document_frame_handler,
)

logger = logging.getLogger("agent")

load_dotenv(".env.local")

if openai_direct_configured():
    logger.info(
        "OpenAI direct configured — dialogue primary is api.openai.com (%s)",
        os.getenv("OPENAI_DIRECT_MODEL", "gpt-4.1-mini"),
    )
elif openai_configured():
    logger.info("OpenAI configured — gateway-routed LLM calls use OpenAI (gpt-4.1-mini)")
elif gateway_configured():
    logger.info(
        "TrueFoundry gateway configured — LLM calls route through gateway (Bedrock fallback)"
    )
elif bedrock_configured():
    logger.info(
        "Bedrock configured — gateway-routed LLM calls use Bedrock until TrueFoundry is set"
    )
elif llm_configured():
    logger.warning("Only LiveKit Inference available for gateway-routed LLM calls")
else:
    logger.warning(
        "No gateway LLM configured — consistency uses rules-only fallback"
    )
if s3_configured():
    logger.info("AWS S3 configured — case artifacts will persist to bucket")
else:
    logger.warning("AWS IAM keys not set — S3 persistence disabled")

if supabase_configured():
    logger.info("Supabase service role configured — structured persistence enabled")
else:
    logger.warning("Supabase service role not set — DB writes disabled")

MEMORY_INDEX = os.getenv("MOSS_MEMORY_INDEX_NAME", "memory")
DEFAULT_USER_ID = "user_1"

# Case fields that, when they change, trigger adaptive Moss re-retrieval (Part 4).
TRACKED_CASE_FIELDS = {
    "state",
    "accident_type",
    "severity",
    "fault",
    "er_visited",
    "imaging_ordered",
    "injuries",
    "treatment",
    "language",
    "prior_representation",
}


# Phrases that mark a caller's fault claim (used to remember the last one so the
# discrepancy can be checked proactively after the police report is parsed).
_FAULT_CLAIM_PHRASES = (
    "red light",
    "luz roja",
    "pasó la luz",
    "paso la luz",
    "ran the",
    "semáforo",
    "their fault",
    "su culpa",
    "no fue mi culpa",
    "not my fault",
)


def _state_from_location(location: str) -> str | None:
    """Best-effort two-letter state code from a free-text location string.

    Delegates to :mod:`geo`, which resolves a bare city or county ("Anaheim",
    "Orange County") to its state — so retrieval can fire before the caller ever
    names the state explicitly.
    """
    return state_from_location(location)


ARIA_INSTRUCTIONS = textwrap.dedent(
    """\
    You are the bilingual (Spanish and English) video intake specialist for
    Caseflow, a personal injury intake platform. You conduct intake over live
    video — warm, professional, unhurried.

    You never give yourself a name. You are simply "the Caseflow intake
    specialist." If the caller asks your name, say warmly that you are the
    Caseflow intake assistant and move on — do not invent a personal name.

    # Language

    Always open the session in English: greet warmly, say you are here to help,
    and invite them to describe what happened. After the caller's first utterance,
    detect their language and conduct the rest of intake in that language only
    (English or Spanish).

    # Intake flow

    1. Greet first when the session starts — in English only. Example tone:
       "Welcome to Caseflow — take a breath, I'm here to help. Can you tell me
       what happened?" Never wait silently; never say "ask a question" or
       "I'm listening."
    2. Collect: accident type, date, state/jurisdiction, injuries, treatment so
       far, fault as the caller perceives it, prior representation. Let the caller
       lead — follow their story, don't march through this like a checklist.
    3. When a document would help (police report, ER discharge, insurance letter),
       see "Camera and documents" below.
    4. After documents are parsed, audit the caller's claims (see "Consistency
       auditing" below). Ask clarifying questions gently, never accusing.
    5. Retrieve supporting knowledge from Moss as soon as you have the inputs it
       needs (see "Retrieval tools" below). Do not wait until the end of the call.
    6. Save each field with save_case_field as you learn it.
    7. Call compute_case_strength and match_firm before closing.
    8. Close by confirming a matched firm will reach out the next morning.
    9. Mock outbound: call_firm_with_brief then send_sms_confirmation.

    # Conversation style

    This is a conversation, not an interrogation. Speak the way an experienced,
    calm intake specialist would on a hard day:
    - One question per turn. Wait for the answer. Never stack questions.
    - Acknowledge what they just said before moving on — briefly and varied, not
      a robotic "I understand" every time.
    - Mirror their pace. If they are upset or in pain, slow down and soften.
    - Never re-ask something you already know from the case so far.
    - Keep turns short (one to two sentences) so it feels like a real dialogue.
    - You may volunteer a reassuring next step, but never lecture.

    # Camera and documents

    The caller is on live video.
    - When a document would help, ask them to turn on their camera so you can take
      a look ("Would you mind turning on your camera so I can see it?"). The camera
      turns on for them automatically when you ask.
    - Then ask them to hold the document steady, close to the lens, and keep it in
      frame. It is parsed automatically — you do not read it aloud or name a tool.
    - Make it a single, calm request — don't stack it with another question.

    # Retrieval tools

    You have four retrieval tools, all backed by Moss:
    - retrieve_state_law(state, topic) — pull jurisdictional PI law (SoL,
      negligence rules, damage caps). Call this the moment you know the caller's
      state — and a city or county is enough to infer it (Anaheim or Orange
      County means California). You do not need them to name the state.
    - retrieve_comparables(accident_type, jurisdiction, severity, fault) — pull
      comparable settlement ranges. Call this once you have accident type and
      severity.
    - retrieve_matching_firms(case_data, caller_location) — pull top matching
      firms. Call this only after you have enough case context (accident type,
      jurisdiction, language preference, severity).
    - retrieve_procedural_guidance(scenario) — pull what-to-do checklists. Call
      this when the caller asks "what should I do" or when you proactively
      volunteer next steps.

    Use these proactively as soon as you have the inputs they need. Do not wait
    until the end of the call. Reference what you retrieve conversationally — for
    example, "based on similar cases in California, settlements have ranged from
    $30,000 to $80,000" — never read results verbatim or say "Moss returned."

    Always acknowledge what the caller just said in one warm sentence BEFORE you
    surface any retrieved fact. Never open a turn with a statistic or a law
    citation — respond to the person first, then weave in what you found. The
    retrieval runs in the background; the caller should feel heard, not queried.

    # Consistency auditing

    After parsed documents arrive, call audit_claim with each significant claim
    the caller has made. If it returns a clarifying question with confidence
    above 0.7, ask that question gently in the caller's language, framed as
    helping clarify rather than catching a contradiction.

    # Citations

    When you reference specific retrieved information in your response, emit a
    citation marker in this exact format: [cite:<id>]. The marker is invisible to
    the caller — it is stripped before TTS. Examples:
    - "Casos similares en California han llegado a acuerdos entre $30,000 y
      $80,000 [cite:settlements:ca-rear-end-med-contested]"
    - "En California tiene dos años para presentar su demanda [cite:state-law:ca-sol]"
    - "Le voy a conectar con Martinez & Associates [cite:firms:martinez]"

    Emit citations for every claim you make that came from retrieval. Multiple
    citations per response are fine. Citation IDs must match exactly the
    [cite:...] ids the retrieval tools returned to you — copy them verbatim.

    # Voice rules

    Plain text only. Cap at about two sentences for normal turns; up to four
    sentences for the discrepancy moment or final firm match and booking. One
    question per turn. No markdown, lists, or tool names spoken aloud. Never
    promise settlement amounts or legal outcomes. Say "filing window" not
    "statute of limitations" unless caller does.

    Speak with natural pauses and let the caller finish their thoughts. When
    acknowledging pain or distress, slow down slightly and soften your tone.
    When confirming a matched firm or booked consultation, speak with reassuring
    confidence. Use the caller's name when you have it, sparingly. Avoid
    repeating "I understand" — vary acknowledgments naturally. If the caller
    speaks Spanish, respond in fluent culturally natural Spanish using formal
    "usted" unless they use informal Spanish.

    # Demo persona awareness

    Maria Delgado scenarios: rear-end in Orange County CA, June 1 2026, Spanish
    primary, police report fault undetermined, ER whiplash with MRI ordered.
    The key moment: she says the other driver ran the red light; the report says
    undetermined — catch this gently in Spanish.
    """
)


def _instructions_for_language(lang: str) -> str:
    lock = (
        "\n\n# Active caller language\n"
        "Respond only in Spanish using formal usted for the remainder of intake."
        if lang == "es"
        else "\n\n# Active caller language\n"
        "Respond only in English for the remainder of intake."
    )
    return ARIA_INSTRUCTIONS + lock


class Assistant(Agent):
    """Caseflow video intake agent with Moss RAG and live case broadcasting."""

    def __init__(
        self,
        *,
        room=None,
        userdata: CaseflowUserdata | None = None,
        user_id: str = DEFAULT_USER_ID,
        voice_state: VoiceSessionState | None = None,
        case_id: str | None = None,
        consent_given_at: str | None = None,
        caller_location: str | None = None,
    ) -> None:
        self._voice_state = voice_state or VoiceSessionState()
        if userdata is None:
            resolved_case_id = case_id or str(uuid.uuid4())
            userdata = CaseflowUserdata(
                user_id=user_id,
                case_id=resolved_case_id,
                consent_given_at=consent_given_at,
                language=self._voice_state.caller_language,
                case_data={
                    "caller_id": user_id,
                    "language": self._voice_state.caller_language,
                },
            )
            userdata.seed_location(caller_location or "")
        self._userdata = userdata
        self._redaction_session = RedactionSession()
        bind_redaction_session(self._redaction_session)
        self._room = room
        self._user_id = userdata.user_id
        self._case_id = userdata.case_id
        inner_llm = build_dialogue_llm(case_id=self._case_id)
        self._redacting_llm = RedactingLLM(
            inner=inner_llm,
            session=self._redaction_session,
        )
        super().__init__(
            llm=self._redacting_llm,
            instructions=ARIA_INSTRUCTIONS,
        )
        self._consent_given_at = userdata.consent_given_at
        self._caller_location = userdata.caller_location
        self._language = userdata.language
        self._case_data = userdata.case_data
        self._moss = MossClient(
            os.getenv("MOSS_PROJECT_ID"), os.getenv("MOSS_PROJECT_KEY")
        )
        # Per-session Moss query cache, shared between the retrieval tools and the
        # parallel orchestrator so identical queries are never re-issued.
        self._moss_cache: dict = {}
        self._retriever = Retriever(
            self._moss, on_result=self._on_moss_result, cache=self._moss_cache
        )
        # Part 4: incremental re-retrieval as the case state evolves mid-call.
        self._adaptive = AdaptiveRetriever(
            self._retriever, resynthesize=self._resynthesize
        )
        self._indexes_loaded = False
        self._turn = userdata.turn
        self._last_user_utterance = userdata.last_user_utterance
        self._last_agent_utterance = userdata.last_agent_utterance
        self._transcript_lines: list[dict] = []
        self._auto_saved_fields: set[str] = set()
        self._doc_capture = DocumentCaptureCoordinator()
        self._minimax_tts = None
        # Strong refs to fire-and-forget tasks so they aren't GC'd mid-flight.
        self._bg_tasks: set = set()
        # Monotonic counter for cited_source events (UI restarts pulse per event).
        self._cite_seq = 0
        # Monotonic counter for Caseflow Decision updates (UI cross-fades per seq).
        self._decision_seq = 0
        self._generated_doc_types: set[str] = set()
        self._completeness_doc_fired = False
        self._match_docs_fired = False
        self._moss_after_first_turn = False
        # Discrepancy + citation-trail state (Gap 5 / Enh F).
        self._discrepancy_surfaced = False
        self._last_fault_claim = ""
        self._moss_citations: list[dict] = []
        self._persistence = CasePersistence(
            self._case_id,
            self._user_id,
            redaction_session=self._redaction_session,
            language=self._language,
            consent_given_at=consent_given_at,
        )

    def bind_tts(self, tts_engine) -> None:
        self._minimax_tts = tts_engine

    def _sync_userdata(self) -> None:
        """Mirror hot session fields into AgentSession userdata for handoffs/tools."""
        ud = self._userdata
        ud.turn = self._turn
        ud.language = self._language
        ud.last_user_utterance = self._last_user_utterance
        ud.last_agent_utterance = self._last_agent_utterance
        ud.caller_location = self._caller_location

    async def tts_node(self, text, model_settings):
        """Strip [cite:<id>] markers before synthesis and emit cited_source events.

        Aria embeds citation markers inline; the caller must never hear them, so we
        filter the streamed text here (markers can span chunks) and fire a
        cited_source event per marker so the firm dashboard pulses the grounding card.
        """
        cleaned = filter_citation_stream(text, self._emit_citation)
        async for frame in Agent.default.tts_node(self, cleaned, model_settings):
            yield frame

    async def _emit_citation(self, citation_id: str) -> None:
        """Broadcast a cited_source event (SSE to firm dashboard + LiveKit packet)."""
        self._cite_seq += 1
        event = {
            "citation_id": citation_id,
            "timestamp": time.time(),
            "seq": self._cite_seq,
            "turn": self._turn,
        }
        logger.info("CASEFLOW_CITE %s", citation_id)
        # Enh F: keep a citation trail (last 32) so the evidence panel can show
        # which Aria turn cited which retrieval.
        self._moss_citations = [*self._moss_citations, event][-32:]
        # SSE path → firm dashboard (partial payload; the store merges it).
        with contextlib.suppress(Exception):
            await broadcast(
                self._room,
                self._case_id,
                "cited_source",
                {"cited_source": event, "moss_citations": self._moss_citations},
            )
        # LiveKit data packet on its own channel for in-room (intake) consumers.
        if self._room is not None:
            with contextlib.suppress(Exception):
                await self._room.local_participant.publish_data(
                    payload=json.dumps(
                        {"type": "cited_source", "data": event}, default=str
                    ).encode("utf-8"),
                    reliable=True,
                )

    @staticmethod
    def _message_text(message: ChatMessage) -> str:
        parts: list[str] = []
        for block in message.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(str(text))
        return " ".join(parts).strip()

    async def _append_transcript(
        self, speaker: str, text: str, language: str, turn: int
    ) -> None:
        if not text.strip():
            return
        line = {
            "speaker": speaker,
            "text": text.strip(),
            "language": language,
            "turn": turn,
        }
        self._transcript_lines.append(line)
        self._case_data["transcript_lines"] = self._transcript_lines[-200:]
        await self._persistence.on_transcript_line(speaker, text, language, turn)
        await self._update_case(
            "transcript_line",
            {"transcript_line": line, "transcript_lines": self._transcript_lines[-200:]},
        )

    async def _persist_field_internal(
        self, field_name: str, value: str, *, source: str = "agent"
    ) -> None:
        memory_value = moss_field_value(
            field_name,
            value,
            session=self._redaction_session,
            language=self._language,
        )
        doc = DocumentInfo(
            id=f"{self._user_id}-{field_name}-{uuid.uuid4()}",
            text=f"{field_name}={memory_value}",
            metadata={"user_id": self._user_id, "field": field_name, "source": source},
        )
        await self._moss.add_docs(MEMORY_INDEX, [doc])
        try:
            await self._moss.load_index(MEMORY_INDEX)
        except Exception:
            logger.exception("Failed to reload memory index")
        if field_name == "language":
            lang = normalize_lang(value) or (
                "es" if value.lower().startswith("es") else "en"
            )
            self._language = lang
            self._voice_state.caller_language = lang
            self._voice_state.language_confirmed = True
        await self._update_case(
            "field_saved",
            {field_name: value, "field_source": source},
        )

    async def _auto_extract_and_save(self, transcript: str, language: str) -> None:
        slots = await extract_slots(
            transcript,
            language,
            case_id=self._case_id,
            turn=self._turn,
            caller_id=self._user_id,
        )
        for slot in slots_above_threshold(slots):
            if slot.field_name in self._auto_saved_fields:
                continue
            if self._case_data.get(slot.field_name):
                continue
            self._auto_saved_fields.add(slot.field_name)
            await self._persist_field_internal(
                slot.field_name, slot.value, source=f"stt:{slot.source}"
            )
            logger.info(
                "CASEFLOW_AUTO_FIELD %s",
                json.dumps(
                    {
                        "field": slot.field_name,
                        "confidence": slot.confidence,
                        "source": slot.source,
                    },
                    ensure_ascii=False,
                ),
            )

    async def _maybe_capture_document(self, transcript: str) -> None:
        intent = detect_document_intent(transcript)
        if intent is None or not self._doc_capture.should_capture(intent.doc_type):
            return
        await request_enable_video(
            self._room,
            case_id=self._case_id,
            doc_type=intent.doc_type,
            turn=self._turn,
        )
        await request_document_capture(
            self._room,
            case_id=self._case_id,
            doc_type=intent.doc_type,
            turn=self._turn,
            matched_phrase=intent.matched_phrase,
        )
        await self._update_case(
            "document_capture_requested",
            {
                "doc_type": intent.doc_type,
                "matched_phrase": intent.matched_phrase,
                "turn": self._turn,
            },
        )

    async def _ingest_document(
        self,
        doc_type: str,
        image_base64: str,
        *,
        turn: int,
        source: str,
    ) -> dict:
        await self._update_case(
            "document_parsing",
            {
                "document_parsing": {
                    "doc_type": doc_type,
                    "status": "parsing",
                    "provider": "Unsiloed",
                    "turn": turn,
                    "timestamp": time.time(),
                }
            },
        )
        await self._publish_document_event(doc_type, {}, status="parsing")
        thumbnail = make_redacted_thumbnail(image_base64) if image_base64 else None
        if s3_configured():
            await save_document_frame(
                self._case_id, turn=turn, doc_type=doc_type, image_base64=image_base64
            )
        parsed = await parse_document_tool(image_base64, doc_type)
        meta = parsed.get("_meta", {}) if isinstance(parsed, dict) else {}

        # Gap 1: a real Unsiloed failure surfaces as an error — never silent.
        if meta.get("status") == "error":
            await self._update_case(
                "document_parse_error",
                {
                    "document_parsing": {
                        "doc_type": doc_type,
                        "status": "error",
                        "provider": "Unsiloed",
                        "error": meta.get("error", "parse failed"),
                        "latency_ms": meta.get("latency_ms"),
                        "turn": turn,
                        "timestamp": time.time(),
                    }
                },
            )
            await self._publish_document_event(doc_type, parsed, status="error")
            logger.warning("Unsiloed parse error for %s: %s", doc_type, meta.get("error"))
            return parsed

        docs = self._case_data.get("documents") or {}
        if not isinstance(docs, dict):
            docs = {}
        entry = {**parsed, "capture_source": source, "turn": turn}
        if thumbnail:
            entry["thumbnail"] = thumbnail
        docs[doc_type] = entry

        # Gap 3 + Enh C: map parsed fields into case_state BEFORE the fan-out so
        # comparables/state-law filter on the right jurisdiction + injuries.
        derived = self._derive_case_fields(doc_type, parsed)
        await self._update_case(
            "document_parsed",
            {
                "documents": docs,
                **derived,
                "document_parsing": {
                    "doc_type": doc_type,
                    "status": "parsed",
                    "provider": "Unsiloed",
                    "source": meta.get("source"),
                    "field_count": meta.get("field_count", len(parsed)),
                    "latency_ms": meta.get("latency_ms"),
                    "low_confidence": meta.get("low_confidence", []),
                    "turn": turn,
                    "timestamp": time.time(),
                },
                "s3_artifacts": self._s3_artifact_paths(doc_type),
            },
        )
        await self._publish_document_event(doc_type, parsed, status="parsed")
        await self._persistence.on_document_parsed(doc_type, parsed)
        register_pronunciation_terms(
            self._voice_state,
            terms_from_parsed(doc_type, parsed),
            tts=self._minimax_tts,
        )
        if doc_type in {"police_report", "er_discharge"}:
            self._spawn(self._run_retrieval_fanout())
        # Gap 5 + Enh D: proactively run consistency now that a doc is parsed.
        self._spawn(self._post_parse_consistency(doc_type))
        return parsed

    def _derive_case_fields(self, doc_type: str, parsed: dict) -> dict:
        """Map parsed document fields into case_state (Gap 3 + Enh C)."""
        derived: dict = {}
        if doc_type == "police_report":
            location = str(parsed.get("location") or "")
            if location:
                derived["location"] = location
                state = _state_from_location(location)
                if state and not self._case_data.get("state"):
                    derived["state"] = state
            fault = str(parsed.get("fault_determination") or "").lower()
            if "undetermin" in fault and not self._case_data.get("fault"):
                derived["fault"] = "contested"
        elif doc_type == "er_discharge":
            diagnosis = str(parsed.get("primary_diagnosis") or "")
            instructions = str(parsed.get("discharge_instructions") or "")
            if diagnosis and not self._case_data.get("injuries"):
                derived["injuries"] = diagnosis
            keywords = extract_injury_keywords(
                diagnosis, instructions, str(parsed.get("imaging_ordered") or "")
            )
            if keywords:
                derived["injury_keywords"] = keywords
        return derived

    async def _post_parse_consistency(self, doc_type: str) -> None:
        """Proactively surface discrepancies after a parse (Gap 5 + Enh D)."""
        documents = self._case_data.get("documents") or {}
        # Enh D — cross-document: police injury region vs ER discharge region.
        cross = check_cross_document(
            documents.get("police_report"),
            documents.get("er_discharge"),
            self._language,
        )
        if cross and not self._discrepancy_surfaced:
            await self._surface_discrepancy(cross)
            return
        # Gap 5 — police fault undetermined vs the caller's fault claim, without
        # relying on the LLM to choose audit_claim.
        if doc_type != "police_report" or self._discrepancy_surfaced:
            return
        police = documents.get("police_report") or {}
        fault = str(police.get("fault_determination") or "").lower()
        if "undetermin" not in fault or not self._last_fault_claim:
            return
        result = await audit_utterance(
            self._last_fault_claim,
            language=self._language,
            parsed_docs=documents,
            state=str(self._case_data.get("state") or ""),
            case_id=self._case_id,
            turn=self._turn,
            caller_id=self._user_id,
        )
        if result.get("conflict"):
            await self._surface_discrepancy(result)

    async def _surface_discrepancy(self, result: dict) -> None:
        """Record a discrepancy and have Aria ask the clarifying question now."""
        self._discrepancy_surfaced = True
        self._voice_state.message_type = "empathetic"
        with contextlib.suppress(Exception):
            await self._persistence.on_consistency_audit(result)
        audit_fields = {k: v for k, v in result.items() if k != "claims"}
        await self._update_case(
            "discrepancy_found", {"consistency_audit": result, **audit_fields}
        )
        question = result.get("clarifying_question")
        if question and self.session is not None:
            with contextlib.suppress(Exception):
                await self.session.say(question, add_to_chat_ctx=True)

    def _s3_artifact_paths(self, doc_type: str | None = None) -> list[str]:
        bucket = os.getenv("AWS_S3_BUCKET", "caseflow-cases-dev")
        base = f"s3://{bucket}/{self._case_id}/"
        paths = [
            "transcript.jsonl",
            "case/snapshot.json",
            "audit/consistency.json",
            "match/result.json",
        ]
        if doc_type:
            paths.append(f"parsed/{doc_type}.json")
        return [f"{base}{p}" for p in paths]

    async def _on_document_frame(self, data: dict) -> None:
        doc_type = str(data.get("doc_type") or "").strip()
        image_base64 = str(data.get("image_base64") or "").strip()
        turn = int(data.get("turn") or self._turn)
        if not doc_type or not image_base64:
            return
        try:
            await self._ingest_document(
                doc_type,
                image_base64,
                turn=turn,
                source="camera_frame",
            )
        except Exception:
            logger.exception("Failed to ingest document frame for %s", doc_type)

    async def _finalize_post_call(self) -> None:
        try:
            operational = build_operational_case(
                self._case_data,
                session=self._redaction_session,
                language=self._language,
                consent_given_at=self._consent_given_at,
            )
            redacted_lines = operational.get("transcript_lines") or self._transcript_lines
            package = await build_post_call_package(
                case_id=self._case_id,
                caller_id=self._user_id,
                case_data=operational,
                transcript_lines=redacted_lines,
            )
            await self._persistence.flush_all()
            await self._update_case("post_call_package", package)
        except Exception:
            logger.exception("Post-call package build failed")

    def _spawn(self, coro) -> None:
        """Run a coroutine in the background, retaining a reference until done."""
        task = asyncio.create_task(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    async def _preload_indexes(self) -> None:
        if self._indexes_loaded:
            return
        try:
            for index in (*ALL_KNOWLEDGE_INDEXES, MEMORY_INDEX):
                await self._moss.load_index(index)
            self._indexes_loaded = True
        except Exception:
            logger.exception("Failed to preload Moss indexes")

    async def on_enter(self) -> None:
        self._spawn(self._preload_indexes())
        if self.session is None:
            return
        if self._minimax_tts is not None:
            self._voice_state.caller_language = "en"
            self._voice_state.language_confirmed = False
            apply_tts_options(self._minimax_tts, self._voice_state)
        await self.session.generate_reply(
            instructions=Instructions(
                audio=(
                    "The caller just joined live video intake. You are the Caseflow intake "
                    "specialist. Greet them warmly RIGHT NOW in English only — do not wait for "
                    "them to speak first. Say 'Welcome to Caseflow', that you are here to help, "
                    "then ask what happened. Speak slowly and warmly. Two short sentences "
                    "maximum. Do not give yourself a name. Do not speak Spanish until the "
                    "caller responds in Spanish. Never say 'ask a question', 'I'm listening', "
                    "or similar passive phrases."
                ),
            ),
        )

    async def _on_moss_result(self, event: dict) -> None:
        """Callback for the Retriever: append the retrieval card and broadcast it.

        Reaches the firm dashboard via the SSE fan-out in ``_update_case`` and the
        intake-side context panel via a LiveKit ``moss_context`` data packet.
        """
        retrievals = self._case_data.get("moss_retrievals")
        if not isinstance(retrievals, list):
            retrievals = []
        retrievals = [*retrievals, event][-16:]  # keep the last 16 cards
        await self._update_case(
            "moss_retrieval",
            {"moss_retrieval": event, "moss_retrievals": retrievals},
        )
        await self._publish_moss_context_event(event)

    async def _broadcast_voice_bridge(self, *, language: str, language_changed: bool) -> None:
        """Surface Deepgram STT → MiniMax TTS routing on the firm dashboard."""
        if self._voice_state is None:
            return
        payload = {
            "stt_provider": "Deepgram",
            "stt_model": os.getenv("DEEPGRAM_MODEL", "nova-3"),
            "detected_language": language,
            "language_switched": language_changed,
            "tts_provider": "MiniMax",
            "tts_model": os.getenv("MINIMAX_TTS_MODEL", "speech-2.8-hd"),
            "tts_voice": self._voice_state.voice_id_for(),
            "tts_emotion": select_emotion(self._voice_state.message_type),
            "pronunciation_terms": len(self._voice_state.extra_pronunciations),
            "timestamp": time.time(),
        }
        await self._update_case("voice_bridge", {"voice_bridge": payload})

    async def _broadcast_voice_event(self, event: str, payload: dict) -> None:
        """Emit structured voice pipeline events to the firm dashboard SSE path."""
        await self._update_case(
            event,
            {
                "voice_pipeline": {
                    **payload,
                    "event": event,
                    "timestamp": time.time(),
                }
            },
        )

    async def _publish_document_event(self, doc_type: str, parsed: dict, *, status: str) -> None:
        """Push Unsiloed parse status to intake UI via LiveKit data channel."""
        if self._room is None:
            return
        try:
            payload = {
                "type": "document_parse",
                "data": {
                    "doc_type": doc_type,
                    "status": status,
                    "fields": parsed if status == "parsed" else {},
                    "timestamp": time.time(),
                },
            }
            await self._room.local_participant.publish_data(
                payload=json.dumps(payload, default=str).encode("utf-8"),
                reliable=True,
            )
        except Exception:
            logger.exception("Failed to publish document_parse")

    async def _audit_dialogue_turn(self, text: str) -> None:
        """Log dialogue LLM turns to TrueFoundry audit trail (firm metrics panel)."""
        await _record_audit(
            {
                "audit_id": str(uuid.uuid4()),
                "event_type": "gateway_call",
                "model_id": os.getenv("GATEWAY_MODEL", "qwen-max"),
                "resolved_model": getattr(self._redacting_llm, "model", "qwen-max"),
                "provider": getattr(self._redacting_llm, "provider", "truefoundry"),
                "case_id": self._case_id,
                "turn": self._turn,
                "caller_id": self._user_id,
                "input_chars": len(self._last_user_utterance),
                "output_chars": len(text),
                "latency_ms": 0,
                "failover": False,
                "timestamp": time.time(),
            }
        )

    async def _publish_moss_context_event(self, event: dict) -> None:
        if self._room is None:
            return
        try:
            matches: list[dict] = []
            for snippet in event.get("snippets", []):
                entry: dict = {"text": (snippet.get("text") or "").strip()}
                score = snippet.get("score")
                if score is not None:
                    with contextlib.suppress(TypeError, ValueError):
                        entry["score"] = float(score)
                metadata = {
                    k: v for k, v in snippet.items() if k not in ("text", "score")
                }
                if metadata:
                    entry["metadata"] = metadata
                matches.append(entry)

            payload = {
                "type": "moss_context",
                "data": {
                    "query": f"[{event.get('namespace')}] {event.get('query')}",
                    "matches": matches,
                    "time_taken_ms": event.get("time_taken_ms"),
                    "timestamp": event.get("timestamp"),
                },
            }
            await self._room.local_participant.publish_data(
                payload=json.dumps(payload, default=str).encode("utf-8"),
                reliable=True,
            )
        except Exception:
            logger.exception("Failed to publish moss_context")

    async def _update_case(self, event: str, fields: dict) -> None:
        # Part 4A: detect case-state changes before merging so adaptive retrieval
        # can re-query just the affected Moss streams.
        diff = [
            key
            for key in fields
            if key in TRACKED_CASE_FIELDS and fields[key] != self._case_data.get(key)
        ]
        self._case_data.update(fields)
        self._case_data["case_id"] = self._case_id
        self._case_data["last_event"] = event
        if self._consent_given_at:
            self._case_data["consent_given_at"] = self._consent_given_at
        if s3_configured():
            self._case_data["s3_prefix"] = (
                f"s3://{os.getenv('AWS_S3_BUCKET', 'caseflow-cases-dev')}/{self._case_id}/"
            )
        self._redacting_llm.set_language(self._language)
        self._persistence.set_language(self._language)
        operational = build_operational_case(
            self._case_data,
            session=self._redaction_session,
            language=self._language,
            consent_given_at=self._consent_given_at,
        )
        await broadcast(self._room, self._case_id, event, operational)
        await self._persistence.on_case_update(
            event, operational, full_fields=self._case_data
        )
        self._spawn(self._maybe_generate_documents(event))
        if diff:
            logger.info("CASEFLOW_STATE_DIFF %s", diff)
            self._spawn(self._adaptive.on_case_state_change(diff, dict(self._case_data)))

    async def _resynthesize(self) -> None:
        """Re-run synthesis from the latest per-stream rows (adaptive cross-fade)."""
        retrievals = self._retriever.latest_retrievals()
        await synthesize_and_emit(
            retrievals,
            self._case_data,
            self._on_decision,
            case_id=self._case_id,
            caller_id=self._user_id,
        )

    async def _emit_generated_document(self, meta: dict) -> None:
        doc_type = str(meta.get("doc_type") or "")
        if not doc_type:
            return
        docs = self._case_data.get("generated_documents")
        if not isinstance(docs, list):
            docs = []
        docs = [d for d in docs if str(d.get("doc_type")) != doc_type]
        docs.append(meta)
        self._case_data["generated_documents"] = docs
        await self._persistence.on_generated_document(meta)
        await self._update_case(
            "document_generated",
            {"generated_documents": docs, "latest_document": meta},
        )

    async def _maybe_generate_documents(self, event: str) -> None:
        if event == "document_generated":
            return
        try:
            if (
                not self._completeness_doc_fired
                and completeness_crossed(self._case_data)
                and "intake_summary" not in self._generated_doc_types
            ):
                self._completeness_doc_fired = True
                self._generated_doc_types.add("intake_summary")

                async def _on_done(meta: dict) -> None:
                    await self._emit_generated_document(meta)

                await generate_intake_summary(
                    case_id=self._case_id,
                    caller_id=self._user_id,
                    case_data=dict(self._case_data),
                    language=self._language,
                    redaction_session=self._redaction_session,
                    on_complete=_on_done,
                )

            if (
                event == "firms_matched"
                and not self._match_docs_fired
                and "demand_letter" not in self._generated_doc_types
            ):
                self._match_docs_fired = True
                self._generated_doc_types.update({"demand_letter", "action_sheet"})

                async def _on_post_match(meta: dict) -> None:
                    await self._emit_generated_document(meta)

                await generate_post_match_documents(
                    case_id=self._case_id,
                    caller_id=self._user_id,
                    case_data=dict(self._case_data),
                    language=self._language,
                    redaction_session=self._redaction_session,
                    on_complete=_on_post_match,
                )

            self._case_data["case_completeness"] = round(
                case_completeness(self._case_data), 2
            )
        except Exception:
            logger.exception("Document generation orchestration failed")

    @function_tool()
    async def retrieve_state_law(
        self, context: RunContext, state: str, topic: str = "general"
    ) -> str:
        """Look up jurisdictional personal-injury law from the Moss state-law index.

        Call this once you learn the caller's state, and again when the topic
        shifts (filing window, fault rules, damages).

        Args:
            state: Two-letter US state code (CA, TX, FL).
            topic: One of sol (filing window), negligence, damages, or general.
        """
        rows = await self._retriever.state_law(state, topic)
        if not rows:
            return "No state law found for that jurisdiction."
        return "\n\n".join(r.summary() for r in rows)

    @function_tool()
    async def retrieve_comparables(
        self,
        context: RunContext,
        accident_type: str,
        jurisdiction: str,
        severity: str = "medium",
        fault: str = "contested",
    ) -> str:
        """Retrieve comparable past settlements from the Moss settlements index.

        Use this to ground a realistic settlement range for the caller — never
        promise an amount, only describe comparable outcomes.

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
    async def retrieve_matching_firms(
        self, context: RunContext, caller_location: str = ""
    ) -> str:
        """Find the top partner firms for this case from the Moss firms index.

        Filters the curated firm roster by jurisdiction, caller language, specialty,
        and case-value floor, using the case data collected so far.

        Args:
            caller_location: City or county for local-presence matching (optional).
        """
        rows = await self._retriever.firms(self._case_data, caller_location)
        if rows:
            await self._update_case(
                "firms_retrieved",
                {"moss_firm_matches": [r.__dict__ for r in rows]},
            )
            return "\n\n".join(r.summary() for r in rows)
        return "No matching firms found for this case profile."

    @function_tool()
    async def retrieve_procedural_guidance(
        self, context: RunContext, scenario: str
    ) -> str:
        """Retrieve a next-steps checklist from the Moss procedures index.

        Use when the caller asks "what should I do next?" or to proactively offer
        guidance (first 72 hours, insurance adjuster, recorded statements,
        documenting injuries, finding a doctor).

        Args:
            scenario: Plain-language description of the situation or question.
        """
        rows = await self._retriever.procedures(scenario)
        if not rows:
            return "No procedural guidance found."
        return "\n\n".join(r.summary() for r in rows)

    @function_tool()
    async def save_case_field(
        self, context: RunContext, field_name: str, value: str
    ) -> str:
        """Persist a structured case field (accident_type, injuries, fault_claim, state, etc.).

        Args:
            field_name: Case field key.
            value: Field value as plain text.
        """
        await self._persist_field_internal(field_name, value, source="tool")
        return f"Saved {field_name}."

    @function_tool()
    async def recall_case_data(self, context: RunContext, query: str) -> str:
        """Recall case fields saved for this caller.

        Args:
            query: What to recall about the case or caller.
        """
        result = await self._moss.query(
            MEMORY_INDEX,
            query,
            QueryOptions(
                top_k=8,
                filter={
                    "field": "user_id",
                    "condition": {"$eq": self._user_id},
                },
            ),
        )
        docs = getattr(result, "docs", None) or []
        facts = [(getattr(d, "text", "") or "").strip() for d in docs]
        facts = [f for f in facts if f and not f.startswith("(memory seed)")]
        if not facts:
            return "No case data saved yet."
        return "\n".join(facts)

    @function_tool()
    async def parse_document(
        self, context: RunContext, image_base64: str, doc_type: str
    ) -> str:
        """Parse a document the caller holds up to the camera via Unsiloed.

        Ask the caller to turn on video first if needed, then hold the document
        steady close to the lens.

        Args:
            image_base64: Base64-encoded camera frame of the document.
            doc_type: police_report, er_discharge, or insurance_letter.
        """
        # Gap 1: never block Aria's turn on a multi-second Unsiloed parse — ingest
        # in the background and let her keep talking; the dashboard shows progress
        # and the parsed fields land via the document_parse events.
        self._spawn(
            self._ingest_document(
                doc_type, image_base64, turn=self._turn, source="tool"
            )
        )
        label = doc_type.replace("_", " ")
        if self._language.startswith("es"):
            return f"Estoy revisando su {label} ahora mismo; un momento."
        return f"I'm reading your {label} now — one moment."

    async def _run_retrieval_fanout(self) -> None:
        try:
            location = str(self._case_data.get("location") or "")
            result = await run_parallel_retrieval(
                self._retriever,
                self._case_data,
                caller_location=location,
                on_decision=self._on_decision,
                case_id=self._case_id,
                caller_id=self._user_id,
            )
            logger.info(orchestrator_summarize(result))
        except Exception:
            logger.exception("Parallel retrieval fan-out failed")

    async def _on_decision(self, payload: dict) -> None:
        """Broadcast a Caseflow Decision update (synthesizing / ready / error)."""
        self._decision_seq += 1
        prior = self._case_data.get("caseflow_decision")
        prior = prior if isinstance(prior, dict) else {}
        # Preserve the last good synthesis under a transient "synthesizing" status.
        merged = {**prior, **payload, "seq": self._decision_seq, "timestamp": time.time()}
        await self._update_case("caseflow_decision", {"caseflow_decision": merged})

    @function_tool()
    async def check_consistency_tool(
        self,
        context: RunContext,
        field_name: str,
        verbal_claim: str,
        parsed_value: str,
    ) -> str:
        """Check if verbal account conflicts with parsed document evidence.

        Args:
            field_name: Field being compared (e.g. fault_claim).
            verbal_claim: What the caller said.
            parsed_value: What the parsed document states.
        """
        result = await check_consistency(
            field_name,
            verbal_claim,
            parsed_value,
            self._language,
            case_id=self._case_id,
            turn=self._turn,
            caller_id=self._user_id,
            case_state=self._case_data,
        )
        if result.get("conflict"):
            self._voice_state.message_type = "empathetic"
            await self._persistence.on_consistency_audit(result)
            await self._update_case(
                "discrepancy_found",
                {"consistency_audit": result, **result},
            )
        return json.dumps(result)

    @function_tool()
    async def audit_claim(self, context: RunContext, utterance: str) -> str:
        """Cross-check a caller statement against documents and Moss knowledge.

        Extracts the claims in the statement, then checks them against parsed
        documents, the retrieved state law (e.g. filing-window beliefs), and
        comparable settlements (e.g. unrealistic expectations). If a conflict is
        found, returns a gentle clarifying question to ask in the caller's language.

        Args:
            utterance: The caller's most recent statement to audit.
        """
        retrievals = self._case_data.get("moss_retrievals") or []
        law = [
            s
            for ev in retrievals
            if ev.get("namespace") == "state-law"
            for s in ev.get("snippets", [])
        ]
        comps = [
            s
            for ev in retrievals
            if ev.get("namespace") == "settlements"
            for s in ev.get("snippets", [])
        ]
        result = await audit_utterance(
            utterance,
            language=self._language,
            parsed_docs=self._case_data.get("documents"),
            law_snippets=law,
            comparables=comps,
            state=str(self._case_data.get("state") or ""),
            case_id=self._case_id,
            turn=self._turn,
            caller_id=self._user_id,
        )
        if result.get("conflict"):
            self._discrepancy_surfaced = True
            self._voice_state.message_type = "empathetic"
            await self._persistence.on_consistency_audit(result)
            audit_fields = {k: v for k, v in result.items() if k != "claims"}
            await self._update_case(
                "discrepancy_found",
                {"consistency_audit": result, **audit_fields},
            )
        return json.dumps(result)

    @function_tool()
    async def compute_case_strength_tool(self, context: RunContext) -> str:
        """Compute a 0-100 case strength score from collected case data."""
        result = compute_case_strength(self._case_data)
        await self._update_case("strength_computed", result)
        return json.dumps(result)

    @function_tool()
    async def match_firm_tool(
        self, context: RunContext, caller_location: str = ""
    ) -> str:
        """Match the case to top 3 firms from the knowledge base.

        Args:
            caller_location: City or county for local matching.
        """
        ud = context.userdata
        if not isinstance(ud, CaseflowUserdata):
            ud = self._userdata
        location = (caller_location or ud.caller_location or "").strip()
        result = match_firm(ud.case_data, location)
        self._voice_state.message_type = "reassuring"
        await self._persistence.on_firms_matched(result)
        await self._update_case("firms_matched", result)
        return json.dumps(result)

    @function_tool()
    async def call_firm_with_brief(
        self, context: RunContext, firm_id: str, case_summary: str
    ) -> str:
        """Outbound call to matched firm — mocked for hackathon demo.

        Args:
            firm_id: Matched firm identifier.
            case_summary: Brief for the receptionist.
        """
        result = call_firm(firm_id, case_summary)
        await self._persistence.on_firm_brief(case_summary)
        await self._update_case("outbound_call", result)
        return json.dumps(result)

    @function_tool()
    async def send_sms_confirmation(
        self, context: RunContext, consumer_phone: str, consultation_time: str
    ) -> str:
        """SMS confirmation to consumer.

        Args:
            consumer_phone: Caller phone number.
            consultation_time: Booked consultation time.
        """
        body = (
            f"Caseflow: Su consulta está confirmada para {consultation_time}. "
            f"Un bufete se comunicará con usted. Reply STOP to opt out."
            if self._language.startswith("es")
            else (
                f"Caseflow: Your consultation is confirmed for {consultation_time}. "
                "A matched firm will reach out. Reply STOP to opt out."
            )
        )
        result = send_sms(consumer_phone, body)
        await self._update_case("sms_sent", result)
        return json.dumps(result)

    @function_tool()
    async def check_sol_tool(
        self,
        context: RunContext,
        state: str,
        accident_date: str,
        plaintiff_age: int = 30,
    ) -> str:
        """Check statute-of-limitations viability for the caller's state.

        Args:
            state: Two-letter US state code.
            accident_date: ISO date YYYY-MM-DD.
            plaintiff_age: Caller age (default 30).
        """
        result = check_sol(state, accident_date, plaintiff_age)
        await self._update_case("sol_checked", result)
        return json.dumps(result)


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


CASEFLOW_AGENT_NAME = os.getenv("AGENT_NAME", "caseflow-agent")


@server.rtc_session(agent_name=CASEFLOW_AGENT_NAME)
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    user_id = DEFAULT_USER_ID
    case_id: str | None = None
    consent_given_at: str | None = None
    caller_location: str | None = None
    if ctx.job.metadata:
        try:
            meta = json.loads(ctx.job.metadata)
            user_id = meta.get("user_id", DEFAULT_USER_ID)
            case_id = meta.get("case_id")
            consent_given_at = meta.get("consent_given_at")
            caller_location = meta.get("caller_location")
        except json.JSONDecodeError:
            logger.warning("Invalid job metadata; using default user_id")

    voice_state = VoiceSessionState(metrics=MetricsTracker())
    minimax_tts, _minimax_inner = build_caseflow_voice(state=voice_state)

    session_userdata = CaseflowUserdata(
        user_id=user_id,
        case_id=case_id or str(uuid.uuid4()),
        consent_given_at=consent_given_at,
        language=voice_state.caller_language,
        case_data={
            "caller_id": user_id,
            "language": voice_state.caller_language,
        },
    )
    session_userdata.seed_location(caller_location or "")

    session = AgentSession[CaseflowUserdata](
        stt=LoggingSTT(state=voice_state, tts=minimax_tts),
        tts=minimax_tts,
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
        userdata=session_userdata,
    )

    assistant = Assistant(
        room=ctx.room,
        userdata=session_userdata,
        voice_state=voice_state,
    )
    assistant.bind_tts(minimax_tts)

    setup_document_frame_handler(
        ctx.room,
        on_frame=assistant._on_document_frame,
    )

    @session.on("user_input_transcribed")
    def _on_user_transcribed(ev: UserInputTranscribedEvent) -> None:
        if not ev.is_final:
            return
        lang = resolve_caller_language(
            stt_language=str(ev.language) if ev.language else None,
            transcript=ev.transcript,
            current=voice_state.caller_language,
        )
        language_changed = sync_caller_language(voice_state, lang, tts=minimax_tts)
        assistant._language = lang
        assistant._case_data["language"] = lang
        assistant._redacting_llm.set_language(lang)
        assistant._persistence.set_language(lang)
        if language_changed:
            assistant.update_instructions(_instructions_for_language(lang))
        voice_state.message_type = "default"
        assistant._turn += 1
        assistant._last_user_utterance = ev.transcript
        # Remember the caller's most recent fault claim so the discrepancy can be
        # checked proactively once the police report is parsed (Gap 5).
        if any(p in ev.transcript.lower() for p in _FAULT_CLAIM_PHRASES):
            assistant._last_fault_claim = ev.transcript
        assistant._sync_userdata()

        async def _after_transcript() -> None:
            await assistant._broadcast_voice_bridge(
                language=lang, language_changed=language_changed
            )
            await assistant._append_transcript(
                "caller", ev.transcript, lang, assistant._turn
            )
            await assistant._auto_extract_and_save(ev.transcript, lang)
            if assistant._turn == 1 and not assistant._moss_after_first_turn:
                assistant._moss_after_first_turn = True
                assistant._spawn(assistant._run_retrieval_fanout())
            await assistant._maybe_capture_document(ev.transcript)
            await maybe_validate_turn(
                turn=assistant._turn,
                case_id=assistant._case_id,
                caller_id=assistant._user_id,
                last_user_utterance=assistant._last_user_utterance,
                last_agent_utterance=assistant._last_agent_utterance,
                case_state=assistant._case_data,
                language=lang,
            )

        assistant._spawn(_after_transcript())
        stt_engine = session.stt
        assistant._spawn(
            assistant._broadcast_voice_event(
                "voice_stt",
                voice_stt_payload(
                    provider=stt_engine.provider
                    if isinstance(stt_engine, LoggingSTT)
                    else ("Deepgram" if deepgram_configured() else "LiveKit-Inference"),
                    model=stt_engine.model
                    if isinstance(stt_engine, LoggingSTT)
                    else (
                        os.getenv("DEEPGRAM_MODEL", "nova-3")
                        if deepgram_configured()
                        else caseflow_stt_model()
                    ),
                    language=lang,
                    transcript=ev.transcript,
                ),
            )
        )

    @session.on("conversation_item_added")
    def _on_conversation_item(ev) -> None:
        item = ev.item
        if not isinstance(item, ChatMessage) or item.role != "assistant":
            return
        text = Assistant._message_text(item)
        if not text:
            return
        assistant._last_agent_utterance = text
        assistant._sync_userdata()

        async def _persist_agent_line() -> None:
            await assistant._append_transcript(
                "aria",
                text,
                assistant._language,
                assistant._turn,
            )
            await assistant._audit_dialogue_turn(text)

        assistant._spawn(_persist_agent_line())

    @session.on("close")
    def _on_session_close(_ev) -> None:
        assistant._spawn(assistant._finalize_post_call())

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev) -> None:
        if ev.new_state == "speaking":
            apply_tts_options(minimax_tts, voice_state)
            tts_text = assistant._last_agent_utterance or ""
            emotion = select_emotion(voice_state.message_type)
            log_tts_request(
                provider=minimax_tts.provider,
                model=minimax_tts.model,
                voice_id=voice_state.voice_id_for(),
                language=voice_state.caller_language,
                emotion=emotion,
                text_len=len(tts_text),
            )
            assistant._spawn(
                assistant._broadcast_voice_event(
                    "voice_tts",
                    voice_tts_payload(
                        provider=minimax_tts.provider,
                        model=minimax_tts.model,
                        voice_id=voice_state.voice_id_for(),
                        language=voice_state.caller_language,
                        emotion=emotion,
                        message_type=voice_state.message_type,
                    ),
                )
            )
            assistant._spawn(
                gateway_tts(
                    "minimax-speech-2.8-hd",
                    tts_text,
                    voice_state.voice_id_for(),
                )
            )
        if ev.old_state == "speaking" and voice_state.message_type != "default":
            voice_state.message_type = "default"
            apply_tts_options(minimax_tts, voice_state)
        if ev.new_state == "listening" and voice_state.metrics:
            turn = voice_state.metrics.current
            voice_state.metrics.end_turn()
            if turn is not None:
                assistant._spawn(
                    assistant._broadcast_voice_event(
                        "voice_turn_metrics",
                        {
                            k: v
                            for k, v in turn.__dict__.items()
                            if not k.startswith("_") and v is not None
                        },
                    )
                )

    await session.start(
        agent=assistant,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(
                    model=ai_coustics.EnhancerModel.QUAIL_VF_S
                ),
            ),
            video_input=True,
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
