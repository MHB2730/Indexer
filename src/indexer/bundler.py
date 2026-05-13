"""Assemble the output bundle.

Produces, in `out_dir`:
  * <NN>_Annexure <Label> - <Title>.<ext>   — copied & renamed annexures
  * index.pdf                                — tabled standalone index
  * main_annotated.pdf                       — main doc with bundle-page refs
  * bundle.pdf                               — single merged court bundle:
        Cover page → tabled Index → Main document → each Annexure (stamped)
        with continuous bottom-centre page numbers, PDF bookmarks (TOC),
        and clickable links from the Index entries to the annexure pages.
  * report.json                              — match decisions & paths
"""
from __future__ import annotations

import json
import logging
import math
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz  # PyMuPDF

from .matcher import MatchResult

log = logging.getLogger(__name__)


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
    page_count: int = 0
    # Page numbering is annexure-relative: Annexure A starts at page 1.
    start_page: int = 0     # 1-based page within the annexure section
    end_page: int = 0
    # Where this annexure begins inside the merged bundle PDF (1-based).
    bundle_page: int = 0


# Brand palette (PyMuPDF expects 0..1 RGB tuples)
NAVY = (0.122, 0.227, 0.373)         # #1F3A5F
NAVY_DARK = (0.055, 0.133, 0.220)    # #0E2238
GOLD = (0.718, 0.475, 0.122)         # #B7791F
WHITE = (1.0, 1.0, 1.0)
INK = (0.06, 0.09, 0.16)
MUTED = (0.42, 0.45, 0.50)
LINE = (0.86, 0.88, 0.91)


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
    log.info("assemble: main=%s pool_matches=%d out=%s",
             main_doc.name, len(matches), out_dir)

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

    # Convert DOCX main → PDF so the merged bundle can include it.
    main_pdf, temp_pdf = _ensure_main_pdf(main_doc)
    try:
        # Plan now assigns each entry a 1-based annexure-relative start_page
        # (Annexure A = 1) and end_page. The index uses those.
        _plan_layout(main_pdf, entries, out_dir)

        standalone_index = out_dir / "index.pdf"
        _write_index_pdf(entries, standalone_index)

        main_annotated = out_dir / "main_annotated.pdf"
        _annotate_main(main_pdf, entries, main_annotated)

        bundle_path = out_dir / "bundle.pdf"
        _build_merged_bundle(
            entries=entries,
            main_pdf=main_annotated if main_pdf else None,
            out_dir=out_dir,
            bundle_path=bundle_path,
        )
    finally:
        if temp_pdf and temp_pdf.exists():
            try:
                temp_pdf.unlink()
            except OSError:
                pass

    report = {
        "main_doc": str(main_doc),
        "out_dir": str(out_dir),
        "bundle_pdf": str(bundle_path) if bundle_path.exists() else None,
        "entries": [asdict(e) for e in entries],
        "unresolved": unresolved,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    log.info("assemble: wrote %d entries, %d unresolved", len(entries), len(unresolved))
    return report


# ── filenames ─────────────────────────────────────────────────────

def _safe(text: str, max_len: int = 60) -> str:
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]", " ", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:max_len].rstrip(" .")


def _output_filename(seq: int, label: str, title: str, src: Path) -> str:
    title_part = f" - {_safe(title)}" if title else ""
    return f"{seq:02d}_Annexure {label}{title_part}{src.suffix.lower()}"


# ── DOCX → PDF ────────────────────────────────────────────────────

