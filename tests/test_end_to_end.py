"""End-to-end smoke test against synthetic fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from indexer.bundler import assemble  # noqa: E402
from indexer.matcher import match_all  # noqa: E402
from indexer.parser import extract    # noqa: E402
from indexer.references import find_references  # noqa: E402


def main() -> None:
    fixtures = ROOT / "tests" / "fixtures"
    main_doc = fixtures / "main.pdf"
    pool_dir = fixtures / "pool"
    out_dir = ROOT / "tests" / "out"

    if not main_doc.exists():
        print("Run `python tests/make_fixtures.py` first.")
        sys.exit(1)

    if out_dir.exists():
        for p in out_dir.iterdir():
            p.unlink()
    else:
        out_dir.mkdir(parents=True)

    doc = extract(main_doc)
    refs = find_references(doc.text)
    print(f"Found {len(refs)} references:")
    for r in refs:
        print(f"  - {r.label}: {r.title or '(no title)'}")

    pool = [p for p in pool_dir.iterdir() if p.suffix.lower() == ".pdf"]
    matches = match_all(refs, pool)

    print("\nTop matches:")
    for mr in matches:
        b = mr.best
        if b:
            print(f"  {mr.reference.label:<5} -> {b.path.name:<40}  "
                  f"[{mr.confidence} {b.score}]")

    report = assemble(matches, main_doc, out_dir, auto_confidence="low")
    print(f"\nWrote {len(report['entries'])} entries.")
    print(f"Unresolved: {len(report['unresolved'])}")
    print(json.dumps(report["entries"], indent=2))


if __name__ == "__main__":
    main()
