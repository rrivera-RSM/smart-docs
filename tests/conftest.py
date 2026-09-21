from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


os.environ.setdefault("SMARTDOCS_NER_MODE", "rules")
os.environ.setdefault("SMARTDOCS_FEATURE_PDF", "true")
os.environ.setdefault("SMARTDOCS_FEATURE_IMAGE_OCR", "true")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "e2e"


def load_corpus_manifest() -> dict[str, object]:
    return json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def api_client() -> TestClient:
    from apps.api.main import app

    with TestClient(app) as client:
        yield client
