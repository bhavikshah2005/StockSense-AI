"""Production settings and health endpoints. No secrets are printed."""

from pydantic import ValidationError

from app.core.config import Settings


def _production(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "database_url": "postgresql://user:secret@db.example:5432/stocksense",
        "redis_url": "rediss://default:secret@cache.example:6379",
        "frontend_url": "https://app.example",
        "cookie_secure": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_production_requires_https_cookie_and_hosted_redis() -> None:
    ready = _production()
    assert ready.app_env == "production"
    assert ready.cookie_secure is True
    for overrides in (
        {"cookie_secure": False},
        {"frontend_url": "http://localhost:5173"},
        {"redis_url": "redis://127.0.0.1:6379/0"},
        {"database_url": ""},
    ):
        try:
            _production(**overrides)
        except ValidationError:
            continue
        raise AssertionError("production settings accepted an unsafe value")


def test_live_does_not_require_a_body_secret(client) -> None:  # type: ignore[no-untyped-def]
    live = client.get("/live")
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert live.headers["x-content-type-options"] == "nosniff"
    assert live.headers["x-frame-options"] == "DENY"
    ready = client.get("/ready")
    assert ready.status_code == 200
    body = ready.json()
    assert body["database"] == "ok"
    assert body["redis"] in {"ok", "unavailable"}
    assert "password" not in ready.text.lower()