def _ensure_main_pdf(main_doc: Path) -> tuple[Path | None, Path | None]:
    """Return (pdf_path, temp_to_clean). For DOCX, convert via Word/COM.

    On systems without Word installed, falls back to returning (None, None)
    — the merged bundle will skip the main document.
    """
    if main_doc.suffix.lower() == ".pdf":
        return main_doc, None
    if main_doc.suffix.lower() not in {".docx", ".doc"}:
        return None, None
    try:
        from docx2pdf import convert
    except ImportError:
        log.warning("docx2pdf not installed; main doc excluded from merged bundle")
        return None, None
    out = Path(tempfile.gettempdir()) / f"indexer-main-{main_doc.stem}.pdf"
    if out.exists():
        out.unlink()
    try:
        # Initialise COM for this thread — required when called from a
        # PySide6 worker thread.
        try:
            import pythoncom  # type: ignore
            pythoncom.CoInitialize()
            cleanup_com = True
        except ImportError:
            cleanup_com = False
        try:
            convert(str(main_doc), str(out))
        finally:
            if cleanup_com:
                pythoncom.CoUninitialize()
    except Exception as e:
        log.warning("DOCX → PDF conversion failed (%s); main doc excluded", e)
        return None, None
    return (out, out) if out.exists() else (None, None)


# ── layout planning ───────────────────────────────────────────────

def _pdf_page_count(path: Path) -> int:
    try:
        with fitz.open(path) as d:
            return d.page_count
    except Exception:
        return 1


# Entries per index page (after subtracting the header rows on each page)
_INDEX_ROWS_FIRST_PAGE = 30
_INDEX_ROWS_NEXT_PAGE = 36


def _estimated_index_pages(entry_count: int) -> int:
    if entry_count <= _INDEX_ROWS_FIRST_PAGE:
        return 1
    return 1 + math.ceil(
        (entry_count - _INDEX_ROWS_FIRST_PAGE) / _INDEX_ROWS_NEXT_PAGE
    )


def _plan_layout(main_pdf: Path | None, entries: list[BundleEntry], out_dir: Path) -> dict:
    """Plan the merged bundle.

    Layout: Index → Main Document (if PDF) → Annexure A → Annexure B → …

    Page numbering is annexure-relative: Annexure A starts at page 1. The
    index and main document pages are NOT numbered — they're navigation
    rather than substantive content.
    """
    index_pages = _estimated_index_pages(len(entries))
    main_pages = _pdf_page_count(main_pdf) if main_pdf else 0

    cursor = 1
    index_start = cursor
    cursor += index_pages
    main_start = cursor
    cursor += main_pages
    annex_start_bundle = cursor

    annex_page = 1   # annexure-relative numbering
    for e in entries:
        src_pdf = out_dir / e.output_name
        if src_pdf.suffix.lower() != ".pdf":
            e.page_count = 0
            e.bundle_page = 0
            e.start_page = 0
            e.end_page = 0
            continue
        e.page_count = _pdf_page_count(src_pdf)
        e.bundle_page = cursor
        e.start_page = annex_page
        e.end_page = annex_page + e.page_count - 1
        cursor += e.page_count
        annex_page += e.page_count

    return {
        "index_start": index_start, "index_pages": index_pages,
        "main_start": main_start, "main_pages": main_pages,
        "annex_start_bundle": annex_start_bundle,
        "total_pages": cursor - 1,
    }


# ── Index ─────────────────────────────────────────────────────────

_ROW_H = 26
_MARGIN = 56
_PAGE_COL_WIDTH = 100   # right-hand column reserved for "Pages 1 - 5"


def _draw_index_header(page: fitz.Page, top_y: float) -> float:
    """Draw 'Index' title plus a thin rule. Returns the y where rows start."""
    page.insert_text((_MARGIN, top_y + 26), "Index",
                     fontsize=24, fontname="hebo", color=NAVY_DARK)
    rule_y = top_y + 40
    page.draw_line((_MARGIN, rule_y), (page.rect.width - _MARGIN, rule_y),
                   color=NAVY, width=1.2)
    return rule_y + 18


def _truncate_to_fit(text: str, fontname: str, fontsize: int, max_width: float) -> str:
    if fitz.get_text_length(text, fontname=fontname, fontsize=fontsize) <= max_width:
        return text
    while text and fitz.get_text_length(text + "…", fontname=fontname,
                                        fontsize=fontsize) > max_width:
        text = text[:-1]
    return text + "…"


