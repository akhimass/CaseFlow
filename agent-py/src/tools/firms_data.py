from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_FIRMS_PATH = _REPO_ROOT / "kb" / "firms.json"


def load_firms() -> list[dict[str, Any]]:
    with _FIRMS_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("kb/firms.json must be a list")
    return data
