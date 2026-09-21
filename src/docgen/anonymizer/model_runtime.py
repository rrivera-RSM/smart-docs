from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path

from docgen.anonymizer.detector_registry import (
    NoOpNerDetector,
    PresidioNerDetector,
    UnavailableNerDetector,
)
from docgen.anonymizer.model_config import (
    MODEL_DIRECTORY,
    MODEL_ID,
    MODEL_MANIFEST,
    MODEL_REVISION,
)


def verify_model_manifest(model_path: str | Path) -> tuple[bool, str]:
    directory = Path(model_path)
    manifest_path = directory / MODEL_MANIFEST
    if not directory.is_dir() or not manifest_path.is_file():
        return False, "El modelo local o su manifiesto de integridad no estan disponibles."
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "El manifiesto del modelo local no es valido."
    if manifest.get("model_id") != MODEL_ID or manifest.get("revision") != MODEL_REVISION:
        return False, "La version del modelo local no coincide con la version aprobada."
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        return False, "El manifiesto del modelo no contiene checksums."
    for relative_name, expected in files.items():
        if not isinstance(relative_name, str) or not isinstance(expected, str):
            return False, "El manifiesto del modelo contiene una entrada no valida."
        target = directory / relative_name
        if not target.is_file():
            return False, f"Falta un archivo requerido del modelo: {relative_name}."
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if not hmac.compare_digest(digest, expected):
            return False, f"El checksum del modelo no coincide: {relative_name}."
    return True, "Modelo local verificado por SHA-256."


def create_ner_detector() -> NoOpNerDetector | UnavailableNerDetector | PresidioNerDetector:
    if os.getenv("SMARTDOCS_NER_MODE", "required").strip().lower() == "rules":
        return NoOpNerDetector()
    model_path = os.getenv("SMARTDOCS_NER_MODEL_PATH", MODEL_DIRECTORY).strip()
    verified, detail = verify_model_manifest(model_path)
    if not verified:
        return UnavailableNerDetector(detail)
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    detector = PresidioNerDetector(model_path)
    if detector.ready:
        detector.detail = detail
    return detector
