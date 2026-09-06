from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database.models import (
    LedgerAccountModel,
    LedgerAccountType,
    UserModel,
    WalletModel,
)

pytestmark = pytest.mark.integration


def create_user(db_session: Session, email: str | None = None) -> UserModel:
    user = UserModel(
        email=email or f"test-{uuid4()}@example.com",
        api_key_hash="test-only-hash",
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_persist_exact_decimal_wallet_balance(db_session: Session) -> None:
    user = create_user(db_session)
    wallet = WalletModel(
        user_id=user.id,
        currency="CNY",
        balance=Decimal("10.25"),
    )
    db_session.add(wallet)
    db_session.flush()
    db_session.expire(wallet)

    persisted_wallet = db_session.scalar(select(WalletModel).where(WalletModel.id == wallet.id))

    assert persisted_wallet is not None
    assert persisted_wallet.balance == Decimal("10.25")


def test_reject_duplicate_user_email(db_session: Session) -> None:
    email = f"duplicate-{uuid4()}@example.com"
    create_user(db_session, email=email)
    db_session.add(UserModel(email=email, api_key_hash="another-hash"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_reject_second_cny_wallet_for_same_user(db_session: Session) -> None:
    user = create_user(db_session)
    db_session.add_all(
        [
            WalletModel(user_id=user.id, currency="CNY"),
            WalletModel(user_id=user.id, currency="CNY"),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_reject_negative_wallet_balance(db_session: Session) -> None:
    user = create_user(db_session)
    db_session.add(
        WalletModel(
            user_id=user.id,
            currency="CNY",
            balance=Decimal("-0.01"),
        )
    )

    with pytest.raises(DBAPIError):
        db_session.flush()


def test_reject_non_cny_wallet(db_session: Session) -> None:
    user = create_user(db_session)
    db_session.add(WalletModel(user_id=user.id, currency="USD"))

    with pytest.raises(DBAPIError):
        db_session.flush()


def test_restrict_deleting_user_with_wallet(db_session: Session) -> None:
    user = create_user(db_session)
    db_session.add(WalletModel(user_id=user.id, currency="CNY"))
    db_session.flush()

    db_session.delete(user)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_reject_duplicate_system_ledger_account_key(db_session: Session) -> None:
    account_key = f"SYSTEM:CHANNEL_CLEARING:TEST:{uuid4().hex}"
    db_session.add_all(
        [
            LedgerAccountModel(
                account_type=LedgerAccountType.CHANNEL_CLEARING.value,
                account_key=account_key,
                currency="CNY",
            ),
            LedgerAccountModel(
                account_type=LedgerAccountType.CHANNEL_CLEARING.value,
                account_key=account_key,
                currency="CNY",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()