def _format_pages(e: BundleEntry) -> str:
    if not e.start_page:
        return "—"
    if e.start_page == e.end_page:
        return f"Page {e.start_page}"
    return f"Pages {e.start_page} – {e.end_page}"


def _write_index_pdf(
    entries: list[BundleEntry],
    path: Path,
) -> list[tuple[int, fitz.Rect, int]]:
    """Render the index into `path`.

    Each row: 'Annexure X: Title'  ............  Pages N – M
    Returns (index_page_idx, row_rect, target_bundle_page) tuples so the
    caller can install clickable links once the merged bundle exists.
    """
    doc = fitz.open()
    pending_links: list[tuple[int, fitz.Rect, int]] = []

    page = doc.new_page()
    y = _draw_index_header(page, top_y=_MARGIN)
    rows_on_this_page = 0
    max_rows = _INDEX_ROWS_FIRST_PAGE

    for e in entries:
        if rows_on_this_page >= max_rows:
            page = doc.new_page()
            y = _draw_index_header(page, top_y=_MARGIN)
            rows_on_this_page = 0
            max_rows = _INDEX_ROWS_NEXT_PAGE

        row_rect = fitz.Rect(_MARGIN, y, page.rect.width - _MARGIN, y + _ROW_H)

        # Build the row text — annexure label, title, dot leader, page range.
        label_text = f"Annexure {e.label}"
        title_text = f": {e.title}" if e.title else ""
        page_text = _format_pages(e)

        # Page text (right-aligned within fixed-width right column)
        right_col_x = row_rect.x1 - _PAGE_COL_WIDTH
        page_w = fitz.get_text_length(page_text, fontname="helv", fontsize=12)
        page_y = y + (_ROW_H + 12) / 2 - 3
        page.insert_text((row_rect.x1 - page_w, page_y),
                         page_text, fontsize=12, fontname="helv", color=NAVY)

        # Left text: "Annexure X" bold + ": Title" regular, truncated to fit
        max_left_width = right_col_x - row_rect.x0 - 16   # 16 = gap before page col
        baseline_y = page_y
        label_w = fitz.get_text_length(label_text, fontname="hebo", fontsize=12)
        page.insert_text((row_rect.x0, baseline_y), label_text,
                         fontsize=12, fontname="hebo", color=NAVY)
        remaining = max_left_width - label_w
        if title_text and remaining > 30:
            shown_title = _truncate_to_fit(title_text, "helv", 12, remaining)
            page.insert_text((row_rect.x0 + label_w, baseline_y),
                             shown_title, fontsize=12, fontname="helv", color=INK)

        # Subtle bottom rule
        page.draw_line((row_rect.x0, row_rect.y1 - 2),
                       (row_rect.x1, row_rect.y1 - 2),
                       color=LINE, width=0.4)

        if e.bundle_page:
            pending_links.append((doc.page_count - 1, fitz.Rect(row_rect), e.bundle_page))

        y += _ROW_H
        rows_on_this_page += 1

    doc.save(path)
    doc.close()
    return pending_links


# ── main doc annotation ───────────────────────────────────────────

