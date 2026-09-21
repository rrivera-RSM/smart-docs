from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from conftest import FIXTURE_ROOT, load_corpus_manifest
from docgen.anonymizer.adapter_registry import DocumentAdapterRegistry
from docgen.anonymizer.resolution import canonical_value
from docgen.anonymizer.verified_engine import build_verified_rules_engine
from docgen.document_formats import detect_document_format, mime_type_for


MANIFEST = load_corpus_manifest()


def corpus_params(section: str) -> list[object]:
    return [
        pytest.param(
            case,
            id=case["id"],
            marks=[pytest.mark.slow] if case.get("slow") else [],
        )
        for case in MANIFEST[section]
    ]


def wait_for_job(
    client: TestClient,
    job_id: str,
    *,
    timeout_seconds: float = 30,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"/api/anonymizer/{job_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] not in {
            "queued",
            "extracting",
            "detecting",
            "applying",
        }:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"El trabajo {job_id} no terminó en {timeout_seconds} segundos.")


def expected_pairs(case: dict[str, object]) -> set[tuple[str, str]]:
    return {
        (entity_type, canonical_value(entity_type, value))
        for entity_type, values in case["expected_values"].items()
        for value in values
    }


@pytest.mark.e2e
@pytest.mark.parametrize("case", corpus_params("anonymizer_cases"))
def test_anonymizer_api_full_document_workflow(
    api_client: TestClient,
    case: dict[str, object],
) -> None:
    path = FIXTURE_ROOT / case["path"]
    source = path.read_bytes()
    uploaded = api_client.post(
        "/api/anonymizer/analyze",
        files={"file": (path.name, source, mime_type_for(case["format"]))},
    )
    assert uploaded.status_code == 202, uploaded.text

    review = wait_for_job(api_client, uploaded.json()["job_id"])
    assert review["status"] == "review_ready", review
    actual = {
        (finding["entity_type"], canonical_value(finding["entity_type"], finding["value"]))
        for finding in review["findings"]
    }
    assert expected_pairs(case) <= actual

    applied = api_client.post(
        f"/api/anonymizer/{review['job_id']}/apply",
        json={
            "review_confirmed": True,
            "remove_unsupported_content": False,
            "decisions": [
                {
                    "group_id": group["id"],
                    "action": "replace",
                    "replacement": group["replacement"],
                }
                for group in review["groups"]
            ],
        },
    )
    assert applied.status_code == 202, applied.text
    ready = wait_for_job(api_client, review["job_id"])
    assert ready["status"] == "ready", ready

    download = api_client.get(ready["download_url"])
    assert download.status_code == 200
    assert detect_document_format(download.content) == case["format"]

    residual = build_verified_rules_engine().analyze(download.content)
    residual_pairs = {
        (finding.entity_type, canonical_value(finding.entity_type, finding.value))
        for finding in residual.findings
    }
    assert expected_pairs(case).isdisjoint(residual_pairs)

    deleted = api_client.delete(f"/api/anonymizer/{review['job_id']}")
    assert deleted.status_code == 204
    assert api_client.get(f"/api/anonymizer/{review['job_id']}").status_code == 404


@pytest.mark.e2e
@pytest.mark.parametrize("case", corpus_params("generator_cases"))
def test_generator_api_full_document_workflow(
    api_client: TestClient,
    case: dict[str, object],
) -> None:
    path = FIXTURE_ROOT / case["path"]
    source = path.read_bytes()
    uploaded = api_client.post(
        "/api/generator/analyze",
        files={"file": (path.name, source, mime_type_for(case["format"]))},
    )
    assert uploaded.status_code == 200, uploaded.text
    analysis = uploaded.json()
    assert set(analysis["variables"]) == set(case["variables"])

    generated = api_client.post(
        f"/api/generator/{analysis['job_id']}/generate",
        json={"context": case["context"]},
    )
    assert generated.status_code == 200, generated.text

    download = api_client.get(generated.json()["download_url"])
    assert download.status_code == 200
    assert detect_document_format(download.content) == case["format"]
    adapter = DocumentAdapterRegistry().for_document(download.content)
    blocks, issues = adapter.extract(download.content)
    assert not issues
    rendered_text = "\n".join(block.text for block in blocks).casefold()
    for expected in case["expected_text"]:
        assert expected.casefold() in rendered_text
