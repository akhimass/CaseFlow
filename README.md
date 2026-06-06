# Caseflow — Multilingual PI Video Intake

Caseflow is a multilingual (Spanish + English) video intake agent for personal injury cases, built for the YC Conversational AI Hackathon on the [LiveKit Moss Hacker Starter](https://github.com/livekit-examples/moss-hacker-starter).

Aria conducts live video intake, parses documents held to camera via Unsiloed, retrieves legal knowledge and comparables via Moss, catches verbal/document discrepancies, scores case strength, matches firms, and closes with a mock Twilio outbound + SMS.

## Stack

| Layer | Technology |
| --- | --- |
| Transport + Agents | LiveKit Cloud, LiveKit Agents Python |
| STT / LLM / TTS | LiveKit Inference (swap to MiniMax/Qwen later) |
| Retrieval | Moss (`knowledge` + `memory` indexes) |
| Document parsing | Unsiloed |
| Firm dashboard | Next.js + SSE case stream |
| Persistence | Supabase (optional) |

## Repository layout

```
CaseFlow/
├── agent-py/
│   ├── src/agent.py           # Aria agent + Caseflow tools
│   ├── src/case_tools.py      # Unsiloed, scoring, matching
│   ├── src/case_broadcast.py
│   ├── src/sol_lookup.py
│   └── knowledge.json         # PI law, firms, settlements
├── frontend/
│   ├── app/page.tsx           # Marketing landing
│   ├── app/intake/page.tsx    # Video intake (LiveKit)
│   └── app/firm/page.tsx      # Firm dashboard (SSE)
├── supabase/migrations/       # cases, documents, firms, matches
└── package.json
```

## Setup

```bash
pnpm setup
lk app env -w agent-py
lk app env -w frontend
```

Paste Moss + Unsiloed keys into `agent-py/.env.local`:

```dotenv
MOSS_PROJECT_ID=...
MOSS_PROJECT_KEY=...
UNSILOED_API_KEY=...
```

Set `AGENT_NAME=caseflow-agent` in `frontend/.env.local`.

## Build Moss indexes

After reviewing `agent-py/knowledge.json`:

```bash
pnpm moss:index
```

## Run

```bash
pnpm dev
```

- Landing: http://localhost:3000
- Intake: http://localhost:3000/intake
- Firm dashboard: http://localhost:3000/firm

## Demo flow (Maria Delgado)

1. Join video intake — Aria greets in Spanish
2. Maria describes rear-end in Orange County, June 1 2026
3. Holds up police report → Unsiloed parses fault undetermined
4. Holds up ER discharge → whiplash, MRI ordered
5. Aria catches red-light claim vs undetermined report — asks clarifying question in Spanish
6. Moss retrieves CA rear-end comparables ($45–72K)
7. Match engine surfaces Martinez & Associates + others
8. Mock outbound call + SMS confirmation

## License

MIT — see [LICENSE](./LICENSE).