_LABEL_PATTERN = re.compile(
    r"""
    \b(?:annexure|annexures?|annex|annexe|schedule)\b
    \s+
    [\"'‘’“”«»]?\s*([A-Z]{1,4}\d{0,3}|\d{1,3})\s*[\"'‘’“”«»]?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _annotate_main(main_pdf: Path | None, entries: list[BundleEntry],
                   out_path: Path) -> None:
    if not main_pdf or main_pdf.suffix.lower() != ".pdf":
        # No PDF main doc → produce an empty placeholder so the merge step
        # remains uniform. Caller decides whether to include it.
        return
    by_label = {e.label.upper(): e for e in entries}
    doc = fitz.open(main_pdf)
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
                tag = f"  [Bundle p.{entry.bundle_page}]"
                page.insert_text((q.x1 + 2, q.y1 - 1), tag,
                                 fontsize=8, fontname="hebo", color=GOLD)
    doc.save(out_path)
    doc.close()


# ── annexure stamping ─────────────────────────────────────────────

def _stamp_annexure_header(doc: fitz.Document, label: str) -> None:
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
        text, fontsize=fontsize, fontname="hebo", color=WHITE,
    )


def _stamp_annexure_page_numbers(doc: fitz.Document,
                                 first_annex_page_idx: int,
                                 total_annex_pages: int) -> None:
    """Stamp '<n> of <total>' centred at the bottom of every annexure page.

    `first_annex_page_idx` is 0-based — the index of the first page in `doc`
    that belongs to Annexure A. Pages before that (Index, Main Document)
    are left unnumbered.
    """
    annex_no = 1
    for i, page in enumerate(doc):
        if i < first_annex_page_idx:
            continue
        text = f"{annex_no}  of  {total_annex_pages}"
        fontsize = 10
        w = fitz.get_text_length(text, fontname="helv", fontsize=fontsize)
        x = (page.rect.width - w) / 2
        y = page.rect.height - 26
        page.insert_text((x, y), text, fontsize=fontsize, fontname="helv",
                         color=MUTED)
        annex_no += 1


# ── merged bundle ─────────────────────────────────────────────────

def _build_merged_bundle(
    entries: list[BundleEntry],
    main_pdf: Path | None,
    out_dir: Path,
    bundle_path: Path,
) -> None:
    bundle = fitz.open()

    # 1. Index (always page 1)
    tmp_index = out_dir / ".tmp_index_for_bundle.pdf"
    pending_links = _write_index_pdf(entries, tmp_index)
    with fitz.open(tmp_index) as idx:
        bundle.insert_pdf(idx)
    try:
        tmp_index.unlink()
    except OSError:
        pass
    index_pages = bundle.page_count

    # 2. Main document (only if PDF — converted from DOCX earlier if needed)
    if main_pdf and main_pdf.exists():
        with fitz.open(main_pdf) as d:
            bundle.insert_pdf(d)
    main_end_page_idx = bundle.page_count   # 0-based index of first annexure page

    # 3. Annexures (stamp header on first page of each)
    total_annex_pages = 0
    for e in entries:
        src = out_dir / e.output_name
        if src.suffix.lower() != ".pdf":
            continue
        with fitz.open(src) as d:
            _stamp_annexure_header(d, e.label)
            bundle.insert_pdf(d)
            total_annex_pages += d.page_count

    # 4. Stamp annexure-relative page numbers (Annexure A page 1, etc.)
    _stamp_annexure_page_numbers(
        bundle,
        first_annex_page_idx=main_end_page_idx,
        total_annex_pages=total_annex_pages,
    )

    # 5. Install clickable links from index rows → annexure pages.
    for index_page_offset, rect, target_page in pending_links:
        merged_page_idx = index_page_offset
        if 0 <= merged_page_idx < bundle.page_count and 0 < target_page <= bundle.page_count:
            page = bundle[merged_page_idx]
            page.insert_link({
                "kind": fitz.LINK_GOTO,
                "from": rect,
                "page": target_page - 1,
                "to": fitz.Point(0, 0),
            })

    # 6. PDF outline (bookmarks)
    toc: list[list] = [[1, "Index", 1]]
    cursor = index_pages + 1
    if main_pdf and main_pdf.exists():
        toc.append([1, "Main Document", cursor])
        with fitz.open(main_pdf) as d:
            cursor += d.page_count
    if entries:
        toc.append([1, "Annexures", cursor])
        for e in entries:
            if e.page_count and e.bundle_page:
                title = f"Annexure {e.label}"
                if e.title:
                    title += f" — {e.title}"
                toc.append([2, _safe(title, 90), e.bundle_page])
    try:
        bundle.set_toc(toc)
    except Exception as ex:
        log.warning("Could not set PDF bookmarks: %s", ex)

    bundle.save(bundle_path)
    bundle.close()
