"""Seed the generated case-file PDFs for the demo cases into S3.

The firm dashboard's "Generated case file" panel previews/downloads
`{case_id}/docs/{doc_type}.{md,pdf}` from S3. Live intakes write these during a
call; this script pre-builds them for the seeded demo cases (lib/demo-cases.ts)
so every demo firm has real, downloadable Intake Summary / Demand Letter /
Action Sheet PDFs — grounded in each case's stored evidence — without a live run.

Usage (from agent-py/):
    # 1. Dump the demo cases the frontend seeds:
    (cd ../frontend && npx tsx -e \
      "import {DEMO_CASES} from './lib/demo-cases.ts'; import {writeFileSync} from 'fs'; \
       writeFileSync('/tmp/demo_cases.json', JSON.stringify(DEMO_CASES))")
    # 2. Generate + upload (macOS needs WeasyPrint's libs on the dyld path):
    DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
      uv run python scripts/seed_demo_documents.py /tmp/demo_cases.json

PDF rendering uses WeasyPrint (system libs: pango/cairo/gdk-pixbuf/harfbuzz —
already present in the agent Docker image; `brew install pango` on macOS).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

from document_generator import generate_document  # noqa: E402
from pii_redaction import RedactionSession  # noqa: E402

DOC_TYPES = ["intake_summary", "demand_letter", "action_sheet"]


async def main(cases_path: str) -> None:
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))
    made = 0
    for case in cases:
        case_id = case["case_id"]
        caller = str(case.get("caller_id") or "")
        for doc_type in DOC_TYPES:
            meta = await generate_document(
                doc_type=doc_type,
                case_id=case_id,
                caller_id=caller,
                case_data=case,
                language=str(case.get("language") or "en"),
                redaction_session=RedactionSession(),
            )
            if meta and meta.get("s3_path_pdf"):
                made += 1
                print(f"OK  {case_id}/{doc_type}  {meta.get('page_count')}p  {meta['s3_path_pdf']}")
            else:
                pdf = meta.get("s3_path_pdf") if meta else None
                print(f"WARN {case_id}/{doc_type} no PDF (pdf={pdf}) — is WeasyPrint set up?")
    print(f"DONE {made} PDFs")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/demo_cases.json"
    asyncio.run(main(path))
