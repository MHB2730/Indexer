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
from datetime import date
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
    bundle_page: int = 0
    page_count: int = 0


# Brand palette (PyMuPDF expects 0..1 RGB tuples)
NAVY = (0.122, 0.227, 0.373)         # #1F3A5F
NAVY_DARK = (0.055, 0.133, 0.220)    # #0E2238
GOLD = (0.718, 0.475, 0.122)         # #B7791F
WHITE = (1.0, 1.0, 1.0)
INK = (0.06, 0.09, 0.16)
MUTED = (0.42, 0.45, 0.50)
ZEBRA = (0.965, 0.97, 0.98)
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
        _plan_layout(main_pdf, entries, out_dir)

        standalone_index = out_dir / "index.pdf"
        _write_index_pdf(entries, standalone_index)

        main_annotated = out_dir / "main_annotated.pdf"
        _annotate_main(main_pdf, entries, main_annotated)

        bundle_path = out_dir / "bundle.pdf"
        _build_merged_bundle(
            entries=entries,
            main_doc=main_doc,
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
    cover_pages = 1
    index_pages = _estimated_index_pages(len(entries))
    main_pages = _pdf_page_count(main_pdf) if main_pdf else 0

    cursor = 1
    cover_start = cursor
    cursor += cover_pages
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

    return {
        "cover_start": cover_start, "cover_pages": cover_pages,
        "index_start": index_start, "index_pages": index_pages,
        "main_start": main_start, "main_pages": main_pages,
        "total_pages": cursor - 1,
    }


# ── cover page ────────────────────────────────────────────────────

def _draw_cover(doc: fitz.Document, main_doc: Path) -> None:
    page = doc.new_page()
    w, h = page.rect.width, page.rect.height
    # Top navy band
    page.draw_rect(fitz.Rect(0, 0, w, 110), color=NAVY, fill=NAVY, width=0)
    # Gold accent
    page.draw_rect(fitz.Rect(0, 110, w, 116), color=GOLD, fill=GOLD, width=0)

    # Brand line
    page.insert_text((48, 70), "INDEXER", fontsize=22, fontname="hebo",
                     color=WHITE)
    page.insert_text((48, 92), "LEGAL BUNDLE ASSEMBLER", fontsize=10,
                     fontname="helv", color=(0.88, 0.71, 0.37))

    # Main title centred mid-page
    title = "BUNDLE OF DOCUMENTS"
    title_size = 28
    tw = fitz.get_text_length(title, fontname="hebo", fontsize=title_size)
    page.insert_text(((w - tw) / 2, h * 0.42), title,
                     fontsize=title_size, fontname="hebo", color=NAVY_DARK)

    # Underline accent under title
    line_y = h * 0.42 + 8
    page.draw_line((w / 2 - 60, line_y), (w / 2 + 60, line_y),
                   color=GOLD, width=2)

    # Subtitle from main doc filename
    sub = _safe(main_doc.stem.replace("_", " ").replace("-", " "), 120)
    if sub:
        sw = fitz.get_text_length(sub, fontname="helv", fontsize=14)
        page.insert_text(((w - sw) / 2, h * 0.42 + 38), sub,
                         fontsize=14, fontname="helv", color=INK)

    today = date.today().strftime("%d %B %Y").lstrip("0")
    footer = f"Compiled on {today}"
    fw = fitz.get_text_length(footer, fontname="helv", fontsize=11)
    page.insert_text(((w - fw) / 2, h - 90), footer,
                     fontsize=11, fontname="helv", color=MUTED)

    # Bottom band
    page.draw_rect(fitz.Rect(0, h - 40, w, h), color=NAVY, fill=NAVY, width=0)
    note = "Prepared with Indexer • indexer.app"
    nw = fitz.get_text_length(note, fontname="helv", fontsize=9)
    page.insert_text(((w - nw) / 2, h - 16), note,
                     fontsize=9, fontname="helv", color=(0.88, 0.71, 0.37))


# ── tabled Index ──────────────────────────────────────────────────

# Standalone-index column widths sum to ~ A4 minus margins.
_COL_SEQ = 38
_COL_LABEL = 110
_COL_PAGE = 60
# (description column gets the leftover space)

_HEADER_H = 28
_ROW_H = 22
_MARGIN = 48


def _draw_index_header(page: fitz.Page, top_y: float) -> tuple[float, dict]:
    """Draw 'INDEX' title and table header on `page` starting near top_y.

    Returns (table_top_y, column_rects).
    """
    w = page.rect.width
    # Title
    page.insert_text((_MARGIN, top_y + 14), "INDEX",
                     fontsize=22, fontname="hebo", color=NAVY_DARK)
    page.insert_text((_MARGIN, top_y + 34), "Bundle of documents",
                     fontsize=10, fontname="helv", color=MUTED)
    # Gold underline
    page.draw_line((_MARGIN, top_y + 44), (_MARGIN + 60, top_y + 44),
                   color=GOLD, width=2)

    header_top = top_y + 60
    header_bottom = header_top + _HEADER_H

    # Compute column rectangles
    table_left = _MARGIN
    table_right = w - _MARGIN
    seq_left = table_left
    seq_right = seq_left + _COL_SEQ
    label_left = seq_right
    label_right = label_left + _COL_LABEL
    page_right = table_right
    page_left = page_right - _COL_PAGE
    desc_left = label_right
    desc_right = page_left

    cols = {
        "seq": fitz.Rect(seq_left, header_top, seq_right, header_bottom),
        "label": fitz.Rect(label_left, header_top, label_right, header_bottom),
        "desc": fitz.Rect(desc_left, header_top, desc_right, header_bottom),
        "page": fitz.Rect(page_left, header_top, page_right, header_bottom),
    }

    # Header background
    page.draw_rect(
        fitz.Rect(table_left, header_top, table_right, header_bottom),
        color=NAVY, fill=NAVY, width=0,
    )
    # Header labels
    _draw_cell_text(page, cols["seq"], "#", bold=True, color=WHITE, align="center")
    _draw_cell_text(page, cols["label"], "Annexure", bold=True, color=WHITE,
                    align="left", padding=10)
    _draw_cell_text(page, cols["desc"], "Description", bold=True, color=WHITE,
                    align="left", padding=10)
    _draw_cell_text(page, cols["page"], "Page", bold=True, color=WHITE,
                    align="right", padding=10)

    return header_bottom, cols


def _draw_cell_text(page: fitz.Page, rect: fitz.Rect, text: str,
                    bold: bool = False, color=INK, align: str = "left",
                    padding: int = 6, fontsize: int = 11) -> None:
    font = "hebo" if bold else "helv"
    # Vertical centre approximation
    y = rect.y0 + (rect.height + fontsize) / 2 - 3
    text = _truncate_to_fit(text, font, fontsize, rect.width - 2 * padding)
    tw = fitz.get_text_length(text, fontname=font, fontsize=fontsize)
    if align == "center":
        x = rect.x0 + (rect.width - tw) / 2
    elif align == "right":
        x = rect.x1 - tw - padding
    else:
        x = rect.x0 + padding
    page.insert_text((x, y), text, fontsize=fontsize, fontname=font, color=color)


def _truncate_to_fit(text: str, fontname: str, fontsize: int, max_width: float) -> str:
    if fitz.get_text_length(text, fontname=fontname, fontsize=fontsize) <= max_width:
        return text
    while text and fitz.get_text_length(text + "…", fontname=fontname,
                                        fontsize=fontsize) > max_width:
        text = text[:-1]
    return text + "…"


def _write_index_pdf(
    entries: list[BundleEntry],
    path: Path,
) -> list[tuple[int, fitz.Rect, int]]:
    """Render the tabled index into `path`.

    Returns a list of (index_page_index, row_rect, target_page_1based) so the
    caller can install clickable links when this index is later embedded in
    the merged bundle.
    """
    doc = fitz.open()
    pending_links: list[tuple[int, fitz.Rect, int]] = []

    page = doc.new_page()
    y, cols = _draw_index_header(page, top_y=_MARGIN)
    rows_on_this_page = 0
    max_rows = _INDEX_ROWS_FIRST_PAGE

    for i, e in enumerate(entries):
        if rows_on_this_page >= max_rows:
            page = doc.new_page()
            y, cols = _draw_index_header(page, top_y=_MARGIN)
            rows_on_this_page = 0
            max_rows = _INDEX_ROWS_NEXT_PAGE

        row_rect = fitz.Rect(_MARGIN, y, page.rect.width - _MARGIN, y + _ROW_H)
        # Zebra
        if i % 2 == 1:
            page.draw_rect(row_rect, color=ZEBRA, fill=ZEBRA, width=0)

        _draw_cell_text(page, fitz.Rect(cols["seq"].x0, y, cols["seq"].x1, y + _ROW_H),
                        str(e.sequence), color=MUTED, align="center")
        _draw_cell_text(page, fitz.Rect(cols["label"].x0, y, cols["label"].x1, y + _ROW_H),
                        f"Annexure {e.label}", bold=True, color=NAVY, padding=10)
        _draw_cell_text(page, fitz.Rect(cols["desc"].x0, y, cols["desc"].x1, y + _ROW_H),
                        e.title or "—", color=INK, padding=10)
        page_str = str(e.bundle_page) if e.bundle_page else "—"
        _draw_cell_text(page, fitz.Rect(cols["page"].x0, y, cols["page"].x1, y + _ROW_H),
                        page_str, color=NAVY, align="right", padding=10)
        # Row bottom rule
        page.draw_line((row_rect.x0, row_rect.y1), (row_rect.x1, row_rect.y1),
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


def _stamp_bundle_page_numbers(doc: fitz.Document, total: int,
                               skip_first: int = 0) -> None:
    for i, page in enumerate(doc, 1):
        if i <= skip_first:
            continue
        text = f"{i}  /  {total}"
        fontsize = 9
        w = fitz.get_text_length(text, fontname="helv", fontsize=fontsize)
        x = (page.rect.width - w) / 2
        y = page.rect.height - 24
        page.insert_text((x, y), text, fontsize=fontsize, fontname="helv",
                         color=MUTED)


# ── merged bundle ─────────────────────────────────────────────────

def _build_merged_bundle(
    entries: list[BundleEntry],
    main_doc: Path,
    main_pdf: Path | None,
    out_dir: Path,
    bundle_path: Path,
) -> None:
    bundle = fitz.open()

    # 1. Cover page
    _draw_cover(bundle, main_doc)
    cover_pages_added = bundle.page_count   # =1

    # 2. Tabled index — render to a temp doc so we can capture link
    # target rects and copy pages in, then install links once the merged
    # bundle's true page numbers are known.
    tmp_index = out_dir / ".tmp_index_for_bundle.pdf"
    pending_links = _write_index_pdf(entries, tmp_index)

    index_first_page_in_bundle = bundle.page_count + 1   # 1-based
    with fitz.open(tmp_index) as idx:
        bundle.insert_pdf(idx)
    try:
        tmp_index.unlink()
    except OSError:
        pass
    index_pages = bundle.page_count - (index_first_page_in_bundle - 1)

    # 3. Main document
    if main_pdf and main_pdf.exists():
        with fitz.open(main_pdf) as d:
            bundle.insert_pdf(d)

    # 4. Annexures (stamp first page header)
    for e in entries:
        src = out_dir / e.output_name
        if src.suffix.lower() != ".pdf":
            continue
        with fitz.open(src) as d:
            _stamp_annexure_header(d, e.label)
            bundle.insert_pdf(d)

    # 5. Bottom-centre page numbers (skip the cover)
    _stamp_bundle_page_numbers(bundle, bundle.page_count, skip_first=cover_pages_added)

    # 6. Install clickable links from index entries → annexure pages.
    # pending_links entries: (page_idx_in_index_doc, rect_on_index_page, target_bundle_page_1based)
    for index_page_offset, rect, target_page in pending_links:
        merged_page_idx = (index_first_page_in_bundle - 1) + index_page_offset
        if 0 <= merged_page_idx < bundle.page_count and 0 < target_page <= bundle.page_count:
            page = bundle[merged_page_idx]
            page.insert_link({
                "kind": fitz.LINK_GOTO,
                "from": rect,
                "page": target_page - 1,
                "to": fitz.Point(0, 0),
            })

    # 7. PDF outline (bookmarks)
    toc: list[list] = [
        [1, "Cover", 1],
        [1, "Index", index_first_page_in_bundle],
    ]
    cursor = index_first_page_in_bundle + index_pages
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
