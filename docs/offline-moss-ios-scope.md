# On-device Moss legal reference (iOS) — scope & design

**Status:** design / scope only (not built). Owner: native iOS.
**Goal:** Let the iOS app answer a narrow set of legal-reference lookups —
statute-of-limitations (SoL) windows and procedural checklists — *with no
network*, using Moss's on-device search, so the app degrades gracefully when
connectivity drops mid-intake.

## What is and isn't feasible offline

A full intake call is **not** offline-capable and we should not pretend it is.
The live voice loop requires the network end-to-end:

- **STT** (Deepgram nova-3) — cloud
- **Dialogue + consistency LLM** (MiniMax-Text-01 / gateway) — cloud
- **TTS** (MiniMax speech-2.8-hd) — cloud
- **LiveKit** media transport — cloud
- **Unsiloed** document parsing — cloud

What *is* feasible offline is a **read-only legal reference**: deterministic,
small-corpus semantic lookups against a bundled Moss index. This is exactly the
`state-law` and `procedures` corpora we already build for the agent. They are
small (tens of short Markdown docs), change rarely, and contain no PII — ideal to
ship in the app bundle.

Scope this feature as: *"If the network is unavailable, the caller can still ask
‘how long do I have to file in California?’ or ‘what should I do right after a
crash?’ and get an accurate, cited answer from on-device search."*

## Corpus to bundle

Reuse the existing knowledge corpora (no new content authoring):

- `agent-py/knowledge/state-law/*.md` — SoL, negligence rule, damages, general
  primer, per jurisdiction (CA/TX/FL today).
- `agent-py/knowledge/procedures/*.md` — what-to-do checklists by scenario.

Each file already has frontmatter (`state`, `topic`, `citation`, …) that becomes
metadata and a body that becomes the searchable text — see
`agent-py/src/create_index.py` for the exact parse. The on-device index should be
built from the **same files** so the offline answer matches the online one.

Deliberately excluded from the offline bundle: `settlements` (valuation is
advisory and benefits from freshness), `firms` (marketplace inventory changes),
and `memory` (per-user PII — must never be bundled).

## Architecture

```
iOS app (offline)
  └─ MossOfflineReference (new Swift service)
       • on-device Moss index: caseflow-legal.moss  (state-law + procedures)
       • query(text, jurisdiction?) → [LegalSnippet{ text, citation, score }]
  └─ Reachability monitor (NWPathMonitor)
       • online  → existing LiveKit data-channel Moss results (agent-side)
       • offline → MossOfflineReference, surfaced in MossResultsView with an
                   "Offline reference" badge
```

The UI already has `MossResultsView` (renders Moss snippets pushed from the
agent). Offline results render in the same view with a distinct badge so the
caller and any observer can see the source changed, not the quality.

## Build pipeline (index → app bundle)

1. Add a build script `ios/scripts/build_offline_index.py` (or extend
   `create_index.py` with an `--offline-bundle` flag) that:
   - loads `state-law` + `procedures` via the existing `_load_markdown_index`,
   - builds an **on-device** Moss index (Moss SDK supports local/on-device
     indexes per Moss docs — confirm the exact local-index API and the
     embedding model that runs on-device, e.g. `moss-minilm`),
   - serializes it to a file artifact (e.g. `caseflow-legal.moss`).
2. Commit the artifact under `ios/Resources/` (or generate in CI) and add it to
   the Xcode app target's bundled resources.
3. Version the artifact (`legal_index_version` in Info.plist) so we can ship
   corpus updates with app updates and show "reference current as of <date>".

## iOS integration steps

1. Add the Moss Swift/on-device dependency to `Package.swift` (confirm Moss ships
   an Apple-platform target; if Moss is Python-only on-device, fall back to a
   bundled SQLite + a small embedding model via Core ML, or a precomputed
   nearest-neighbor table — see "Open questions").
2. New `Services/MossOfflineReference.swift`:
   - loads `caseflow-legal.moss` from the bundle at launch (lazy),
   - `func lookup(_ query: String, jurisdiction: String?) async -> [LegalSnippet]`
     applying a metadata filter on `state` when a jurisdiction is known.
3. Reachability: add `NWPathMonitor` to `AppState`; expose `isOnline`.
4. In `SessionView` / wherever Moss results are consumed, branch on `isOnline`:
   online keeps the current agent-pushed path; offline calls
   `MossOfflineReference.lookup(...)` and maps to the same display model in
   `MossResultsView` with an "Offline reference" badge.
5. Add a manual offline-mode toggle in debug builds for demo reliability.

## Guardrails / correctness

- Offline answers are **reference only** — never a quote of case value, never a
  promise. Keep the same disclaimer copy as online.
- Always show the `citation` metadata with the snippet so an offline SoL answer
  is verifiable (e.g. "Cal. Code Civ. Proc. §335.1").
- If the on-device top score is below a threshold, say "I can't answer that
  offline — let's revisit when you're back online" rather than guessing.

## Open questions to resolve before building

1. **Does Moss expose an on-device/local index API on Apple platforms?** AGENTS.md
   says Moss has "on-device AI capabilities"; confirm the Swift surface and which
   embedding model runs locally. If there is no Apple target, choose the fallback
   (Core ML MiniLM embeddings + bundled vectors) — same corpus, different runtime.
2. On-device index size and cold-load time budget (target < 50 ms query, < 1 s
   load) for the small legal corpus.
3. Corpus refresh cadence — ship with app updates vs. a signed background
   download when online (keeping the offline copy as the floor).

## Estimate

- Build pipeline + bundled artifact: ~0.5 day
- `MossOfflineReference` + reachability + UI branch: ~1 day
- Polish, badge, threshold/disclaimer, debug toggle: ~0.5 day

~2 days for one native iOS engineer, contingent on Open Question #1.
