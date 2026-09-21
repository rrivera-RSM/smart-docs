import unittest

from docgen.ui.state import (
    OUTPUT_BYTES_KEY,
    SOURCE_NAME_KEY,
    TEMPLATE_BYTES_KEY,
    UPLOAD_REVISION_KEY,
    store_fixed_template,
    store_output,
    sync_uploaded_template,
)


class SessionStateTests(unittest.TestCase):
    def test_new_upload_clears_output_and_form_values(self) -> None:
        state = {
            OUTPUT_BYTES_KEY: b"old-output",
            "smart_docs.field.cliente": "Valor anterior",
        }

        result = sync_uploaded_template(state, "plantilla.docx", b"source")

        self.assertEqual(result, b"source")
        self.assertEqual(state[TEMPLATE_BYTES_KEY], b"source")
        self.assertEqual(state[SOURCE_NAME_KEY], "plantilla.docx")
        self.assertNotIn(OUTPUT_BYTES_KEY, state)
        self.assertNotIn("smart_docs.field.cliente", state)
        self.assertEqual(state[UPLOAD_REVISION_KEY], 1)

    def test_same_upload_keeps_derived_state_and_rotates_widget(self) -> None:
        state: dict[str, object] = {}
        sync_uploaded_template(state, "plantilla.docx", b"source")
        store_output(state, b"generated")
        revision = state[UPLOAD_REVISION_KEY]

        sync_uploaded_template(state, "plantilla.docx", b"source")

        self.assertEqual(state[OUTPUT_BYTES_KEY], b"generated")
        self.assertEqual(state[UPLOAD_REVISION_KEY], revision + 1)

    def test_original_upload_can_replace_an_autofixed_working_copy(self) -> None:
        state: dict[str, object] = {}
        sync_uploaded_template(state, "plantilla.docx", b"source")
        store_fixed_template(state, b"fixed")
        revision = state[UPLOAD_REVISION_KEY]

        sync_uploaded_template(state, "plantilla.docx", b"source")

        self.assertEqual(state[TEMPLATE_BYTES_KEY], b"source")
        self.assertEqual(state[UPLOAD_REVISION_KEY], revision + 1)


if __name__ == "__main__":
    unittest.main()
