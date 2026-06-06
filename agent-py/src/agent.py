import contextlib
import json
import logging
import os
import textwrap
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    inference,
    room_io,
)
from livekit.plugins import ai_coustics, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from moss import DocumentInfo, MossClient, QueryOptions

from case_broadcast import broadcast
from case_tools import (
    check_consistency,
    compute_case_strength,
    match_firm,
    mock_call_firm,
    mock_sms_confirmation,
    parse_document_unsiloed,
)
from sol_lookup import check_sol

logger = logging.getLogger("agent")

load_dotenv(".env.local")

KNOWLEDGE_INDEX = os.getenv("MOSS_INDEX_NAME", "knowledge")
MEMORY_INDEX = os.getenv("MOSS_MEMORY_INDEX_NAME", "memory")
DEFAULT_USER_ID = "user_1"

ARIA_INSTRUCTIONS = textwrap.dedent(
    """\
    You are Aria, a bilingual (Spanish and English) video intake specialist for
    Caseflow, a personal injury intake platform. You conduct intake over live
    video — warm, professional, unhurried. Auto-detect the caller's language from
    their first utterance and conduct the entire intake in that language.

    # Intake flow

    1. Greet in the caller's language. Ask what happened.
    2. Collect: accident type, date, state/jurisdiction, injuries, treatment so
       far, fault as the caller perceives it, prior representation.
    3. When documents are relevant, ask the caller to hold them up to the camera
       and call parse_document.
    4. After parsing, call check_consistency if verbal claims may conflict with
       documents — especially fault. Ask clarifying questions gently, never accusing.
    5. Call search_legal_knowledge for SoL rules, comparables, and firm context.
    6. Save each field with save_case_field as you learn it.
    7. Call compute_case_strength and match_firm before closing.
    8. Close by confirming a matched firm will reach out the next morning.
    9. Mock outbound: call_firm_with_brief then send_sms_confirmation.

    # Voice rules

    Plain text only. One to three sentences. One question per turn. No markdown,
    lists, or tool names spoken aloud. Never promise settlement amounts or legal
    outcomes. Say "filing window" not "statute of limitations" unless caller does.

    # Demo persona awareness

    Maria Delgado scenarios: rear-end in Orange County CA, June 1 2026, Spanish
    primary, police report fault undetermined, ER whiplash with MRI ordered.
    The key moment: she says the other driver ran the red light; the report says
    undetermined — catch this gently in Spanish.
    """
)


