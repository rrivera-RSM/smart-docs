import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class AppSmokeTests(unittest.TestCase):
    def test_initial_screen_renders_without_exceptions(self) -> None:
        app_path = Path(__file__).parents[1] / "src" / "docgen" / "app.py"

        app = AppTest.from_file(str(app_path)).run(timeout=10)

        self.assertEqual(list(app.exception), [])
        self.assertGreater(len(app.markdown), 0)


if __name__ == "__main__":
    unittest.main()
