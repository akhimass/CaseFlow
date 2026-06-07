"""Build the Moss indexes used by the Caseflow voice agent.

Caseflow uses **four separate Moss knowledge indexes** — one per retrieval stream —
plus the per-user ``memory`` index:

* ``state-law``   — jurisdictional PI law primers (SoL, negligence, damages, general)
* ``settlements`` — comparable settlement examples
* ``firms``       — partner law-firm profiles (the curated marketplace inventory)
* ``procedures``  — what-to-do checklists by scenario
* ``memory``      — per-user agentic memory (read+write at runtime, seeded here)

The four knowledge indexes are built from per-entry Markdown files under
``agent-py/knowledge/<index>/*.md``. Each file has YAML-style frontmatter that
becomes the document's Moss metadata, and a body that becomes the document text::

    ---
    id: ca-sol
    state: CA
    topic: sol
    citation: "Cal. Code Civ. Proc. §335.1"
    ---

    California statute of limitations for personal injury...

Moss has no native namespace concept, so each retrieval stream is its own index;
this gives true isolation and lets every legal index use the higher-accuracy
``moss-mediumlm`` embedding model (better for bilingual ES/EN legal text), while
``memory`` stays on the fast default ``moss-minilm``.

Run from the repo root via ``pnpm moss:index`` (which invokes
``uv --directory agent-py run src/create_index.py``) once Moss credentials are set.
Needs ``MOSS_PROJECT_ID`` / ``MOSS_PROJECT_KEY``; without them it exits with a clear
message instead of contacting Moss.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from moss import DocumentInfo, MossClient

# Resolve paths relative to this file so the script works regardless of cwd.
# ``src/create_index.py`` -> parent.parent == agent-py/.
AGENT_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = AGENT_DIR / "knowledge"
ENV_PATH = AGENT_DIR / ".env.local"

# Higher-accuracy embeddings for the legal corpus (bilingual ES/EN, domain nuance).
DEFAULT_KNOWLEDGE_MODEL = "moss-mediumlm"
# Fast default for high-churn per-user memory writes.
DEFAULT_MEMORY_MODEL = "moss-minilm"
DEFAULT_MEMORY_INDEX = "memory"

# Maps each knowledge index to the env var that can override its name. The index
# name defaults to the subdirectory name under knowledge/.
KNOWLEDGE_INDEXES: dict[str, str] = {
    "state-law": "MOSS_STATE_LAW_INDEX",
    "settlements": "MOSS_SETTLEMENTS_INDEX",
    "firms": "MOSS_FIRMS_INDEX",
    "procedures": "MOSS_PROCEDURES_INDEX",
}

load_dotenv(ENV_PATH)


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    """Split a Markdown file into (metadata, body).

    Frontmatter is a leading ``---`` fenced block of ``key: value`` lines. Values
    may be quoted; quotes are stripped. We avoid a YAML dependency on purpose — the
    corpus only uses flat string/number scalars, so a line parser is sufficient and
    has no third-party install cost. All metadata values are coerced to strings
    because Moss stores metadata as strings.
    """
    text = raw.lstrip("﻿")  # tolerate a UTF-8 BOM
    if not text.startswith("---"):
        return {}, text.strip()

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()

    _, front, body = parts
    metadata: dict[str, str] = {}
    for line in front.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip().strip('"').strip("'")
        metadata[key.strip()] = value
    return metadata, body.strip()


def _load_markdown_index(subdir: str) -> list[DocumentInfo]:
    """Load every ``*.md`` entry in ``knowledge/<subdir>/`` into DocumentInfos."""
    directory = KNOWLEDGE_DIR / subdir
    if not directory.is_dir():
        raise FileNotFoundError(f"Knowledge directory not found: {directory}")

    documents: list[DocumentInfo] = []
    for path in sorted(directory.glob("*.md")):
        metadata, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if not body:
            continue
        doc_id = metadata.pop("id", None) or path.stem
        documents.append(
            DocumentInfo(
                id=str(doc_id),
                text=body,
                metadata={str(k): str(v) for k, v in metadata.items()},
            )
        )

    if not documents:
        raise ValueError(f"No Markdown documents found in {directory}.")
    return documents


def _memory_seed_documents() -> list[DocumentInfo]:
    """A single placeholder doc so the memory index exists and loads cleanly.

    The agent's memory tools upsert real per-user documents at runtime. This seed
    is filtered out at query time by its ``user_id``.
    """
    return [
        DocumentInfo(
            id="__seed__",
            text="(memory seed) placeholder document so the memory index can be loaded before the first write.",
            metadata={"user_id": "__seed__"},
        )
    ]


async def _build_one(
    client: MossClient, index_name: str, docs: list[DocumentInfo], model_id: str
) -> None:
    print(
        f"Creating Moss index '{index_name}' ({len(docs)} docs, model '{model_id}')..."
    )
    result = await client.create_index(index_name, docs, model_id)
    print(
        f"  done (job: {result.job_id}, index: {result.index_name}, docs: {result.doc_count})"
    )


async def build_indexes() -> None:
    project_id = os.getenv("MOSS_PROJECT_ID")
    project_key = os.getenv("MOSS_PROJECT_KEY")
    knowledge_model = os.getenv("MOSS_KNOWLEDGE_MODEL_ID", DEFAULT_KNOWLEDGE_MODEL)
    memory_index = os.getenv("MOSS_MEMORY_INDEX_NAME", DEFAULT_MEMORY_INDEX)
    memory_model = os.getenv("MOSS_MEMORY_MODEL_ID", DEFAULT_MEMORY_MODEL)

    missing = [
        name
        for name, value in {
            "MOSS_PROJECT_ID": project_id,
            "MOSS_PROJECT_KEY": project_key,
        }.items()
        if not value
    ]
    if missing:
        raise OSError(
            "Missing required Moss environment variables: "
            + ", ".join(missing)
            + f". Set them in {ENV_PATH} before running this script."
        )

    assert project_id is not None
    assert project_key is not None

    # Load all corpora up front so a content error fails before any network call.
    knowledge_docs = {
        subdir: _load_markdown_index(subdir) for subdir in KNOWLEDGE_INDEXES
    }

    client = MossClient(project_id, project_key)

    for subdir, env_var in KNOWLEDGE_INDEXES.items():
        index_name = os.getenv(env_var, subdir)
        await _build_one(client, index_name, knowledge_docs[subdir], knowledge_model)

    await _build_one(client, memory_index, _memory_seed_documents(), memory_model)

    total = sum(len(docs) for docs in knowledge_docs.values())
    print(
        f"All Moss indexes created: {len(KNOWLEDGE_INDEXES)} knowledge indexes "
        f"({total} docs) + memory. Ready for use."
    )


if __name__ == "__main__":
    asyncio.run(build_indexes())
