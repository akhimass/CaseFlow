# Caseflow — the multilingual video intake agent for personal injury

**[caseflow.com](https://caseflow.com)** · Built at the YC Conversational AI Hackathon (hosted by Moss)

> A Spanish- or English-speaking accident victim video-calls Caseflow. The agent
> runs intake in their language, parses the documents they hold up to the camera,
> retrieves the comparable settlements and statute-of-limitations rules live,
> catches discrepancies between their account and their evidence, values the case,
> and matches them to the right firm. The firm receives a fully audited case file
> with a verbal brief — not just a name and a phone number.

---

## The problem

Personal injury is one of the largest legal-advertising categories in the U.S.,
and firms compete fiercely for a finite number of cases. Yet the front door of
that business — intake — is broken in three ways:

- **Language.** Tens of millions of U.S. residents speak Spanish as their primary
  language, and PI disproportionately affects working-class and immigrant
  communities. Most firms cannot run high-quality intake in Spanish, so those
  callers get a worse experience or drop off entirely.
- **Speed and drop-off.** Intake is still mostly phone tag. Leads that aren't
  reached within minutes go cold, and after-hours callers — when many accidents
  happen — hit voicemail. The industry runs on expensive call centers that
  produce thin, unverified leads.
- **Leads, not cases.** What a firm buys today is a name and a number. Someone on
  staff still has to call back, re-run intake, chase documents, check the filing
  deadline, and sanity-check the story. The expensive human work happens _after_
  the lead is paid for.

**Caseflow turns the first call into an audited case file.** Same conversation a
senior paralegal would have — in the caller's language, 24/7, grounded in live
legal retrieval and the caller's own documents — handed to the firm ready to act.

## Why now

The hackathon's premise: _"Voice models are solved. Retrieval is the new
bottleneck."_ That is exactly the PI intake problem. The hard part isn't talking
— it's grounding the conversation in the right jurisdiction's law, the right
comparable settlements, and the caller's actual documents, in real time, and
catching when the story and the evidence disagree. Caseflow is built around
retrieval as the core, not an afterthought.

## What it does

1. **Bilingual video intake.** Opens in English, detects the caller's language
   from their first utterance, and runs the rest of intake in English or Spanish —
   wellbeing first, never an interrogation.
2. **Full PI coverage.** Auto (rear-end, T-bone, motorcycle, pedestrian),
   slip-and-fall and premises liability, dog bites, workplace third-party
   injuries, medical malpractice, and wrongful death — the intake adapts to the
   case type within one conversational structure.
3. **Live document parsing.** The caller holds a police report, ER discharge, or
   incident report to the camera; it's parsed into typed fields with per-field
   confidence on screen.
4. **Live retrieval.** Statute of limitations, comparable settlements, procedural
   guidance, and matching firms stream onto the firm dashboard as the call happens.
5. **The discrepancy moment.** When the caller's account contradicts their
   evidence (she says the other driver ran the red light; the police report says
   fault undetermined), the agent catches it and asks a gentle clarifying question
   — then an independent second model re-checks the finding.
6. **Valuation + match.** Economic + non-economic value anchored to comparable
   settlements and discounted for liability, then matched to a firm by jurisdiction,
   language, severity, and specialty.

## Demo (Maria Delgado)

Spanish-speaking, rear-ended in Orange County. Holds up a police report (fault
undetermined) and an ER discharge (whiplash, MRI ordered). Says _"el otro
conductor pasó la luz roja."_ Caseflow catches the contradiction, asks gently in
Spanish, retrieves CA rear-end comparables and the 2-year filing window, values
the case, and surfaces matched firms — all visible on the firm dashboard in real
time.

## Startup timeline

- **Jun 2026 — YC Conversational AI Hackathon.** Working bilingual intake, live
  retrieval across four Moss indexes, document parsing, discrepancy detection,
  valuation, firm matching, iOS + web clients.
- **Q3 2026 — Design partners.** 3–5 PI firms in CA/TX/FL running real after-hours
  and Spanish-language intake; ingest each firm's own intake criteria into Moss.
- **Q4 2026 — Marketplace.** Move from seeded partner firms to matching against
  full firm directories (State Bar, Avvo, Martindale); per-case routing with
  feedback-driven re-ranking.
- **2027 — Scale the vertical.** Expand jurisdictional law coverage state by
  state; add case types end-to-end; on-device offline legal reference on iOS for
  field use. Expand the same audited-intake pattern to adjacent verticals
  (immigration, family, employment) where multilingual, document-heavy intake is
  the bottleneck.

---

## Tech stack

| Layer              | Technology                                                                                  |
| ------------------ | ------------------------------------------------------------------------------------------- |
| Transport + Agents | LiveKit Cloud, LiveKit Agents (Python)                                                      |
| Voice              | MiniMax TTS (speech-2.8-hd) + MiniMax-Text-01 dialogue; Deepgram nova-3 STT                 |
| Retrieval          | Moss — four indexes (`state-law`, `settlements`, `firms`, `procedures`) + per-user `memory` |
| Document AI        | Unsiloed (parse + `/v2/extract` schema extraction)                                          |
| Model gateway      | TrueFoundry (single governed gateway, audit, PII guardrails)                                |
| Cloud / AI         | AWS S3 (case artifacts), Bedrock (second-opinion), Comprehend Medical (ICD-10)              |
| Frontend           | Next.js (App Router), live case stream to firm dashboard                                    |
| Persistence        | Supabase (structured records) + S3 (artifacts)                                              |
| Clients            | Web (mobile Safari) + native iOS (Swift)                                                    |

## Sponsor stack — how we built on top of each

**Moss** — Retrieval is the product, so we run _four_ separate Moss indexes
(state law, settlements, firms, procedures) plus per-user memory, instead of one
generic corpus, giving each stream true isolation and the higher-accuracy
bilingual embedding model. Our firm lead-gen is a single Moss multi-index query
that correlates the firms index against comparable settlements and the
jurisdiction's filing rule, so every firm card carries its own grounding. We
built a feedback loop on top — 👍/👎 from firms re-ranks future Moss results —
and the consistency layer cross-checks the caller's claims against retrieved law
and settlements, not just their documents.

**LiveKit** — One agent runs in two modes over LiveKit Agents: live caller intake
and a separate firm-facing verbal briefing, with semantic turn detection and
noise cancellation tuned for distressed callers on bad phone connections. We push
parsed-document frames and live retrieval cards over LiveKit data channels, so the
same event path drives both the web and native iOS clients. The result feels like
a calm human intake specialist, not a chatbot waiting for a wake word.

**MiniMax** — MiniMax is both the brain and the voice: MiniMax-Text-01 drives the
dialogue and MiniMax speech-2.8-hd speaks it, with separate serene voices for
English and Spanish. We route emotion and speed per moment — softening and slowing
for pain or grief, steady and reassuring when confirming a matched firm — and the
language layer handles mid-call code-switching instead of locking to one language.
This makes Spanish intake feel native, not translated.

**Unsiloed** — Callers hold real documents to a phone camera, and Unsiloed parses
them into typed fields live; we built schema-based extraction (`/v2/extract`) with
a self-classifying `document_type` field so a driver's license shown instead of a
police report is caught, not mislabeled. Per-field confidence drives a "verify
with caller" UI on the firm dashboard, so low-confidence fields are flagged for
human confirmation rather than trusted blindly. Parsed ER-discharge text is handed
downstream for ICD-10 coding, turning a photo into structured, auditable evidence.

**TrueFoundry** — Every model call routes through TrueFoundry as a single governed
gateway, with per-request metadata, audit logging, and failover baked in. We
attach PII guardrails to documents scanned or uploaded from the iOS and web apps,
so sensitive content is screened before it's trusted downstream — a second layer
over our app-side redaction. A dev metrics view surfaces the real audit trail —
the full model fleet by provider, latency, and failovers — so model usage is
observable, not a black box.

**AWS** — Case artifacts (transcripts, parsed docs, audits, match results) land in
tiered S3 buckets with KMS encryption, separating sensitive content from
operational data. AWS Bedrock runs an independent second-opinion: a different
model family re-reviews each flagged discrepancy and votes confirm/refute before
it reaches the firm, so we don't challenge a real caller on a false positive. AWS
Comprehend Medical codes ER discharges to ICD-10, refining injury severity and
sharpening the comparable-settlement query.

---

## Run it

Full scope, demo flow, and environment variables: see [CLAUDE.md](./CLAUDE.md).

```bash
cd CaseFlow
pnpm setup
pnpm moss:index        # build the four Moss indexes from agent-py/knowledge/
pnpm agent:py:download-files   # VAD + turn-detector models (first run only)
pnpm dev               # starts the Python agent worker + Next.js app
```

- Landing: http://localhost:3000
- Intake: http://localhost:3000/intake
- Firm dashboard: http://localhost:3000/firm

You need two processes — the frontend alone cannot dispatch the agent. In the
agent terminal you should see `registered worker {"agent_name": "caseflow-agent", ...}`.

**Agent didn't join the room?** Check, in order: (1) the agent worker is running
(`pnpm dev:agent-py`); (2) model files downloaded (`pnpm agent:py:download-files`);
(3) `AGENT_NAME` matches between `frontend/.env.local` and the agent; (4)
`LIVEKIT_URL` / keys match across both `.env.local` files.

## License

MIT — see [LICENSE](./LICENSE).
