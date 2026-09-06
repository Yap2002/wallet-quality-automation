import os
from collections.abc import Generator
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database import session as session_module
from app.infrastructure.database.models import UserModel

pytestmark = pytest.mark.integration


def build_test_factory() -> tuple[sessionmaker[Session], Engine]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("TEST_DATABASE_URL is required; integration tests must use real MySQL")
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False), engine


def test_request_session_commits_after_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory, engine = build_test_factory()
    email = f"commit-{uuid4()}@example.com"
    monkeypatch.setattr(session_module, "get_session_factory", lambda: factory)

    provider = cast(
        Generator[Session, None, None],
        session_module.get_db_session(),
    )
    request_session = next(provider)
    request_session.add(UserModel(email=email, api_key_hash="commit-test-hash"))
    with pytest.raises(StopIteration):
        next(provider)

    try:
        with factory() as verification_session:
            persisted_user = verification_session.scalar(
                select(UserModel).where(UserModel.email == email)
            )
            assert persisted_user is not None
    finally:
        with factory.begin() as cleanup_session:
            cleanup_session.execute(delete(UserModel).where(UserModel.email == email))
        engine.dispose()


def test_request_session_rolls_back_after_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory, engine = build_test_factory()
    email = f"rollback-{uuid4()}@example.com"
    monkeypatch.setattr(session_module, "get_session_factory", lambda: factory)

    provider = cast(
        Generator[Session, None, None],
        session_module.get_db_session(),
    )
    request_session = next(provider)
    request_session.add(UserModel(email=email, api_key_hash="rollback-test-hash"))
    with pytest.raises(RuntimeError, match="simulated request failure"):
        provider.throw(RuntimeError("simulated request failure"))

    with factory() as verification_session:
        persisted_user = verification_session.scalar(
            select(UserModel).where(UserModel.email == email)
        )
        assert persisted_user is None
    engine.dispose()
