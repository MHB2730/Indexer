"""Find annexure references and their descriptive titles in a main document."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Any quote character we might see — straight ASCII + Word's curly variants.
#   U+0022 "   U+0027 '
#   U+2018 ‘   U+2019 ’
#   U+201C “   U+201D ”
#   U+00AB «   U+00BB »
_QUOTE = r"[\"'‘’“”«»]"

# An annexure "label" is a short alphanumeric tag, e.g.
#   A, B, FA1, AA2, MEK3, 12
_LABEL = r"[A-Z]{1,4}\d{0,3}|\d{1,3}"

# Word + space + (optional opening quote) + label + (optional closing quote)
ANNEXURE_RE = re.compile(
    rf"""
    \b(?:annexure|annexures?|annex|annexe|schedule)\b
    \s+
    {_QUOTE}?\s*(?P<label>{_LABEL})\s*{_QUOTE}?
    """,
    re.IGNORECASE | re.VERBOSE,
)

# "marked 'A'" / "marked "FA1"" — the label is quoted so we require quotes.
MARKED_RE = re.compile(
    rf"""
    \bmarked\b
    \s+
    {_QUOTE}\s*(?P<label>{_LABEL})\s*{_QUOTE}
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Title pattern: "Annexure A: Objection ..." or "Annexure A - Objection ..."
TITLE_RE = re.compile(
    rf"""
    \b(?:annexure|annexures?|annex|annexe|schedule)\b
    \s+
    {_QUOTE}?\s*(?P<label>{_LABEL})\s*{_QUOTE}?
    \s*[:\-–—]\s*
    (?P<title>[^\n\r.;]{{3,120}})
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Characters to strip when normalising a captured label.
_LABEL_STRIPS = "\"'‘’“”«» "


@dataclass
class Reference:
    label: str
    title: str = ""
    mentions: int = 0
    spans: list[tuple[int, int]] = field(default_factory=list)
    context: str = ""   # rich text around each mention — used by matcher


MAX_MENTIONS_FOR_CONTEXT = 5
_SENT_END = re.compile(r"[.;\n\r]")


def _norm(label: str) -> str:
    return label.strip(_LABEL_STRIPS).upper()


def _sentence_around(text: str, span: tuple[int, int]) -> str:
    """Return the single sentence/line containing this match position."""
    s, e = span
    # Walk left to nearest sentence terminator or start of text
    start = s
    while start > 0 and not _SENT_END.match(text[start - 1]):
        start -= 1
    end = e
    while end < len(text) and not _SENT_END.match(text[end]):
        end += 1
    return text[start:end].strip()


def _build_context(text: str, spans: list[tuple[int, int]]) -> str:
    """Concatenate the sentences containing each mention (deduped)."""
    if not spans:
        return ""
    seen: set[str] = set()
    out: list[str] = []
    for span in spans[:MAX_MENTIONS_FOR_CONTEXT]:
        sentence = _sentence_around(text, span)
        if sentence and sentence not in seen:
            seen.add(sentence)
            out.append(sentence)
    return " ".join(out)


def find_references(text: str) -> list[Reference]:
    refs: dict[str, Reference] = {}

    for m in ANNEXURE_RE.finditer(text):
        label = _norm(m.group("label"))
        ref = refs.setdefault(label, Reference(label=label))
        ref.mentions += 1
        ref.spans.append((m.start(), m.end()))

    for m in MARKED_RE.finditer(text):
        label = _norm(m.group("label"))
        ref = refs.setdefault(label, Reference(label=label))
        ref.mentions += 1
        ref.spans.append((m.start(), m.end()))

    for m in TITLE_RE.finditer(text):
        label = _norm(m.group("label"))
        title = m.group("title").strip().rstrip(",;:")
        if label in refs and not refs[label].title:
            refs[label].title = title

    for ref in refs.values():
        ref.context = _build_context(text, ref.spans)

    return sorted(refs.values(), key=lambda r: _sort_key(r.label))


def _sort_key(label: str) -> tuple:
    m = re.match(r"^([A-Z]*)(\d*)$", label)
    if not m:
        return (2, label)
    letters, digits = m.group(1), m.group(2)
    if letters and not digits:
        return (0, letters)
    if digits and not letters:
        return (1, int(digits))
    return (0, letters, int(digits) if digits else 0)
