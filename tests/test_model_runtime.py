from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docgen.anonymizer.detector_registry import UnavailableNerDetector
from docgen.anonymizer.model_config import MODEL_ID, MODEL_MANIFEST, MODEL_REVISION
from docgen.anonymizer.model_runtime import create_ner_detector, verify_model_manifest


class ModelIntegrityTests(unittest.TestCase):
    def test_manifest_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            weights = directory / "model.safetensors"
            weights.write_bytes(b"approved")
            (directory / MODEL_MANIFEST).write_text(
                json.dumps(
                    {
                        "model_id": MODEL_ID,
                        "revision": MODEL_REVISION,
                        "files": {
                            weights.name: hashlib.sha256(weights.read_bytes()).hexdigest()
                        },
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(verify_model_manifest(directory)[0])
            weights.write_bytes(b"tampered")
            valid, detail = verify_model_manifest(directory)

            self.assertFalse(valid)
            self.assertIn("checksum", detail)

    def test_missing_model_fails_closed_without_download(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            missing = Path(directory_name) / "missing"
            with patch.dict(
                os.environ,
                {
                    "SMARTDOCS_NER_MODE": "required",
                    "SMARTDOCS_NER_MODEL_PATH": str(missing),
                },
                clear=False,
            ):
                detector = create_ner_detector()

        self.assertIsInstance(detector, UnavailableNerDetector)
        self.assertFalse(detector.ready)


if __name__ == "__main__":
    unittest.main()
