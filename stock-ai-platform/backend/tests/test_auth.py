import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models import User, UserSession
from app.services.email import RecordingEmailSender

PASSWORD = "Validpass1"
ORIGIN = "http://localhost:5173"


def _email() -> str:
    return f"user-{uuid.uuid4().hex}@example.com"


def _register(client: TestClient, email: str | None = None, full_name: str = "Ada Lovelace") -> tuple[str, dict]:
    address = email or _email()
    response = client.post(
        "/api/auth/register",
        json={"email": address, "password": PASSWORD, "full_name": full_name},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201, response.text
    return address, response.json()


def test_register_succeeds_without_secrets(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": _email(), "password": PASSWORD, "full_name": "Grace Hopper"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["full_name"] == "Grace Hopper"
    assert body["is_active"] is True
    assert "password" not in body
    assert "password_hash" not in body
    assert PASSWORD not in response.text
    set_cookie = response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "stocksense_session=" in set_cookie


def test_duplicate_registration(client: TestClient) -> None:
    email, _ = _register(client)
    response = client.post(
        "/api/auth/register",
        json={"email": email.upper(), "password": PASSWORD, "full_name": "Other"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "An account with this email already exists"


def test_invalid_email(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": PASSWORD, "full_name": "Ada"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 422


def test_weak_password(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": _email(), "password": "short", "full_name": "Ada"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 422


def test_login_success_and_me(client: TestClient) -> None:
    email, registered = _register(client)
    client.post("/api/auth/logout", headers={"Origin": ORIGIN})
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200
    assert response.json()["id"] == registered["id"]
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_incorrect_password_and_unknown_account_match(client: TestClient) -> None:
    email, _ = _register(client)
    wrong = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Wrongpass1"},
        headers={"Origin": ORIGIN},
    )
    missing = client.post(
        "/api/auth/login",
        json={"email": _email(), "password": "Wrongpass1"},
        headers={"Origin": ORIGIN},
    )
    assert wrong.status_code == 401
    assert missing.status_code == 401
    assert wrong.json()["detail"] == missing.json()["detail"] == "Invalid email or password"


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_expired_session(client: TestClient) -> None:
    _register(client)
    db = _db()
    db.execute(update(UserSession).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    db.commit()
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_logout_clears_session(client: TestClient) -> None:
    _register(client)
    assert client.get("/api/auth/me").status_code == 200
    logout = client.post("/api/auth/logout", headers={"Origin": ORIGIN})
    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_password_change_rotates_other_sessions(client: TestClient) -> None:
    email, _ = _register(client)
    other = TestClient(app)
    other.post(
        "/api/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert other.get("/api/auth/me").status_code == 200
    changed = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "Newpassword2"},
        headers={"Origin": ORIGIN},
    )
    assert changed.status_code == 204
    assert other.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me").status_code == 200
    old_login = client.post(
        "/api/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert old_login.status_code == 401
    new_login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Newpassword2"},
        headers={"Origin": ORIGIN},
    )
    assert new_login.status_code == 200
    other.close()


def test_profile_requires_auth_and_ignores_foreign_identity(client: TestClient) -> None:
    _, first = _register(client, full_name="User A")
    anonymous = TestClient(app)
    assert anonymous.get("/api/users/me").status_code == 401
    anonymous.close()
    client.cookies.clear()
    _, second = _register(client, full_name="User B")
    client.cookies.clear()
    client.post(
        "/api/auth/login",
        json={"email": first["email"], "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    blocked = client.patch(
        "/api/users/me",
        json={
            "full_name": "Still A",
            "id": second["id"],
            "is_active": False,
            "password_hash": "nope",
        },
        headers={"Origin": ORIGIN},
    )
    assert blocked.status_code == 422
    updated = client.patch(
        "/api/users/me",
        json={"full_name": "Still A"},
        headers={"Origin": ORIGIN},
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == first["id"]
    assert updated.json()["full_name"] == "Still A"
    assert updated.json()["is_active"] is True
    profile = client.get(f"/api/users/me?user_id={second['id']}")
    assert profile.json()["id"] == first["id"]
    assert profile.json()["email"] != second["email"]


def test_forgot_password_hides_account_existence(client: TestClient, email_sender: RecordingEmailSender) -> None:
    missing = client.post(
        "/api/auth/forgot-password",
        json={"email": _email()},
        headers={"Origin": ORIGIN},
    )
    email, _ = _register(client)
    found = client.post(
        "/api/auth/forgot-password",
        json={"email": email},
        headers={"Origin": ORIGIN},
    )
    assert missing.status_code == found.status_code == 200
    assert missing.json() == found.json()
    assert len(email_sender.messages) == 1
    assert email_sender.messages[0].recipient == email


def test_reset_password_is_single_use_and_revokes_sessions(
    client: TestClient,
    email_sender: RecordingEmailSender,
) -> None:
    email, _ = _register(client)
    assert client.get("/api/auth/me").status_code == 200
    client.post("/api/auth/forgot-password", json={"email": email}, headers={"Origin": ORIGIN})
    token = email_sender.messages[-1].reset_url.split("token=", 1)[1]
    reset = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "Resetpass9"},
        headers={"Origin": ORIGIN},
    )
    assert reset.status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    reused = client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "Resetpass9"},
        headers={"Origin": ORIGIN},
    )
    assert reused.status_code == 400
    old = client.post(
        "/api/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert old.status_code == 401
    new = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Resetpass9"},
        headers={"Origin": ORIGIN},
    )
    assert new.status_code == 200
    invalid = client.post(
        "/api/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "Resetpass9"},
        headers={"Origin": ORIGIN},
    )
    assert invalid.status_code == 400


def test_cors_allows_configured_origin_only(client: TestClient) -> None:
    allowed = client.options(
        "/api/auth/login",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    assert allowed.headers["access-control-allow-credentials"] == "true"
    blocked = client.options(
        "/api/auth/login",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert blocked.headers.get("access-control-allow-origin") != "https://evil.example"
    denied = client.post(
        "/api/auth/login",
        json={"email": "person@example.com", "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert denied.status_code == 403


def test_login_rate_limit(client: TestClient) -> None:
    original = settings.login_rate_limit
    settings.login_rate_limit = 2
    try:
        email = _email()
        statuses = [
            client.post(
                "/api/auth/login",
                json={"email": email, "password": "Wrongpass1"},
                headers={"Origin": ORIGIN},
            ).status_code
            for _ in range(3)
        ]
    finally:
        settings.login_rate_limit = original
    assert statuses == [401, 401, 429]


def test_users_are_isolated_rows(client: TestClient) -> None:
    email_a, user_a = _register(client, full_name="User A")
    client.cookies.clear()
    email_b, user_b = _register(client, full_name="User B")
    db = _db()
    rows = db.scalars(select(User).where(User.email.in_([email_a, email_b]))).all()
    assert {row.id for row in rows} == {uuid.UUID(user_a["id"]), uuid.UUID(user_b["id"])}
    owned = db.scalar(select(User).where(User.id == uuid.UUID(user_a["id"]), User.email == email_a))
    assert owned is not None
    assert owned.email != email_b


def _db() -> Session:
    override = app.dependency_overrides[get_db]
    return next(override())
