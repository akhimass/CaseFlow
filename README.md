# Caseflowy — the multilingual video intake agent for personal injury

**[caseflowy.com](https://caseflowy.com)** · Built at the YC Conversational AI Hackathon (hosted by Moss)

> A Spanish- or English-speaking accident victim video-calls Caseflowy. The agent
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

**Caseflowy turns the first call into an audited case file.** Same conversation a
senior paralegal would have — in the caller's language, 24/7, grounded in live
legal retrieval and the caller's own documents — handed to the firm ready to act.

## Why now

The hackathon's premise: _"Voice models are solved. Retrieval is the new
bottleneck."_ That is exactly the PI intake problem. The hard part isn't talking
— it's grounding the conversation in the right jurisdiction's law, the right
comparable settlements, and the caller's actual documents, in real time, and
catching when the story and the evidence disagree. Caseflowy is built around
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
7. **Generated case file (PDF).** The intake is compiled into lawyer/paralegal-ready
   PDFs — an Intake Summary, a Demand Letter draft, and a 24-hour Action Sheet —
   each grounded in the case's own S3 artifacts (transcript, parsed documents,
   retrieved law and comparables), independently audited, and downloadable from the
   firm dashboard. The firm receives a case file, not a lead.

## Roadmap

**✅ Shipped — Jun 2026 · YC Conversational AI Hackathon.** Bilingual (EN/ES) video
intake, live retrieval across four Moss indexes (state law, settlements, firms,
procedures), real-time Unsiloed document parsing, an AI-to-AI consistency audit
that catches narrative-vs-evidence discrepancies, comparable-grounded case
valuation, firm matching with a verbal briefing, and a generated case-file PDF —
on web and native iOS.

**Q3 2026 — Design partners & conversion.** 3–5 PI firms across CA/TX/FL running
production intake, with after-hours and Spanish coverage as the wedge. Instrument
the full funnel (arrive → intake → match → consult → retained) as the north-star
metric. Each firm's acceptance criteria ingested into private Moss namespaces;
languages add Mandarin, Vietnamese, Tagalog, Russian. HIPAA BAAs across the stack;
SOC 2 Type I initiated.

**Q4 2026 — Marketplace & vertical depth.** Move from seeded firms to full
directory ingestion (State Bars, Avvo, Martindale, Justia) with capacity-aware
best-match routing — a two-sided loop where more callers sharpen matching and
attract more firms. Case types expand end-to-end (auto, premises, workplace
third-party, med-mal, product liability, wrongful death). SOC 2 Type II.

**H1 2027 — Adjacent verticals, language depth, offline iOS.** The same
audited-intake pattern extends to immigration, family, and employment law — all
multilingual, document-heavy, deadline-critical. 20+ languages via MiniMax + Moss
with no code changes. iOS gains an offline mode (cached state law, checklists, a
local consistency engine) for accident scenes and waiting rooms — HIPAA-respecting,
no sensitive data persisted on device.

**H2 2027 — Category position & white-label.** All 50 states for PI, self-serve
onboarding for any licensed attorney, and white-label for multi-state firms.
North-star: the share of U.S. personal-injury cases that originate through
Caseflowy. **What Stripe is to payments, Caseflowy is to high-stakes legal intake.**

**2028+ — International & standards.** Replicate where multilingual, document-heavy
intake is most underserved (Canada EN/FR, Spain & LATAM, Western Europe).
Open-source the intake schema and the audit-of-claim layer as a spec so any agent
can prove its intake was honest and evidence-grounded — we run the reference
implementation.

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

**AWS** — S3 is the case's system of record, and we use it as the grounding
substrate for the deliverable: every case writes its transcript, parsed
documents, consistency audit, and match result to tiered, KMS-encrypted S3
buckets (sensitive content separated from operational), and the generated case
file — Intake Summary, Demand Letter, and Action Sheet PDFs — is built _from_
those artifacts and written back to the same case prefix, so the firm's
downloadable PDFs are grounded in stored evidence rather than a transient prompt.
AWS Bedrock runs an independent second-opinion: a different model family
re-reviews each flagged discrepancy and votes confirm/refute before it reaches
the firm, so we don't challenge a real caller on a false positive. AWS Comprehend
Medical codes ER discharges to ICD-10, refining injury severity and sharpening the
comparable-settlement query.

---

## Try the demo

There are two ways to experience Caseflowy:

- **As a client** — start a video intake call and describe your accident. The
  agent runs intake in English or Spanish, asks you to hold up any documents to
  the camera, and walks you through to a matched firm.
- **As a firm** — sign in as one of the pre-existing partner law firms to watch
  the firm dashboard light up in real time: live transcript, parsed documents,
  Moss retrieval cards, the consistency audit, case valuation, and the matched
  lead — the audited case file, not just a name and number.

## License

MIT — see [LICENSE](./LICENSE).
