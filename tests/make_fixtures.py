"""Generate a synthetic legal bundle for end-to-end testing.

Creates:
  fixtures/main.pdf        — affidavit-style doc referencing 6 annexures
  fixtures/pool/           — 10 candidate PDFs, some matching some noise,
                             with deliberately messy filenames.

Run:
  python tests/make_fixtures.py
"""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


FIXTURES = Path(__file__).resolve().parent / "fixtures"
POOL = FIXTURES / "pool"


MAIN_BODY = """\
IN THE HIGH COURT OF SOUTH AFRICA
(GAUTENG DIVISION, PRETORIA)

FOUNDING AFFIDAVIT

1. I, the deponent, state under oath as follows.

2. Attached hereto, marked "FA1", is a copy of my identity document.
   Annexure FA1: Identity document of the deponent.

3. The respondent's letter of demand dated 12 March 2024 is annexed hereto
   as Annexure FA2 - Letter of demand from the respondent.

4. Annexure FA3: Bank statement of ABSA account 4471 covering March 2024.

5. I refer to the agreement of sale, attached as Annexure A: Agreement of
   Sale between the parties dated 4 January 2023.

6. See also Annexure B - Notice of Objection filed on 1 June 2024.

7. Schedule 1: Inventory of movables removed from the premises.

8. As stated above, see further Annexure FA2 and Annexure A.

WHEREFORE the applicant prays for relief as per the notice of motion.
"""


CANDIDATES = [
    ("ID_copy_deponent.pdf",
     "REPUBLIC OF SOUTH AFRICA\nIDENTITY DOCUMENT\nSurname: ...\n"),
    ("letter of demand 12-03-2024.pdf",
     "LETTER OF DEMAND\nDate: 12 March 2024\nTo whom it may concern,\n"
     "We demand payment of the outstanding amount.\n"),
    ("absa_stmt_4471_march24.pdf",
     "ABSA BANK\nStatement for account 4471\nPeriod: 1 - 31 March 2024\n"),
    ("agreement_of_sale_2023.pdf",
     "AGREEMENT OF SALE\nentered into between the parties on 4 January 2023\n"),
    ("scan_0044.pdf",
     "NOTICE OF OBJECTION\nFiled: 1 June 2024\nThe objector hereby gives notice...\n"),
    ("inventory_movables.pdf",
     "INVENTORY OF MOVABLES\nItem 1: Sofa\nItem 2: Dining table\n"),
    ("misc_photo.pdf", "Photograph of the premises (no relevance).\n"),
    ("random_invoice.pdf", "INVOICE 0099\nServices rendered.\n"),
    ("draft_notes.pdf", "Draft notes — not for filing.\n"),
    ("old_correspondence.pdf",
     "Correspondence from 2019 unrelated to current matter.\n"),
]


def _write_pdf(path: Path, text: str, title: str | None = None) -> None:
    doc = fitz.open()
    page = doc.new_page()
    y = 60
    if title:
        page.insert_text((60, y), title, fontsize=14, fontname="helv")
        y += 30
    for line in text.splitlines():
        page.insert_text((60, y), line, fontsize=11, fontname="helv")
        y += 16
        if y > 780:
            page = doc.new_page()
            y = 60
    doc.save(path)
    doc.close()


def main() -> None:
    POOL.mkdir(parents=True, exist_ok=True)
    _write_pdf(FIXTURES / "main.pdf", MAIN_BODY, title="FOUNDING AFFIDAVIT")
    for name, body in CANDIDATES:
        _write_pdf(POOL / name, body)
    print(f"Wrote fixtures to {FIXTURES}")


if __name__ == "__main__":
    main()
