"""Match annexure references against a pool of candidate documents.

Strategy:
  1. Build a BM25 index over the *full text* of every candidate (OCR'd if
     the file is a scan and Tesseract is installed).
  2. For each reference, form a rich query from the surrounding paragraph
     in the main document — not just the title — and run BM25.
  3. Add a date-overlap bonus: any date string (e.g. "12 March 2024",
     "12/03/2024") that appears in BOTH the reference's context and a
     candidate's text is strong evidence.
  4. Add a proper-noun overlap bonus.
  5. Filename fuzzy match contributes lightly (filenames are often garbage
     on real legal pools).

Weights: content 0.55 · dates 0.20 · proper nouns 0.10 · filename 0.15.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi
from rapidfuzz import fuzz

from .parser import matching_text
from .references import Reference


@dataclass
class CandidateScore:
    path: Path
    score: float            # 0..100
    filename_score: float
    content_score: float
    date_overlap: int
    noun_overlap: int
    label_hit: bool


@dataclass
class MatchResult:
    reference: Reference
    ranked: list[CandidateScore]

    @property
    def best(self) -> CandidateScore | None:
        return self.ranked[0] if self.ranked else None

    @property
    def confidence(self) -> str:
        b = self.best
        if not b:
            return "none"
        if b.score >= 70:
            return "high"
        if b.score >= 45:
            return "medium"
        return "low"


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

# Words that contribute no discriminative signal in legal bundles.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "at",
    "for", "with", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "this", "that", "these", "those", "it", "its", "i",
    "we", "he", "she", "they", "them", "his", "her", "their", "our", "my",
    "me", "you", "your", "do", "does", "did", "doing", "has", "have", "had",
    "having", "would", "should", "could", "shall", "will", "may", "might",
    "must", "can", "not", "no", "yes", "so", "if", "then", "than", "such",
    "which", "who", "whom", "whose", "what", "where", "when", "why", "how",
    "all", "any", "some", "each", "every", "other", "another", "same",
    "into", "out", "up", "down", "over", "under", "between", "through",
    # Legal / bundle boilerplate
    "annexure", "annexures", "annex", "annexe", "schedule", "marked",
    "hereto", "herein", "hereof", "hereinafter", "thereof", "thereto",
    "whereof", "wherein", "above", "below", "aforesaid", "respondent",
    "applicant", "plaintiff", "defendant", "honourable", "honorable",
    "court", "affidavit", "founding", "answering", "replying",
    "deponent", "annex", "paragraph", "para", "page", "pages", "see",
    "refer", "reference", "referred", "attached", "copy", "true",
    "correct", "thereof",
}


def _filter_tokens(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]

_DATE_PATTERNS = [
    # 12 March 2024 / 12th March 2024 / March 12, 2024
    re.compile(
        r"\b(?:\d{1,2}(?:st|nd|rd|th)?\s+)?"
        r"(?:january|february|march|april|may|june|july|august|"
        r"september|october|november|december|"
        r"jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)"
        r"(?:\s+\d{1,2}(?:st|nd|rd|th)?)?[,\s]+\d{4}\b",
        re.IGNORECASE,
    ),
    # 12/03/2024, 12-03-24, 2024/03/12
    re.compile(r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b"),
    re.compile(r"\b\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}\b"),
]


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _normalise_date(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _extract_dates(text: str) -> set[str]:
    hits: set[str] = set()
    for pat in _DATE_PATTERNS:
        for m in pat.finditer(text):
            hits.add(_normalise_date(m.group(0)))
    return hits


_NOUN_RE = re.compile(r"\b([A-Z][a-z]{3,}|[A-Z]{3,})\b")
_NOUN_STOP = {
    "The", "This", "That", "These", "Those", "From", "With", "Without",
    "Annexure", "Annex", "Schedule", "Section", "Court", "Honourable",
    "Honorable", "Plaintiff", "Defendant", "Respondent", "Applicant",
    "Affidavit", "Application", "Republic", "South", "Africa", "Notice",
}


def _extract_nouns(text: str) -> set[str]:
    return {m.group(1) for m in _NOUN_RE.finditer(text)} - _NOUN_STOP


@dataclass
class _CandidateIndex:
    path: Path
    filename: str
    text: str
    tokens: list[str]
    dates: set[str]
    nouns: set[str]


def build_index(pool: list[Path]) -> list[_CandidateIndex]:
    out: list[_CandidateIndex] = []
    for p in pool:
        text = matching_text(p)
        out.append(_CandidateIndex(
            path=p,
            filename=p.stem,
            text=text,
            tokens=_filter_tokens(_tokenize(p.stem + " " + text)),
            dates=_extract_dates(text),
            nouns=_extract_nouns(text),
        ))
    return out


def _label_in_text(label: str, text: str) -> bool:
    return re.search(
        rf"(?<![A-Za-z0-9]){re.escape(label)}(?![A-Za-z0-9])",
        text, re.IGNORECASE,
    ) is not None


def _build_query(ref: Reference) -> str:
    """Combine title + context window into a single BM25 query."""
    parts: list[str] = []
    if ref.title:
        parts.append(ref.title)
    if ref.context:
        parts.append(ref.context)
    return " ".join(parts).strip() or f"annexure {ref.label}"


def match_all(refs: list[Reference], pool: list[Path]) -> list[MatchResult]:
    index = build_index(pool)
    corpus = [c.tokens for c in index]
    bm25 = BM25Okapi(corpus) if corpus else None

    results: list[MatchResult] = []
    for ref in refs:
        query = _build_query(ref)
        query_tokens = _filter_tokens(_tokenize(query))
        ref_dates = _extract_dates(query)
        ref_nouns = _extract_nouns(query)

        if bm25 and query_tokens:
            content_scores = bm25.get_scores(query_tokens)
            max_c = max(content_scores) if len(content_scores) else 0.0
        else:
            content_scores = [0.0] * len(index)
            max_c = 0.0

        ranked: list[CandidateScore] = []
        for c, cs in zip(index, content_scores):
            fn_target = ref.title or ref.label
            filename_score = fuzz.token_set_ratio(fn_target.lower(), c.filename.lower())

            content_score = (cs / max_c * 100.0) if max_c > 0 else 0.0

            date_hits = len(ref_dates & c.dates)
            noun_hits = len(ref_nouns & c.nouns)
            # Saturating bonuses
            date_score = min(date_hits, 3) / 3.0 * 100.0
            noun_score = min(noun_hits, 6) / 6.0 * 100.0

            label_hit = _label_in_text(ref.label, c.filename + " " + c.text[:600])

            combined = (
                0.55 * content_score
                + 0.20 * date_score
                + 0.10 * noun_score
                + 0.15 * filename_score
            )
            if label_hit:
                combined = min(100.0, combined + 6.0)

            ranked.append(CandidateScore(
                path=c.path,
                score=round(min(combined, 100.0), 1),
                filename_score=round(filename_score, 1),
                content_score=round(content_score, 1),
                date_overlap=date_hits,
                noun_overlap=noun_hits,
                label_hit=label_hit,
            ))

        ranked.sort(key=lambda x: x.score, reverse=True)
        results.append(MatchResult(reference=ref, ranked=ranked[:8]))

    return results
