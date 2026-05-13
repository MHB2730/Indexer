"""Find annexure references and their descriptive titles in a main document."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Matches: Annexure A, Annexure "FA1", Annexure 'B', Annexure 12, Annex A,
# marked "FA1", marked 'A'.
_LABEL = r"[A-Z]{1,4}\d{0,3}|\d{1,3}"
ANNEXURE_RE = re.compile(
    rf"""(?ix)
    \b
    (?:annexure|annex|schedule)
    \s+
    ["'""]?(?P<label>{_LABEL})["'""]?
    """,
)
MARKED_RE = re.compile(
    rf"""(?ix)
    \bmarked\s+["'""](?P<label>{_LABEL})["'""]
    """,
)

# Title pattern: "Annexure A: Objection ..." or "Annexure A - Objection ..."
TITLE_RE = re.compile(
    rf"""(?ix)
    \b(?:annexure|annex|schedule)\s+
    ["'""]?(?P<label>{_LABEL})["'""]?
    \s*[:\-–—]\s*
    (?P<title>[^\n\r.;]{{3,120}})
    """,
)


@dataclass
class Reference:
    label: str           # normalized, e.g. "A", "FA1", "12"
    title: str = ""      # descriptive title if found
    mentions: int = 0    # number of times referenced
    spans: list[tuple[int, int]] = field(default_factory=list)  # (start, end) in source text


def _norm(label: str) -> str:
    return label.strip().strip("\"'""").upper()


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

    return sorted(refs.values(), key=lambda r: _sort_key(r.label))


def _sort_key(label: str) -> tuple:
    """Sort 'A' < 'B' < 'FA1' < '2' sensibly: letters first alpha, numbers numeric."""
    m = re.match(r"^([A-Z]*)(\d*)$", label)
    if not m:
        return (2, label)
    letters, digits = m.group(1), m.group(2)
    if letters and not digits:
        return (0, letters)
    if digits and not letters:
        return (1, int(digits))
    return (0, letters, int(digits) if digits else 0)
