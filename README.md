# Caseflowy — Multilingual PI Video Intake

**Hackathon spec:** see [CLAUDE.md](./CLAUDE.md) — source of truth for scope, demo flow, and sponsor stack.

Caseflowy is a multilingual (Spanish + English) video intake agent for personal injury cases, built for the YC Conversational AI Hackathon on the [LiveKit Moss Hacker Starter](https://github.com/livekit-examples/moss-hacker-starter).

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
│   ├── src/agent.py           # Aria agent + Caseflowy tools
│   ├── src/case_tools.py      # Unsiloed, scoring, matching
│   ├── src/case_broadcast.py
│   ├── src/sol_lookup.py
│   ├── knowledge/             # Moss seed: state-law, settlements, firms, procedures
│   └── src/tools/             # Unsiloed, matching, Twilio, SoL, etc.
├── kb/firms.json              # 5 hardcoded demo firms (matching source of truth)
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

After reviewing `agent-py/knowledge/*.json`:

```bash
pnpm moss:index
```

## Run

First-time setup downloads VAD / turn-detector models (required or the agent worker crashes silently):

```bash
pnpm agent:py:download-files
```

Then start **both** the Python agent worker and the Next.js app:

```bash
pnpm dev
```

You need two processes: the frontend alone cannot dispatch Aria. In the agent terminal you should see:

`registered worker {"agent_name": "caseflow-agent", ...}`

- Landing: http://localhost:3000
- Intake: http://localhost:3000/intake
- Firm login: http://localhost:3000/firm/login
- Firm dashboard: http://localhost:3000/firm

### Agent didn’t join the room?

1. **Agent worker not running** — run `pnpm dev:agent-py` (or `pnpm dev` from repo root).
2. **Missing model files** — run `pnpm agent:py:download-files`, then restart the agent.
3. **Name mismatch** — `AGENT_NAME=caseflow-agent` in `frontend/.env.local` must match `@server.rtc_session(agent_name="caseflow-agent")` in `agent-py/src/agent.py`.
4. **Wrong LiveKit project** — `LIVEKIT_URL` / API keys must match between `frontend/.env.local` and `agent-py/.env.local`.

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
