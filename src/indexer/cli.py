"""Command-line entry point."""
from __future__ import annotations

from pathlib import Path

import click

from .bundler import assemble
from .matcher import match_all
from .parser import extract
from .references import find_references


SUPPORTED_SUFFIXES = {".pdf", ".docx", ".doc"}


@click.group()
def cli() -> None:
    """Indexer — assemble legal bundles offline."""


@cli.command()
@click.option("--main", "main_path", required=True, type=click.Path(exists=True, path_type=Path))
def scan(main_path: Path) -> None:
    """Print annexure references found in the main document."""
    doc = extract(main_path)
    refs = find_references(doc.text)
    click.echo(f"Found {len(refs)} annexure references in {main_path.name}:")
    for r in refs:
        title = f" — {r.title}" if r.title else ""
        click.echo(f"  Annexure {r.label}{title}  ({r.mentions} mentions)")


@cli.command()
@click.option("--main", "main_path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--pool", "pool_dir", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--out", "out_dir", required=True, type=click.Path(path_type=Path))
@click.option(
    "--auto",
    "auto_confidence",
    type=click.Choice(["high", "medium", "low"]),
    default="high",
    help="Minimum confidence to auto-accept a match.",
)
def build(main_path: Path, pool_dir: Path, out_dir: Path, auto_confidence: str) -> None:
    """Match annexures, copy & rename them, build index, annotate main doc."""
    doc = extract(main_path)
    refs = find_references(doc.text)
    if not refs:
        click.echo("No annexure references found.")
        return

    pool = [p for p in pool_dir.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES]
    click.echo(f"Main: {main_path.name}  |  {len(refs)} refs  |  pool: {len(pool)} files")

    matches = match_all(refs, pool)
    for mr in matches:
        best = mr.best
        if best:
            click.echo(
                f"  Annexure {mr.reference.label:<5} -> {best.path.name}  "
                f"[{mr.confidence} {best.score}]"
            )
        else:
            click.echo(f"  Annexure {mr.reference.label:<5} -> (no candidates)")

    report = assemble(matches, main_path, out_dir, auto_confidence=auto_confidence)
    click.echo(f"\nWrote {len(report['entries'])} annexures to {out_dir}")
    if report["unresolved"]:
        click.echo(f"{len(report['unresolved'])} unresolved — see report.json")


if __name__ == "__main__":
    cli()
