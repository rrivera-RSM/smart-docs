import unittest

from fastapi.testclient import TestClient

from apps.api.main import app
from docgen.config import DOCX_MIME


class UploadSecurityTests(unittest.TestCase):
    def test_rejects_invalid_zip_with_docx_extension(self) -> None:
        client = TestClient(app)

        response = client.post(
            "/api/anonymizer/analyze",
            files={"file": ("documento.docx", b"not-a-zip", DOCX_MIME)},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("Word válido", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
