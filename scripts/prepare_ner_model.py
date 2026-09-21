#!/usr/bin/env python3
"""Download and checksum the approved NER snapshot during setup, never runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from huggingface_hub import snapshot_download  # noqa: E402

from docgen.anonymizer.model_config import (  # noqa: E402
    MODEL_DIRECTORY,
    MODEL_ID,
    MODEL_MANIFEST,
    MODEL_REVISION,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=MODEL_DIRECTORY)
    args = parser.parse_args()
    destination = (PROJECT_ROOT / args.output).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=destination,
        allow_patterns=[
            "config.json",
            "model.safetensors",
            "pytorch_model.bin",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.json",
            "merges.txt",
            "sentencepiece.bpe.model",
        ],
    )
    files = {
        path.relative_to(destination).as_posix(): sha256(path)
        for path in sorted(destination.rglob("*"))
        if path.is_file()
        and path.name != MODEL_MANIFEST
        and ".cache" not in path.parts
    }
    if not files:
        raise RuntimeError("La descarga no ha producido archivos de modelo.")
    (destination / MODEL_MANIFEST).write_text(
        json.dumps(
            {
                "model_id": MODEL_ID,
                "revision": MODEL_REVISION,
                "algorithm": "sha256",
                "files": files,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(destination)


if __name__ == "__main__":
    main()
