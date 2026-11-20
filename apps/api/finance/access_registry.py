"""Persistent registry of authenticated users observed by the application."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from pydantic import BaseModel


class ObservedUser(BaseModel):
    key: str
    email: str
    name: str
    first_seen_at: str
    last_seen_at: str


class ObservedUserStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = RLock()

    def _read_unlocked(self) -> list[ObservedUser]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return [
                ObservedUser.model_validate(item)
                for item in payload.get("users", [])
            ]
        except (OSError, ValueError, TypeError) as exc:
            raise RuntimeError(
                "No se ha podido leer el registro local de accesos."
            ) from exc

    def _write_unlocked(self, users: list[ObservedUser]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        payload = {
            "users": [
                user.model_dump(mode="json")
                for user in sorted(users, key=lambda item: item.email)
            ]
        }
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def list(self) -> list[ObservedUser]:
        with self._lock:
            return sorted(
                self._read_unlocked(),
                key=lambda user: user.last_seen_at,
                reverse=True,
            )

    def observe(self, identity: dict[str, object]) -> ObservedUser | None:
        if not identity.get("authenticated"):
            return None

        email = str(identity.get("email") or "").strip().lower()
        object_id = str(identity.get("oid") or "").strip()
        key = object_id or email
        if not key or not email:
            return None

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            users = self._read_unlocked()
            index = next(
                (
                    position
                    for position, user in enumerate(users)
                    if user.key == key or user.email == email
                ),
                None,
            )
            if index is None:
                observed = ObservedUser(
                    key=key,
                    email=email,
                    name=str(identity.get("name") or "").strip(),
                    first_seen_at=now,
                    last_seen_at=now,
                )
                users.append(observed)
            else:
                current = users[index]
                observed = current.model_copy(
                    update={
                        "key": key,
                        "email": email,
                        "name": str(identity.get("name") or current.name).strip(),
                        "last_seen_at": now,
                    }
                )
                users[index] = observed
            self._write_unlocked(users)
            return observed


_default_path = (
    Path(__file__).resolve().parents[3] / "data" / "finance" / "access" / "observed-users.json"
)
_configured_path = os.getenv("FINANCE_IMPUTER_ACCESS_LOG_PATH", "").strip()
observed_user_store = ObservedUserStore(
    Path(_configured_path).expanduser() if _configured_path else _default_path
)
