# Caseflowy — pitch notes

## The one-liner

Caseflowy is a multilingual video intake agent for personal injury. A Spanish- or
English-speaking caller video-calls our agent, which runs intake in their
language, parses documents they hold to the camera, retrieves comparable
settlements and the statute of limitations live via Moss, catches discrepancies
between their account and their evidence, values the case, and matches them to a
firm — delivering an audited case file, not just a lead.

## Why the demo is an auto rear-end

Our demo today is an auto rear-end because it's the most common PI case and the
most demo-friendly. But Caseflowy handles the full PI vertical — slip-and-fall,
dog bites, premises liability, medical malpractice, workplace third-party
injuries, and wrongful death. Our knowledge base covers state law across these
types in California, Texas, and Florida, and the intake flow adapts to the case
type within the same conversational structure. We show one path, rehearsed
perfectly; the product is already broad.

## Firm matching scales beyond our seed list

For firm matching, we seed our marketplace with partner firms, but Moss's
semantic search means we can match against any firm directory — State Bar
listings, Avvo, Martindale — as soon as we ingest it. The matching engine is
data-agnostic: it correlates the case profile (type, jurisdiction, language,
severity) against firm specialties. Today we show a handful of partner firms; in
production, that's thousands.

## The discrepancy moment (the heart)

Maria says the other driver ran the red light; the police report says fault
undetermined. The agent catches this mid-conversation and asks a gentle
clarifying question in Spanish — then an independent second model on AWS Bedrock
re-checks the finding before it reaches the firm. That's the difference between a
lead and an audited case file.

## Sponsor stack in one breath

LiveKit (video + agent), MiniMax (Spanish/English voice + dialogue LLM), Moss
(four-stream live retrieval — the bottleneck this hackathon is about), Unsiloed
(live document parsing + schema extraction), TrueFoundry (single governed model
gateway + audit), AWS (S3 case artifacts, Bedrock second-opinion, Comprehend
Medical ICD-10). See the root README for how we built on top of each.
