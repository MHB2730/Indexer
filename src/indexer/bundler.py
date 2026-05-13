"""Assemble the output bundle.

Produces, in `out_dir`:
  * <NN>_Annexure <Label> - <Title>.<ext>   — copied & renamed annexures
  * index.pdf                                — index with bundle page numbers
  * main_annotated.pdf                       — main doc with bundle-page refs
  * bundle.pdf                               — single merged bundle (index +
                                               main + all annexures), every
                                               page numbered, each annexure's
                                               first page stamped with its
                                               label.
  * report.json                              — match decisions & paths
"""
from __future__ import annotations

import json
import math
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz  # PyMuPDF

from .matcher import MatchResult


# ── data ──────────────────────────────────────────────────────────

@dataclass
class BundleEntry:
    sequence: int
    label: str
    title: str
    source: str
    output_name: str
    confidence: str
    score: float
    bundle_page: int = 0      # 1-indexed page where this annexure starts
    page_count: int = 0


NAVY = (0.122, 0.227, 0.373)         # #1F3A5F
GOLD = (0.718, 0.475, 0.122)         # #B7791F
MUTED = (0.42, 0.45, 0.50)


# ── public API ────────────────────────────────────────────────────

def assemble(
    matches: list[MatchResult],
    main_doc: Path,
    out_dir: Path,
    auto_confidence: str = "high",
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    tiers = {"high": 3, "medium": 2, "low": 1, "none": 0}
    threshold = tiers[auto_confidence]

    entries: list[BundleEntry] = []
    unresolved: list[dict] = []

    seq = 0
    for mr in matches:
        ref = mr.reference
        best = mr.best
        if not best or tiers[mr.confidence] < threshold:
            unresolved.append({
                "label": ref.label,
                "title": ref.title,
                "confidence": mr.confidence,
                "candidates": [
                    {"path": str(c.path), "score": c.score} for c in mr.ranked[:3]
                ],
            })
            continue

        seq += 1
        out_name = _output_filename(seq, ref.label, ref.title, best.path)
        dest = out_dir / out_name
        shutil.copy2(best.path, dest)
        entries.append(BundleEntry(
            sequence=seq,
            label=ref.label,
            title=ref.title,
            source=str(best.path),
            output_name=out_name,
            confidence=mr.confidence,
            score=best.score,
        ))

    # Side-effect: assigns bundle_page + page_count on each entry so
    # the index + merged bundle carry accurate page numbers.
    _plan_layout(main_doc, entries, out_dir)

    index_path = out_dir / "index.pdf"
    _write_index_pdf(entries, index_path)

    main_annotated = out_dir / "main_annotated.pdf"
    _annotate_main(main_doc, entries, main_annotated)

    bundle_path = out_dir / "bundle.pdf"
    _build_merged_bundle(
        index_path=index_path,
        main_pdf=main_annotated if main_doc.suffix.lower() == ".pdf" else None,
        entries=entries,
        out_dir=out_dir,
        bundle_path=bundle_path,
    )

    report = {
        "main_doc": str(main_doc),
        "out_dir": str(out_dir),
        "bundle_pdf": str(bundle_path) if bundle_path.exists() else None,
        "entries": [asdict(e) for e in entries],
        "unresolved": unresolved,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    return report


# ── filenames ─────────────────────────────────────────────────────

def _safe(text: str, max_len: int = 60) -> str:
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]", " ", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:max_len].rstrip(" .")


def _output_filename(seq: int, label: str, title: str, src: Path) -> str:
    title_part = f" - {_safe(title)}" if title else ""
    return f"{seq:02d}_Annexure {label}{title_part}{src.suffix.lower()}"


# ── layout planning ───────────────────────────────────────────────

def _pdf_page_count(path: Path) -> int:
    try:
        with fitz.open(path) as d:
            return d.page_count
    except Exception:
        return 1


def _estimated_index_pages(entry_count: int) -> int:
    # 38 entry lines per page after header
    return max(1, math.ceil((entry_count + 4) / 38))


def _plan_layout(main_doc: Path, entries: list[BundleEntry], out_dir: Path) -> dict:
    """Compute starting bundle page for each component."""
    index_pages = _estimated_index_pages(len(entries))
    if main_doc.suffix.lower() == ".pdf":
        main_pages = _pdf_page_count(main_doc)
    else:
        main_pages = 0  # DOCX excluded from merged bundle

    cursor = 1
    index_start = cursor
    cursor += index_pages
    main_start = cursor
    cursor += main_pages

    for e in entries:
        src_pdf = out_dir / e.output_name
        if src_pdf.suffix.lower() != ".pdf":
            e.page_count = 0
            e.bundle_page = 0
            continue
        e.page_count = _pdf_page_count(src_pdf)
        e.bundle_page = cursor
        cursor += e.page_count

    total_pages = cursor - 1
    return {
        "index_pages": index_pages,
        "index_start": index_start,
        "main_pages": main_pages,
        "main_start": main_start,
        "total_pages": total_pages,
    }


# ── index ─────────────────────────────────────────────────────────

def _write_index_pdf(entries: list[BundleEntry], path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    margin = 56
    page.insert_text((margin, 70), "INDEX", fontsize=22, fontname="helv",
                     color=NAVY, render_mode=0)
    page.insert_text((margin, 92), "Bundle of documents",
                     fontsize=11, fontname="helv", color=MUTED)
    page.draw_line((margin, 108), (page.rect.width - margin, 108),
                   color=NAVY, width=1.2)

    y = 132
    line_height = 18
    for e in entries:
        if y > page.rect.height - 60:
            page = doc.new_page()
            y = 70

        label_text = f"Annexure {e.label}"
        page.insert_text((margin, y), label_text, fontsize=11,
                         fontname="hebo", color=NAVY)

        title = e.title or ""
        title_x = margin + 110
        page.insert_text((title_x, y), title, fontsize=11,
                         fontname="helv", color=(0.12, 0.13, 0.15))

        # Right-aligned bundle page number
        page_str = str(e.bundle_page) if e.bundle_page else "—"
        page_width = fitz.get_text_length(page_str, fontname="helv", fontsize=11)
        page.insert_text((page.rect.width - margin - page_width, y),
                         page_str, fontsize=11, fontname="helv", color=NAVY)
        y += line_height

    doc.save(path)
    doc.close()


# ── main doc annotation ───────────────────────────────────────────

_LABEL_PATTERN = re.compile(
    r"""(?ix)
    \b(?:annexure|annex|schedule)\s+
    ["'“”‘’]?
    ([A-Z]{1,4}\d{0,3}|\d{1,3})
    ["'“”‘’]?
    """
)


def _annotate_main(main_doc: Path, entries: list[BundleEntry], out_path: Path) -> None:
    """Highlight references and append a [Bundle p.N] tag next to each."""
    if main_doc.suffix.lower() != ".pdf":
        shutil.copy2(main_doc, out_path)
        return

    by_label = {e.label.upper(): e for e in entries}
    doc = fitz.open(main_doc)

    for page in doc:
        text = page.get_text("text")
        for m in _LABEL_PATTERN.finditer(text):
            label = m.group(1).upper()
            entry = by_label.get(label)
            if not entry or not entry.bundle_page:
                continue
            quads = page.search_for(m.group(0))
            for q in quads:
                annot = page.add_highlight_annot(q)
                annot.set_info(content=f"Bundle p.{entry.bundle_page}")
                annot.update()
                # Insert a small bracketed page tag right after the match
                tag = f"  [Bundle p.{entry.bundle_page}]"
                page.insert_text(
                    (q.x1 + 2, q.y1 - 1),
                    tag,
                    fontsize=8,
                    fontname="hebo",
                    color=GOLD,
                )

    doc.save(out_path)
    doc.close()


# ── annexure stamping & merged bundle ─────────────────────────────

def _stamp_annexure_header(doc: fitz.Document, label: str) -> None:
    """Stamp 'ANNEXURE <label>' badge on the first page top-right."""
    if doc.page_count == 0:
        return
    page = doc[0]
    text = f"ANNEXURE {label}"
    fontsize = 13
    pad_x, pad_y = 10, 6
    width = fitz.get_text_length(text, fontname="hebo", fontsize=fontsize) + 2 * pad_x
    height = fontsize + 2 * pad_y
    x1 = page.rect.width - 28
    y0 = 28
    rect = fitz.Rect(x1 - width, y0, x1, y0 + height)
    page.draw_rect(rect, color=NAVY, fill=NAVY, width=0)
    page.insert_text(
        (rect.x0 + pad_x, rect.y0 + pad_y + fontsize - 2),
        text,
        fontsize=fontsize,
        fontname="hebo",
        color=(1.0, 1.0, 1.0),
    )


def _stamp_bundle_page_numbers(doc: fitz.Document, total: int) -> None:
    for i, page in enumerate(doc, 1):
        text = f"{i} / {total}"
        fontsize = 9
        w = fitz.get_text_length(text, fontname="helv", fontsize=fontsize)
        x = (page.rect.width - w) / 2
        y = page.rect.height - 24
        page.insert_text((x, y), text, fontsize=fontsize, fontname="helv",
                         color=MUTED)


def _build_merged_bundle(
    index_path: Path,
    main_pdf: Path | None,
    entries: list[BundleEntry],
    out_dir: Path,
    bundle_path: Path,
) -> None:
    """Concatenate index + main + each annexure into one PDF.

    Annexure first pages get a label stamp. Final bundle gets continuous
    page numbers at the bottom centre.
    """
    bundle = fitz.open()

    # Index
    if index_path.exists():
        with fitz.open(index_path) as d:
            bundle.insert_pdf(d)

    # Main doc (only if PDF)
    if main_pdf and main_pdf.exists():
        with fitz.open(main_pdf) as d:
            bundle.insert_pdf(d)

    # Annexures (stamp header first)
    for e in entries:
        src = out_dir / e.output_name
        if src.suffix.lower() != ".pdf":
            continue
        with fitz.open(src) as d:
            _stamp_annexure_header(d, e.label)
            bundle.insert_pdf(d)

    # Now stamp continuous page numbers across the whole bundle
    total = bundle.page_count
    _stamp_bundle_page_numbers(bundle, total)

    bundle.save(bundle_path)
    bundle.close()
