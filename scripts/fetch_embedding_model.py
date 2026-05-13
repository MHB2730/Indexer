"""Pre-download the bge-small-en-v1.5 ONNX model to vendor/embedding-model/.

Run once at build time so the model can be bundled into the installer and
no internet access is needed at runtime.
"""
from __future__ import annotations

import sys
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[1] / "vendor" / "embedding-model"


def main() -> int:
    VENDOR.mkdir(parents=True, exist_ok=True)
    try:
        from fastembed import TextEmbedding
    except ImportError:
        print("fastembed not installed; run `pip install fastembed` first.")
        return 1

    model_name = "BAAI/bge-small-en-v1.5"
    print(f"Caching {model_name} into {VENDOR} ...")
    model = TextEmbedding(model_name, cache_dir=str(VENDOR))
    # Force download + initialise by running one tiny inference.
    _ = list(model.embed(["warm-up text to trigger model load"]))
    print(f"Cached. Size:")
    total = 0
    for p in VENDOR.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    print(f"  {total / (1024 * 1024):.1f} MB across {sum(1 for _ in VENDOR.rglob('*'))} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
