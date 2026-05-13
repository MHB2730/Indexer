"""Semantic embeddings via bge-small-en-v1.5 (ONNX, fastembed).

Used by the matcher as the dominant signal for candidate ranking. The
model is bundled under vendor/embedding-model and copied into the
PyInstaller distribution at build time. If anything goes wrong loading
it, callers fall back to lexical/date/noun signals.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Sequence

import numpy as np

log = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384


def _model_dir() -> Path | None:
    if hasattr(sys, "_MEIPASS"):
        d = Path(sys._MEIPASS) / "embedding-model"
    else:
        d = Path(__file__).resolve().parents[2] / "vendor" / "embedding-model"
    return d if d.is_dir() else None


_model = None
_load_attempted = False


def _get_model():
    global _model, _load_attempted
    if _load_attempted:
        return _model
    _load_attempted = True
    try:
        from fastembed import TextEmbedding
    except ImportError as e:
        log.warning("fastembed not installed (%s); semantic matching disabled.", e)
        return None
    cache_dir = _model_dir()
    if cache_dir is None:
        log.warning("Bundled embedding model not found; semantic matching disabled.")
        return None
    try:
        _model = TextEmbedding(MODEL_NAME, cache_dir=str(cache_dir),
                               local_files_only=True)
        log.info("Loaded embedding model %s from %s", MODEL_NAME, cache_dir)
    except Exception as e:
        log.warning("Failed to load embedding model: %s", e)
        _model = None
    return _model


def is_available() -> bool:
    return _get_model() is not None


def embed(texts: Sequence[str]) -> np.ndarray | None:
    """Return an (N, 384) array of L2-normalised embeddings, or None."""
    if not texts:
        return None
    model = _get_model()
    if model is None:
        return None
    try:
        cleaned = [(t or " ").strip()[:6000] or " " for t in texts]
        vecs = list(model.embed(cleaned))
        return np.asarray(vecs, dtype=np.float32)
    except Exception as e:
        log.warning("Embedding failed: %s", e)
        return None


def cosine_similarity_matrix(queries: np.ndarray, candidates: np.ndarray) -> np.ndarray:
    """queries (N, D) × candidates (M, D) → (N, M) similarity, in [-1, 1]."""
    return queries @ candidates.T
