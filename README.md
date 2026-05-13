# Indexer

Offline desktop tool for assembling legal bundles. Reads a main document
(PDF or DOCX), finds annexure references, matches them against a pool of
candidate files, builds an index, copies & numbers the annexures, and
annotates the main document with bundle page references.

## Status

Core engine (headless). Qt UI to follow once matching quality is
validated on real bundles.

## Install

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```
python -m indexer.cli build \
    --main path/to/main.pdf \
    --pool path/to/candidate_folder \
    --out  path/to/output_bundle
```

Outputs:

- `output_bundle/` — numbered annexures (`01_Annexure_FA1_<title>.pdf` ...)
- `output_bundle/index.pdf` — generated index page
- `output_bundle/main_annotated.pdf` — main doc with bundle refs
- `output_bundle/report.json` — match decisions + confidence scores

## Layout

```
src/indexer/
    parser.py     # text extraction from PDF / DOCX
    references.py # finds "Annexure X" references in main doc
    matcher.py    # filename + BM25 + heuristic matching
    bundler.py    # copy/rename/index/annotate
    cli.py
```
