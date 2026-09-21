from __future__ import annotations

import io
import time
import unittest

from docx import Document
from fastapi.testclient import TestClient

from apps.api import anonymizer_api
from apps.api.anonymizer_api import AnonymizerJobStore
from apps.api.main import app
from docgen.anonymizer.detector_registry import UnavailableNerDetector
from docgen.anonymizer.models import AnalysisOptions
from docgen.anonymizer.verified_engine import VerifiedLocalAnonymizerEngine
from docgen.config import DOCX_MIME


def _document_bytes(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def _wait(client: TestClient, job_id: str) -> dict[str, object]:
    for _ in range(200):
        response = client.get(f"/api/anonymizer/{job_id}")
        if response.status_code != 200:
            raise AssertionError(response.text)
        payload = response.json()
        if payload["status"] not in {"queued", "extracting", "detecting", "applying"}:
            return payload
        time.sleep(.01)
    raise AssertionError("El trabajo no alcanzo un estado terminal.")


class AdvancedAnonymizerApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_capabilities_publish_model_categories_and_limits(self) -> None:
        response = self.client.get("/api/anonymizer/capabilities")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["default_profile"], "maximum")
        self.assertTrue(payload["model"]["local_only"])
        self.assertIn("PERSON", {item["id"] for item in payload["categories"]})
        self.assertEqual(payload["limits"]["retention_minutes"], 30)

    def test_manual_finding_then_delete_job(self) -> None:
        source = _document_bytes("Proyecto Horizonte firma el acuerdo.")
        response = self.client.post(
            "/api/anonymizer/analyze",
            files={"file": ("acuerdo.docx", source, DOCX_MIME)},
        )
        self.assertEqual(response.status_code, 202)
        payload = _wait(self.client, response.json()["job_id"])
        block = payload["blocks"][0]
        start = block["text"].index("Horizonte")

        manual = self.client.post(
            f"/api/anonymizer/{payload['job_id']}/findings/manual",
            json={
                "block_id": block["id"],
                "start": start,
                "end": start + len("Horizonte"),
                "entity_type": "ORGANIZATION",
                "all_occurrences": True,
            },
        )

        self.assertEqual(manual.status_code, 200)
        group = next(item for item in manual.json()["groups"] if item["entity_type"] == "ORGANIZATION")
        self.assertEqual(group["confidence_band"], "validated")
        self.assertIn("Revisión manual", group["sources"])

        rejected = self.client.post(
            f"/api/anonymizer/{payload['job_id']}/apply",
            json={"decisions": [{"group_id": group["id"], "action": "replace"}]},
        )
        self.assertEqual(rejected.status_code, 400)

        deleted = self.client.delete(f"/api/anonymizer/{payload['job_id']}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(
            self.client.get(f"/api/anonymizer/{payload['job_id']}").status_code,
            404,
        )

    def test_model_unavailable_fails_closed_with_503(self) -> None:
        previous = anonymizer_api.anonymizer_engine
        anonymizer_api.anonymizer_engine = VerifiedLocalAnonymizerEngine(
            ner_detector=UnavailableNerDetector("Modelo local ausente para la prueba."),
        )
        try:
            response = self.client.post(
                "/api/anonymizer/analyze",
                files={"file": ("datos.docx", _document_bytes("DNI 12345678Z"), DOCX_MIME)},
            )
        finally:
            anonymizer_api.anonymizer_engine = previous

        self.assertEqual(response.status_code, 503)
        self.assertIn("Modelo local ausente", response.json()["detail"])

    def test_zero_ttl_store_expires_without_persistence(self) -> None:
        store = AnonymizerJobStore(ttl_minutes=0)
        job = store.create(
            source_name="temporal.docx",
            source_bytes=b"temporary",
            options=AnalysisOptions(),
        )

        with self.assertRaises(KeyError):
            store.get(job.id)


if __name__ == "__main__":
    unittest.main()
