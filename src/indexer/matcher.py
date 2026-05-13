"""Match annexure references against a pool of candidate documents.

Strategy (layered, scores combined):
  1. Filename fuzzy match against label + title
  2. BM25 content match against title + surrounding context
  3. Label-token presence bonus (e.g. "FA1" appearing on candidate's first page)

Outputs ranked candidates per reference; caller decides confidence tiers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi
from rapidfuzz import fuzz

from .parser import first_page_text
from .references import Reference


@dataclass
class CandidateScore:
    path: Path
    score: float        # 0..100
    filename_score: float
    content_score: float
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
        if b.score >= 75:
            return "high"
        if b.score >= 50:
            return "medium"
        return "low"


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class _CandidateIndex:
    path: Path
    filename: str
    first_page: str
    tokens: list[str]


def build_index(pool: list[Path]) -> list[_CandidateIndex]:
    out: list[_CandidateIndex] = []
    for p in pool:
        try:
            fp = first_page_text(p)
        except Exception:
            fp = ""
        out.append(_CandidateIndex(
            path=p,
            filename=p.stem,
            first_page=fp,
            tokens=_tokenize(p.stem + " " + fp),
        ))
    return out


def match_all(refs: list[Reference], pool: list[Path]) -> list[MatchResult]:
    index = build_index(pool)
    corpus = [c.tokens for c in index]
    bm25 = BM25Okapi(corpus) if corpus else None

    results: list[MatchResult] = []
    for ref in refs:
        query = f"annexure {ref.label} {ref.title}".strip()
        query_tokens = _tokenize(query)

        # BM25 over content + filename tokens
        if bm25 and query_tokens:
            content_scores = bm25.get_scores(query_tokens)
            max_c = max(content_scores) if len(content_scores) else 0.0
        else:
            content_scores = [0.0] * len(index)
            max_c = 0.0

        ranked: list[CandidateScore] = []
        for c, cs in zip(index, content_scores):
            # Filename fuzzy: token_set is tolerant to ordering and extras
            fn_target = ref.title or ref.label
            filename_score = fuzz.token_set_ratio(fn_target.lower(), c.filename.lower())

            label_hit = _label_in_text(ref.label, c.filename + " " + c.first_page)

            content_score = (cs / max_c * 100.0) if max_c > 0 else 0.0

            combined = (
                0.45 * filename_score
                + 0.45 * content_score
                + (10.0 if label_hit else 0.0)
            )
            ranked.append(CandidateScore(
                path=c.path,
                score=round(min(combined, 100.0), 1),
                filename_score=round(filename_score, 1),
                content_score=round(content_score, 1),
                label_hit=label_hit,
            ))

        ranked.sort(key=lambda x: x.score, reverse=True)
        results.append(MatchResult(reference=ref, ranked=ranked[:5]))

    return results


def _label_in_text(label: str, text: str) -> bool:
    """Check whether label appears as a standalone token in text."""
    pattern = rf"(?<![A-Za-z0-9]){re.escape(label)}(?![A-Za-z0-9])"
    return re.search(pattern, text, re.IGNORECASE) is not None
