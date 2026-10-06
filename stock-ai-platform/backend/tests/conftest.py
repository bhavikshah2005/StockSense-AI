from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import engine, get_db
from app.core.rate_limit import MemoryRateLimiter, get_rate_limiter
from app.main import app
from app.services.email import RecordingEmailSender, get_email_sender


@pytest.fixture
def email_sender() -> RecordingEmailSender:
    return RecordingEmailSender()


@pytest.fixture
def client(email_sender: RecordingEmailSender) -> Iterator[TestClient]:
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
        join_transaction_mode="create_savepoint",
    )
    db = session_factory()

    def override_get_db() -> Iterator[Session]:
        try:
            yield db
        finally:
            pass

    limiter = MemoryRateLimiter()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    app.dependency_overrides[get_email_sender] = lambda: email_sender
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        db.close()
        transaction.rollback()
        connection.close()