class Assistant(Agent):
    """Caseflow video intake agent with Moss RAG and live case broadcasting."""

    def __init__(self, *, room=None, user_id: str = DEFAULT_USER_ID) -> None:
        super().__init__(
            llm=inference.LLM(model="openai/gpt-5.2-chat-latest"),
            instructions=ARIA_INSTRUCTIONS,
        )
        self._room = room
        self._user_id = user_id
        self._case_id = user_id
        self._language = "en"
        self._case_data: dict = {"caller_id": user_id, "language": "en"}
        self._moss = MossClient(
            os.getenv("MOSS_PROJECT_ID"), os.getenv("MOSS_PROJECT_KEY")
        )
        self._indexes_loaded = False

    async def on_enter(self) -> None:
        if not self._indexes_loaded:
            try:
                await self._moss.load_index(KNOWLEDGE_INDEX)
                await self._moss.load_index(MEMORY_INDEX)
                self._indexes_loaded = True
            except Exception:
                logger.exception("Failed to preload Moss indexes")

    async def _publish_moss_context(self, query: str, result) -> None:
        if self._room is None:
            return
        try:
            matches: list[dict] = []
            for doc in getattr(result, "docs", None) or []:
                entry: dict = {"text": (getattr(doc, "text", "") or "").strip()}
                score = getattr(doc, "score", None)
                if score is not None:
                    with contextlib.suppress(TypeError, ValueError):
                        entry["score"] = float(score)
                metadata = getattr(doc, "metadata", None)
                if metadata:
                    entry["metadata"] = metadata
                matches.append(entry)

            payload = {
                "type": "moss_context",
                "data": {
                    "query": query,
                    "matches": matches,
                    "time_taken_ms": getattr(result, "time_taken_ms", None),
                    "timestamp": datetime.now(timezone.utc).timestamp(),
                },
            }
            await self._room.local_participant.publish_data(
                payload=json.dumps(payload, default=str).encode("utf-8"),
                reliable=True,
            )
        except Exception:
            logger.exception("Failed to publish moss_context")

    async def _update_case(self, event: str, fields: dict) -> None:
        self._case_data.update(fields)
        await broadcast(self._room, self._case_id, event, self._case_data)

    @function_tool()
    async def search_legal_knowledge(self, context: RunContext, query: str) -> str:
        """Search PI law, SoL, settlements, and firm profiles before answering legal questions.

        Args:
            query: Topic to look up (SoL, comparables, firm match, negligence rules).
        """
        result = await self._moss.query(
            KNOWLEDGE_INDEX, query, QueryOptions(top_k=3)
        )
        await self._publish_moss_context(query, result)
        docs = getattr(result, "docs", None) or []
        snippets = [(getattr(d, "text", "") or "").strip() for d in docs]
        snippets = [s for s in snippets if s]
        if not snippets:
            return "No relevant legal knowledge found."
        return "\n\n".join(snippets)

    @function_tool()
    async def save_case_field(self, context: RunContext, field_name: str, value: str) -> str:
        """Persist a structured case field (accident_type, injuries, fault_claim, state, etc.).

        Args:
            field_name: Case field key.
            value: Field value as plain text.
        """
        doc = DocumentInfo(
            id=f"{self._user_id}-{field_name}-{uuid.uuid4()}",
            text=f"{field_name}={value}",
            metadata={"user_id": self._user_id, "field": field_name},
        )
        await self._moss.add_docs(MEMORY_INDEX, [doc])
        try:
            await self._moss.load_index(MEMORY_INDEX)
        except Exception:
            logger.exception("Failed to reload memory index")
        if field_name == "language":
            self._language = value.lower()
        await self._update_case("field_saved", {field_name: value})
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

        Args:
            image_base64: Base64-encoded camera frame of the document.
            doc_type: police_report, er_discharge, or insurance_letter.
        """
        parsed = await parse_document_unsiloed(image_base64, doc_type)
        await self._update_case("document_parsed", {"documents": {doc_type: parsed}})
        return json.dumps(parsed)

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
        result = check_consistency(
            field_name, verbal_claim, parsed_value, self._language
        )
        if result.get("conflict"):
            await self._update_case("discrepancy_found", result)
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
        result = match_firm(self._case_data, caller_location)
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
        result = mock_call_firm(firm_id, case_summary)
        await self._update_case("outbound_call", result)
        return json.dumps(result)

    @function_tool()
    async def send_sms_confirmation(
        self, context: RunContext, consumer_phone: str, consultation_time: str
    ) -> str:
        """SMS confirmation to consumer — mocked for hackathon demo.

        Args:
            consumer_phone: Caller phone number.
            consultation_time: Booked consultation time.
        """
        result = mock_sms_confirmation(consumer_phone, consultation_time)
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


@server.rtc_session(agent_name="caseflow-agent")
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    user_id = DEFAULT_USER_ID
    if ctx.job.metadata:
        try:
            meta = json.loads(ctx.job.metadata)
            user_id = meta.get("user_id", DEFAULT_USER_ID)
        except json.JSONDecodeError:
            logger.warning("Invalid job metadata; using default user_id")

    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="multi"),
        tts=inference.TTS(
            model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    assistant = Assistant(room=ctx.room, user_id=user_id)

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

    await ctx.connect()

    await session.generate_reply(
        instructions=(
            "Greet the caller warmly in one sentence in Spanish or English based on "
            "their language. Introduce yourself as Aria from Caseflow and ask what "
            "happened. Invite them to use video if they have documents to show."
        )
    )


if __name__ == "__main__":
    cli.run_app(server)
