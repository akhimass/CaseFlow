# Caseflowy — YC Conversational AI Hackathon

## The pitch (one paragraph)

Caseflowy is a multilingual video intake agent for personal injury cases. A Spanish- or English-speaking caller video-calls our agent, who runs intake in their language, parses documents they hold up to the camera, retrieves comparable settlements and statute-of-limitations rules live via Moss, catches discrepancies between their verbal account and parsed evidence, then matches them to a firm and books the consultation via an outbound Twilio call to the firm. The firm receives a fully audited case file with a verbal brief — not just a lead.

## Hackathon context

- Event: YC Conversational AI Hackathon, June 6-7 2026, hosted by Moss at YC HQ
- Theme: "Voice models are solved. Retrieval is the new bottleneck."
- Tracks: Lead Gen (primary), Support (secondary), Co-Pilot (tertiary)
- Prize target: First place (YC interview + iPhones)
- Submission: Sunday 11 AM. Judging: Sunday 1 PM.

## The demo persona (memorize)

Maria Delgado. Rear-ended in Orange County, CA on June 1, 2026. Speaks Spanish primarily. Has the police report (fault undetermined, other driver claimed right of way) and ER discharge (whiplash, MRI ordered).

The discrepancy moment is the demo's heart: Maria says "el otro conductor pasó la luz roja" (the other driver ran the red light), but the police report says fault undetermined. The agent must catch this and ask a clarifying question gently, in Spanish, mid-conversation.

## Tech stack — strict, do not deviate

### Sponsor tech (use heavily)

- **LiveKit** — video transport + Agents framework (Python). Voice pipeline on LiveKit Agents.
- **Moss** — real-time retrieval. Four namespaces: `state-law`, `settlements`, `firms`, `procedures`.
- **Unsiloed** — live document parsing (`police_report`, `er_discharge`, optional `insurance_letter`).
- **MiniMax** — Spanish + English STT/TTS via LiveKit plugin. Speech 2.8 HD.
- **Qwen** — reasoning via TrueFoundry gateway (`qwen-max` alias). Conversation + consistency checking.
- **TrueFoundry** — **sole model gateway**. Every LLM call routes through TrueFoundry; audit + metrics logged.
- **AWS S3** — case artifacts (transcripts, parsed docs, audits, match results, firm briefs). Supabase remains primary for structured records.

### Non-sponsor additions (justified)

- **Twilio** — outbound PSTN to *test firm number we control*.
- **Supabase** — primary persistence: cases, documents, matches, audit_log, transcripts.
- **Next.js** — App Router.

## Architecture

```
Consumer (mobile Safari)
  → LiveKit video room
  → LiveKit Agent (Python) — Aria
     • MiniMax STT/TTS (direct via LiveKit plugin; TTS audited to TrueFoundry)
     • Qwen via TrueFoundry gateway (conversation reasoning)
     • Moss retrieval (4 streams)
     • Unsiloed document parsing
     • Consistency layer: Qwen via gateway (rules fallback + LiveKit Inference failover)
     • Async validator every 5 turns
  → Supabase (cases, documents, audit_log) + S3 (transcript.jsonl, parsed/*, audit/*, match/*)
  → Firm dashboard (SSE) — transcript, Moss, consistency audit, TrueFoundry metrics
  → Twilio outbound + SMS
```

## Model roles (no fallback framing — defined jobs)

| Model | Role |
|---|---|
| `qwen-max` | Conversation reasoning + consistency auditing |
| `livekit-inference` | Gateway resilience failover only (8s timeout) |
| MiniMax | STT/TTS (direct; audit logged) |

## File ownership

- `agent-py/src/agent.py` — LiveKit Agent, tools registered here
- `agent-py/src/gateway.py` — TrueFoundry unified client (chat, embed, tts audit)
- `agent-py/src/consistency.py` — discrepancy detection (Qwen + rules fallback)
- `agent-py/src/aws_s3.py` — S3 artifact writes (buffered transcript.jsonl)
- `agent-py/src/case_persistence.py` — Supabase + S3 unified persistence
- `agent-py/src/supabase_store.py` — Supabase REST client
- `agent-py/src/validator.py` — async quality eval every 5 turns
- `agent-py/src/tools/` — individual tool implementations
- `agent-py/knowledge/` — Moss seed content
- `kb/firms.json` — 5 demo firms
- `frontend/app/intake/` — consumer video intake
- `frontend/app/firm/` — firm dashboard with live panels
- `frontend/app/admin/metrics/` — dev-only TrueFoundry metrics
- `supabase/migrations/` — schema

## Environment variables

### TrueFoundry (required for gateway)
```
TRUEFOUNDRY_GATEWAY_URL=https://gateway.truefoundry.ai
TRUEFOUNDRY_API_KEY=
TRUEFOUNDRY_PROJECT_ID=   # tracing project FQN when available
QWEN_MODEL_ID=qwen/qwen3-32b
```

### Supabase (primary persistence)
```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

### AWS S3
```
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-west-2
AWS_S3_BUCKET=caseflow-cases-dev
```

### LiveKit + Moss + Unsiloed + MiniMax + Twilio
See `agent-py/.env.example` and `frontend/.env.example`.

## Demo flow (90 seconds)

1. (0:00-0:10) Maria joins video. Agent greets in Spanish.
2. (0:10-0:25) Case fields populate firm dashboard. Moss retrieves CA PI law.
3. (0:25-0:40) Police report + ER discharge parsed live.
4. (0:40-1:00) **Discrepancy moment** — Qwen consistency audit fires; clarifying question in Spanish.
5. (1:00-1:15) Match engine surfaces top 3 firms.
6. (1:15-1:30) Twilio outbound to test receptionist. SMS to Maria.

## Never skip in demo

- Spanish-language intake
- The discrepancy moment
- Live document parsing on screen
- Moss retrieval cards updating in real time
- Outbound Twilio call audible to judges

## Constraints — DO NOT add

- No Bedrock Claude consistency layer (dropped — Qwen owns consistency)
- No Comprehend Medical (Unsiloed parsing is enough)
- No DynamoDB (Supabase is primary)
- No SageMaker, Lex, Polly
- No real-time blocking validation — async validator only
- `/admin/metrics` dev-only, not in production builds

## Run commands

```bash
cd ~/CaseFlow
pnpm setup
pnpm moss:index
pnpm dev
```

- Landing: http://localhost:3000
- Intake: http://localhost:3000/intake
- Firm dashboard: http://localhost:3000/firm
- Gateway metrics: http://localhost:3000/admin/metrics
