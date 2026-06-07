"""PII redaction — regex-based, bilingual, in-memory mapping only."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

Category = Literal[
    "phone",
    "email",
    "name",
    "address",
    "license_plate",
    "ssn",
    "policy_number",
    "bank_account",
    "credit_card",
]

ALL_CATEGORIES: tuple[Category, ...] = (
    "phone",
    "email",
    "name",
    "address",
    "license_plate",
    "ssn",
    "policy_number",
    "bank_account",
    "credit_card",
)

SPANISH_GIVEN_NAMES = frozenset(
    {
        "maria",
        "jose",
        "josé",
        "juan",
        "carlos",
        "ana",
        "luis",
        "luisa",
        "pedro",
        "rosa",
        "miguel",
        "elena",
        "jorge",
        "fernando",
        "guadalupe",
        "alejandro",
        "patricia",
        "ricardo",
        "sofia",
        "sofía",
        "diego",
        "carmen",
        "antonio",
        "manuel",
        "francisco",
        "jesus",
        "jesús",
        "rafael",
        "angel",
        "ángel",
        "gabriela",
        "alejandra",
    }
)

ENGLISH_GIVEN_NAMES = frozenset(
    {
        "john",
        "jane",
        "mary",
        "james",
        "robert",
        "michael",
        "sarah",
        "david",
        "linda",
        "maria",
        "jennifer",
        "william",
        "elizabeth",
        "richard",
        "susan",
    }
)

# Operational field names — values still scanned for embedded PII patterns.
PII_FIELD_NAMES = frozenset(
    {
        "caller_name",
        "name",
        "phone",
        "consumer_phone",
        "email",
        "address",
        "street",
        "street_address",
        "home_address",
        "mailing_address",
        "policy_number",
        "insurance_policy",
        "ssn",
        "social_security",
    }
)


@dataclass
class RedactionHit:
    category: Category
    placeholder: str
    original: str


@dataclass
class RedactionSession:
    """Per-call in-memory mapping. Never persist this object."""

    mapping: dict[str, str] = field(default_factory=dict)
    reverse: dict[str, str] = field(default_factory=dict)
    counts_by_category: dict[str, int] = field(default_factory=dict)
    total_redactions: int = 0

    def merge_mapping(self, new_map: dict[str, str]) -> list[RedactionHit]:
        hits: list[RedactionHit] = []
        for placeholder, original in new_map.items():
            if placeholder in self.mapping:
                continue
            self.mapping[placeholder] = original
            self.reverse[original] = placeholder
            category = _category_from_placeholder(placeholder)
            self.counts_by_category[category] = (
                self.counts_by_category.get(category, 0) + 1
            )
            self.total_redactions += 1
            hits.append(
                RedactionHit(category=category, placeholder=placeholder, original=original)
            )
        return hits

    def audit_payload(self, *, model: str, case_id: str = "") -> dict[str, Any]:
        return {
            "event_type": "pii_redaction",
            "case_id": case_id,
            "model": model,
            "redaction_count": self.total_redactions,
            "categories": dict(self.counts_by_category),
        }


def _category_from_placeholder(placeholder: str) -> Category:
    token = placeholder.strip("[]").replace("CF_", "").rsplit("_", 1)[0].lower()
    alias = {
        "phone": "phone",
        "email": "email",
        "name": "name",
        "address": "address",
        "plate": "license_plate",
        "license": "license_plate",
        "ssn": "ssn",
        "policy": "policy_number",
        "bank": "bank_account",
        "card": "credit_card",
    }
    for key, cat in alias.items():
        if token.startswith(key):
            return cat  # type: ignore[return-value]
    return "name"


class Redactor:
    def __init__(self, session: RedactionSession | None = None) -> None:
        self._session = session or RedactionSession()
        self._counters: dict[Category, int] = {c: 0 for c in ALL_CATEGORIES}

    @property
    def session(self) -> RedactionSession:
        return self._session

    def _next_placeholder(self, category: Category) -> str:
        self._counters[category] += 1
        label = {
            "phone": "PHONE",
            "email": "EMAIL",
            "name": "NAME",
            "address": "ADDRESS",
            "license_plate": "PLATE",
            "ssn": "SSN",
            "policy_number": "POLICY",
            "bank_account": "BANK",
            "credit_card": "CARD",
        }[category]
        return f"[CF_{label}_{self._counters[category]}]"

    def redact(self, text: str, language: str = "en") -> tuple[str, dict[str, str]]:
        if not text:
            return text, {}

        local_map: dict[str, str] = {}
        redacted = text

        patterns: list[tuple[Category, re.Pattern[str]]] = [
            (
                "credit_card",
                re.compile(r"\b(?:\d[ -]?){13,19}\b"),
            ),
            (
                "ssn",
                re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            ),
            (
                "email",
                re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
            ),
            (
                "phone",
                re.compile(
                    r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)"
                    r"|(?<!\d)\+\d{1,3}[-.\s]?\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}(?!\d)"
                ),
            ),
            (
                "policy_number",
                re.compile(
                    r"\b(?:policy|poliza|póliza|claim)\s*(?:#|no\.?|number)?\s*[:\-]?\s*[A-Z0-9]{6,}\b",
                    re.I,
                ),
            ),
            (
                "license_plate",
                re.compile(r"\b[A-Z0-9]{2,3}[-\s]?[A-Z0-9]{3,4}\b"),
            ),
            (
                "bank_account",
                re.compile(r"\b(?:account|cuenta)\s*(?:#|no\.?)?\s*[:\-]?\s*\d{8,17}\b", re.I),
            ),
            (
                "address",
                re.compile(
                    r"\b\d{1,5}\s+(?:[A-Za-záéíóúñ]+\s+){1,4}"
                    r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|"
                    r"Calle|Avenida|Av|Boulevard|Camino|Paseo)\b\.?",
                    re.I,
                ),
            ),
        ]

        for category, pattern in patterns:
            redacted = self._sub_matches(redacted, pattern, category, local_map)

        redacted = self._redact_names(redacted, language, local_map)

        self._session.merge_mapping(local_map)
        return redacted, local_map

    def _sub_matches(
        self,
        text: str,
        pattern: re.Pattern[str],
        category: Category,
        local_map: dict[str, str],
    ) -> str:
        def repl(match: re.Match[str]) -> str:
            original = match.group(0)
            if original in self._session.reverse:
                return self._session.reverse[original]
            for ph, val in local_map.items():
                if val == original:
                    return ph
            placeholder = self._next_placeholder(category)
            local_map[placeholder] = original
            return placeholder

        return pattern.sub(repl, text)

    def _redact_names(
        self, text: str, language: str, local_map: dict[str, str]
    ) -> str:
        names = SPANISH_GIVEN_NAMES if language.lower().startswith("es") else ENGLISH_GIVEN_NAMES
        names = names | SPANISH_GIVEN_NAMES | ENGLISH_GIVEN_NAMES

        def repl_cap(match: re.Match[str]) -> str:
            first, last = match.group(1), match.group(2)
            if first.lower() not in names and last.lower() not in names:
                return match.group(0)
            original = f"{first} {last}"
            if original in self._session.reverse:
                return self._session.reverse[original]
            for ph, val in local_map.items():
                if val == original:
                    return ph
            placeholder = self._next_placeholder("name")
            local_map[placeholder] = original
            return placeholder

        text = re.sub(
            r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\b",
            repl_cap,
            text,
        )

        def repl_given(match: re.Match[str]) -> str:
            word = match.group(0)
            if word.lower() not in names:
                return word
            if word in self._session.reverse:
                return self._session.reverse[word]
            for ph, val in local_map.items():
                if val == word:
                    return ph
            placeholder = self._next_placeholder("name")
            local_map[placeholder] = word
            return placeholder

        return re.sub(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\b", repl_given, text)

    def unredact(self, text: str, mapping: dict[str, str] | None = None) -> str:
        merged = {**self._session.mapping, **(mapping or {})}
        if not merged or not text:
            return text
        # Longest placeholders first to avoid partial replacements.
        for placeholder in sorted(merged, key=len, reverse=True):
            text = text.replace(placeholder, merged[placeholder])
        return text


def redact_messages(
    messages: list[dict[str, str]],
    *,
    session: RedactionSession,
    language: str = "en",
    model: str = "gateway",
) -> list[dict[str, str]]:
    redactor = Redactor(session)
    out: list[dict[str, str]] = []
    for msg in messages:
        content = msg.get("content", "")
        redacted, _ = redactor.redact(content, language)
        out.append({**msg, "content": redacted})
    return out


def redact_json_values(
    value: Any,
    *,
    session: RedactionSession,
    language: str = "en",
) -> Any:
    redactor = Redactor(session)
    if isinstance(value, str):
        redacted, _ = redactor.redact(value, language)
        return redacted
    if isinstance(value, list):
        return [redact_json_values(v, session=session, language=language) for v in value]
    if isinstance(value, dict):
        return {
            k: redact_json_values(v, session=session, language=language)
            for k, v in value.items()
        }
    return value


def moss_field_value(field_name: str, value: str, *, session: RedactionSession, language: str) -> str:
    redactor = Redactor(session)
    if field_name.lower() in PII_FIELD_NAMES:
        redacted, _ = redactor.redact(value, language)
        return redacted
    redacted, _ = redactor.redact(value, language)
    return redacted


def sensitive_blob(case_id: str, case_data: dict[str, Any], session: RedactionSession) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "case_data": case_data,
        "mapping": session.mapping,
        "redaction_stats": session.counts_by_category,
    }


def dumps_redacted(payload: Any) -> str:
    return json.dumps(payload, default=str, ensure_ascii=False)
