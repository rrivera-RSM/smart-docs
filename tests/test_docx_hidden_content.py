from __future__ import annotations

import io
import unittest
import zipfile

from docx import Document

from docgen.anonymizer.verified_engine import build_verified_rules_engine


def document_with_alt_chunk() -> bytes:
    document = Document()
    document.add_paragraph("DNI 12345678Z")
    source = io.BytesIO()
    document.save(source)
    with zipfile.ZipFile(io.BytesIO(source.getvalue())) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}

    document_xml = files["word/document.xml"].decode("utf-8")
    files["word/document.xml"] = document_xml.replace(
        "</w:body>",
        '<w:altChunk r:id="rId999"/></w:body>',
    ).encode("utf-8")
    relationships = files["word/_rels/document.xml.rels"].decode("utf-8")
    files["word/_rels/document.xml.rels"] = relationships.replace(
        "</Relationships>",
        '<Relationship Id="rId999" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/aFChunk" '
        'Target="afchunk1.html"/></Relationships>',
    ).encode("utf-8")
    files["word/afchunk1.html"] = b"<html><body>contenido no inspeccionable</body></html>"

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return output.getvalue()


class HiddenContentTests(unittest.TestCase):
    def test_alt_chunk_blocks_and_is_removed_from_safe_copy(self) -> None:
        engine = build_verified_rules_engine()
        source = document_with_alt_chunk()
        analysis = engine.analyze(source)

        self.assertIn("linked_object", {issue.kind for issue in analysis.coverage_issues})
        output, _ = engine.apply(
            source,
            analysis,
            selected_group_ids={group.id for group in analysis.groups},
            replacements={},
            remove_unsupported_content=True,
        )

        with zipfile.ZipFile(io.BytesIO(output)) as archive:
            names = archive.namelist()
            self.assertNotIn("word/afchunk1.html", names)
            self.assertNotIn(b"altChunk", archive.read("word/document.xml"))
            self.assertNotIn(b"aFChunk", archive.read("word/_rels/document.xml.rels"))


if __name__ == "__main__":
    unittest.main()
