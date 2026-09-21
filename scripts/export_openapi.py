from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SMARTDOCS_NER_MODE", "rules")

from apps.api.main import app  # noqa: E402


def main() -> None:
    destination = Path(sys.argv[1] if len(sys.argv) > 1 else "apps/web/openapi.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
