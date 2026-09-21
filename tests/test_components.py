import unittest

from docgen.ui.components import _html_markup


class HtmlMarkupTests(unittest.TestCase):
    def test_removes_python_indentation_from_html_blocks(self) -> None:
        markup = _html_markup(
            """
            <section>
              <p>Contenido</p>
            </section>
            """
        )

        self.assertTrue(markup.startswith("<section>"))
        self.assertNotIn("\n    <section>", markup)
        self.assertEqual(markup.splitlines()[-1], "</section>")


if __name__ == "__main__":
    unittest.main()
