"""Background workers so the UI stays responsive."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..bundler import assemble
from ..matcher import MatchResult, match_all
from ..parser import extract
from ..references import find_references


SUPPORTED = {".pdf", ".docx", ".doc"}


class ScanWorker(QObject):
    finished = Signal(list, list)   # references, pool_paths
    failed = Signal(str)

    def __init__(self, main_path: Path, pool_dir: Path):
        super().__init__()
        self.main_path = main_path
        self.pool_dir = pool_dir

    def run(self) -> None:
        try:
            doc = extract(self.main_path)
            refs = find_references(doc.text)
            pool = sorted(
                p for p in self.pool_dir.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED
            )
            self.finished.emit(refs, pool)
        except Exception as e:
            self.failed.emit(str(e))


class MatchWorker(QObject):
    finished = Signal(list)   # list[MatchResult]
    failed = Signal(str)

    def __init__(self, refs, pool):
        super().__init__()
        self.refs = refs
        self.pool = pool

    def run(self) -> None:
        try:
            results: list[MatchResult] = match_all(self.refs, self.pool)
            self.finished.emit(results)
        except Exception as e:
            self.failed.emit(str(e))


class BuildWorker(QObject):
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, matches, main_path: Path, out_dir: Path, auto_confidence: str):
        super().__init__()
        self.matches = matches
        self.main_path = main_path
        self.out_dir = out_dir
        self.auto_confidence = auto_confidence

    def run(self) -> None:
        try:
            report = assemble(
                self.matches, self.main_path, self.out_dir,
                auto_confidence=self.auto_confidence,
            )
            self.finished.emit(report)
        except Exception as e:
            self.failed.emit(str(e))
