# TrueFoundry: single front door + virtual models + guardrails

This folder makes TrueFoundry the governed front door for **every** Caseflow LLM
call (dialogue, reasoning, consistency, document audit, firm briefing) instead of
a fallback. The app-side code hooks are already wired and **safe by default** —
nothing changes until you (a) set the env vars and (b) create the matching
TrueFoundry objects below.

## What the code does now

| Concern | Where | Behaviour |
| --- | --- | --- |
| Front door | `gateway.py` `_provider_chain` | `TRUEFOUNDRY_FRONT_DOOR=auto\|on` puts TrueFoundry first; direct providers stay as deeper fallbacks. |
| Virtual model (reasoning) | `gateway.py` `_invoke_provider` | When `TFY_REASONING_MODEL` is set, gateway calls use that virtual model name. |
| Virtual model (dialogue) | `llm_client.py` `_tfy_virtual_dialogue_llm` | When `TFY_DIALOGUE_VIRTUAL_MODEL` is set, conversation leads with that virtual model; Python chain remains a safety net. |
| Guardrails | `gateway.py` / `llm_client.py` | When `TFY_INPUT_GUARDRAILS` / `TFY_OUTPUT_GUARDRAILS` are set, an `X-TFY-GUARDRAILS` header is attached per request. |
| Observability | everywhere | Every request already sends `X-TFY-METADATA` (`case_id`, `turn`, `caller_id`, `firm_id`, `mode`, `application=caseflow`) and `X-TFY-LOGGING-CONFIG`. |

## Setup (≈10 min in the dashboard)

1. **Models** — In AI Gateway → Models, note the catalog FQNs for the providers
   you use (e.g. `openai-main/gpt-4.1-mini`, `bedrock/us.amazon.nova-lite-v1:0`,
   `minimax/MiniMax-Text-01`). Update the `target:` lines in the two
   `virtual-model-*.yaml` files to match.
2. **Virtual models** — Create `caseflow/dialogue` and `caseflow/reasoning`
   (AI Gateway → Virtual Models). Paste the `routing_config` from each YAML into
   the form, or commit the exported manifest for GitOps.
3. **Guardrail** — Create a built-in **PII / PHI Detection** guardrail
   (mutate/redact), add it to a group so its FQN is `caseflow/pii-detection`.
4. **Guardrail rule** — Apply `guardrails.yaml` (`tfy apply -f guardrails.yaml`)
   or recreate it in AI Gateway → Controls → Guardrails.
5. **Tracing** — Set `TRUEFOUNDRY_PROJECT_ID` to your tracing project FQN to turn
   on OpenTelemetry traces.
6. **Env** — Copy the TrueFoundry block from `agent-py/.env.example` into your
   `.env` and fill `TRUEFOUNDRY_GATEWAY_URL` + `TRUEFOUNDRY_API_KEY`.

## Verifying

- Response header `x-tfy-resolved-model` shows which real target served the
  request (proves virtual-model routing + fallback).
- AI Gateway → Analytics shows latency (p50/p95/p99, TTFT), tokens, cost per
  model, and guardrail/fallback activity, sliceable by the metadata above.
- Make a doc-audit call with a fake SSN/name and confirm it is redacted in the
  guardrail logs (gateway layer) — independent of the app-side RedactingLLM.

## Gotchas

- **Streaming + output guardrails**: TF output guardrails don't run when
  `stream: true`. Live dialogue streams (input guardrails still run); the
  reasoning virtual model is non-streamed, so both run there.
- **Virtual models can't target other virtual models** and aren't used by the
  Batch API — use real catalog ids for batch.
- Keep at least one `fallback_candidate: true` target per virtual model so a
  single provider outage can't take down the demo.
