from pathlib import Path

from apps.api.finance.access_registry import ObservedUserStore


def test_registry_ignores_unauthenticated_requests(tmp_path: Path) -> None:
    store = ObservedUserStore(tmp_path / "users.json")

    assert store.observe({"authenticated": False}) is None
    assert store.list() == []


def test_registry_persists_and_updates_observed_users(tmp_path: Path) -> None:
    path = tmp_path / "users.json"
    store = ObservedUserStore(path)

    first = store.observe(
        {
            "authenticated": True,
            "oid": "object-id",
            "email": "PERSONA@RSM.ES",
            "name": "Persona Inicial",
        }
    )
    updated = store.observe(
        {
            "authenticated": True,
            "oid": "object-id",
            "email": "persona@rsm.es",
            "name": "Persona Actualizada",
        }
    )

    assert first is not None
    assert updated is not None
    assert updated.email == "persona@rsm.es"
    assert updated.name == "Persona Actualizada"
    assert updated.first_seen_at == first.first_seen_at
    persisted = ObservedUserStore(path).list()
    assert len(persisted) == 1
    assert persisted[0].last_seen_at == updated.last_seen_at
