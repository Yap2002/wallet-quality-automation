from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import (
    ChannelCallbackModel,
    FeeRuleModel,
    IdempotencyRecordModel,
    LedgerAccountModel,
    LedgerAccountType,
    LedgerDirection,
    LedgerEntryModel,
    TransactionModel,
    WalletModel,
)
from tests.integration.conftest import ApiClient

pytestmark = pytest.mark.integration


def register_user(api_client: ApiClient, email: str | None = None) -> dict[str, Any]:
    response = api_client.post(
        "/api/v1/users",
        json={"email": email or f"user-{uuid4()}@example.com"},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def auth_headers(
    user: dict[str, Any],
    trace_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {user['api_key']}",
        "Idempotency-Key": idempotency_key or f"test-{uuid4().hex}",
    }
    if trace_id is not None:
        headers["X-Trace-ID"] = trace_id
    return headers


def create_wallet(api_client: ApiClient, user: dict[str, Any]) -> dict[str, Any]:
    response = api_client.post(
        f"/api/v1/users/{user['id']}/wallets",
        headers=auth_headers(user),
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def deposit(
    api_client: ApiClient,
    user: dict[str, Any],
    wallet: dict[str, Any],
    amount: str,
) -> dict[str, Any]:
    response = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/deposits",
        headers=auth_headers(user),
        json={"amount": amount},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def test_create_user_wallet_and_query_balance(api_client: ApiClient) -> None:
    user = register_user(api_client, "  Graduate@example.com ")
    wallet = create_wallet(api_client, user)

    response = api_client.get(
        f"/api/v1/wallets/{wallet['id']}",
        headers=auth_headers(user),
    )

    assert user["email"] == "graduate@example.com"
    assert user["api_key"]
    assert response.status_code == 200
    assert response.json()["balance"] == "0.00"
    assert response.json()["currency"] == "CNY"


def test_reject_duplicate_email_and_second_wallet(api_client: ApiClient) -> None:
    user = register_user(api_client, "duplicate-api@example.com")
    create_wallet(api_client, user)

    duplicate_user = api_client.post(
        "/api/v1/users",
        json={"email": "DUPLICATE-API@example.com"},
    )
    duplicate_wallet = api_client.post(
        f"/api/v1/users/{user['id']}/wallets",
        headers=auth_headers(user),
    )

    assert duplicate_user.status_code == 409
    assert duplicate_user.json()["code"] == "EMAIL_ALREADY_EXISTS"
    assert duplicate_wallet.status_code == 409
    assert duplicate_wallet.json()["code"] == "WALLET_ALREADY_EXISTS"


def test_authentication_authorization_and_not_found(api_client: ApiClient) -> None:
    owner = register_user(api_client)
    stranger = register_user(api_client)
    wallet = create_wallet(api_client, owner)

    unauthenticated = api_client.get(f"/api/v1/wallets/{wallet['id']}")
    forbidden = api_client.get(
        f"/api/v1/wallets/{wallet['id']}",
        headers=auth_headers(stranger),
    )
    missing = api_client.get(
        f"/api/v1/wallets/{uuid4()}",
        headers=auth_headers(owner),
    )

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "AUTHENTICATION_REQUIRED"
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "PERMISSION_DENIED"
    assert missing.status_code == 404
    assert missing.json()["code"] == "RESOURCE_NOT_FOUND"


def test_deposit_updates_balance_transaction_and_balanced_ledger(
    api_client: ApiClient,
    db_session: Session,
) -> None:
    user = register_user(api_client)
    wallet = create_wallet(api_client, user)
    trace_id = "deposit-test-trace"

    response = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/deposits",
        headers=auth_headers(user, trace_id),
        json={"amount": "100.25"},
    )

    assert response.status_code == 201
    transaction = response.json()
    assert response.headers["X-Trace-ID"] == trace_id
    assert transaction["type"] == "DEPOSIT"
    assert transaction["status"] == "SUCCEEDED"
    assert transaction["amount"] == "100.25"
    assert transaction["trace_id"] == trace_id

    persisted_wallet = db_session.get(WalletModel, UUID(wallet["id"]))
    entries = db_session.scalars(
        select(LedgerEntryModel).where(LedgerEntryModel.transaction_id == UUID(transaction["id"]))
    ).all()
    assert persisted_wallet is not None
    assert persisted_wallet.balance == Decimal("100.25")
    assert persisted_wallet.version == 1
    assert len(entries) == 2
    assert {entry.direction for entry in entries} == {
        LedgerDirection.DEBIT.value,
        LedgerDirection.CREDIT.value,
    }
    assert sum(
        entry.amount for entry in entries if entry.direction == LedgerDirection.DEBIT.value
    ) == sum(entry.amount for entry in entries if entry.direction == LedgerDirection.CREDIT.value)


def test_withdrawal_success_and_insufficient_balance_has_no_money_effect(
    api_client: ApiClient,
    db_session: Session,
) -> None:
    user = register_user(api_client)
    wallet = create_wallet(api_client, user)
    deposit(api_client, user, wallet, "50.00")

    success = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/withdrawals",
        headers=auth_headers(user),
        json={"amount": "20.00"},
    )
    transaction_count_before_failure = db_session.scalar(
        select(func.count()).select_from(TransactionModel)
    )
    entry_count_before_failure = db_session.scalar(
        select(func.count()).select_from(LedgerEntryModel)
    )
    failed = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/withdrawals",
        headers=auth_headers(user),
        json={"amount": "31.00"},
    )

    db_session.expire_all()
    persisted_wallet = db_session.get(WalletModel, UUID(wallet["id"]))
    assert success.status_code == 201
    assert success.json()["status"] == "SUCCEEDED"
    assert failed.status_code == 409
    assert failed.json()["code"] == "INSUFFICIENT_BALANCE"
    assert persisted_wallet is not None
    assert persisted_wallet.balance == Decimal("30.00")
    assert (
        db_session.scalar(select(func.count()).select_from(TransactionModel))
        == transaction_count_before_failure
    )
    assert (
        db_session.scalar(select(func.count()).select_from(LedgerEntryModel))
        == entry_count_before_failure
    )


def test_transfer_preserves_total_balance_and_creates_two_entries(
    api_client: ApiClient,
    db_session: Session,
) -> None:
    payer = register_user(api_client)
    payee = register_user(api_client)
    payer_wallet = create_wallet(api_client, payer)
    payee_wallet = create_wallet(api_client, payee)
    deposit(api_client, payer, payer_wallet, "100.00")

    response = api_client.post(
        "/api/v1/transfers",
        headers=auth_headers(payer),
        json={
            "source_wallet_id": payer_wallet["id"],
            "destination_wallet_id": payee_wallet["id"],
            "amount": "40.00",
        },
    )

    assert response.status_code == 201
    transaction = response.json()
    assert transaction["type"] == "TRANSFER"
    assert transaction["status"] == "SUCCEEDED"

    db_session.expire_all()
    payer_after = db_session.get(WalletModel, UUID(payer_wallet["id"]))
    payee_after = db_session.get(WalletModel, UUID(payee_wallet["id"]))
    entries = db_session.scalars(
        select(LedgerEntryModel).where(LedgerEntryModel.transaction_id == UUID(transaction["id"]))
    ).all()
    assert payer_after is not None
    assert payee_after is not None
    assert payer_after.balance == Decimal("60.00")
    assert payee_after.balance == Decimal("40.00")
    assert payer_after.balance + payee_after.balance == Decimal("100.00")
    assert len(entries) == 2
    assert sum(entry.amount for entry in entries) == Decimal("80.00")


def test_highest_priority_fee_rule_is_charged_to_payer_and_credited_to_platform(
    api_client: ApiClient,
    db_session: Session,
) -> None:
    db_session.add_all(
        [
            FeeRuleModel(
                name="low-priority-fixed",
                fixed_fee=Decimal("9.00"),
                priority=10,
            ),
            FeeRuleModel(
                name="preferred-combined",
                fixed_fee=Decimal("1.00"),
                percentage_rate=Decimal("0.01"),
                minimum_fee=Decimal("2.00"),
                maximum_fee=Decimal("5.00"),
                priority=100,
            ),
        ]
    )
    db_session.flush()
    payer = register_user(api_client)
    payee = register_user(api_client)
    payer_wallet = create_wallet(api_client, payer)
    payee_wallet = create_wallet(api_client, payee)
    deposit(api_client, payer, payer_wallet, "100.00")

    quote = api_client.post(
        "/api/v1/fees/calculate",
        headers=auth_headers(payer),
        json={"amount": "40.00"},
    )
    transfer_response = api_client.post(
        "/api/v1/transfers",
        headers=auth_headers(payer),
        json={
            "source_wallet_id": payer_wallet["id"],
            "destination_wallet_id": payee_wallet["id"],
            "amount": "40.00",
        },
    )

    assert quote.status_code == 200
    assert quote.json()["fee_amount"] == "2.00"
    assert quote.json()["total_debit"] == "42.00"
    assert quote.json()["rule_name"] == "preferred-combined"
    assert transfer_response.status_code == 201
    transfer = transfer_response.json()
    assert transfer["fee_amount"] == "2.00"

    db_session.expire_all()
    payer_after = db_session.get(WalletModel, UUID(payer_wallet["id"]))
    payee_after = db_session.get(WalletModel, UUID(payee_wallet["id"]))
    entries = db_session.scalars(
        select(LedgerEntryModel).where(LedgerEntryModel.transaction_id == UUID(transfer["id"]))
    ).all()
    platform_account = db_session.scalar(
        select(LedgerAccountModel).where(
            LedgerAccountModel.account_type == LedgerAccountType.PLATFORM_FEE.value
        )
    )
    assert payer_after is not None
    assert payee_after is not None
    assert platform_account is not None
    assert payer_after.balance == Decimal("58.00")
    assert payee_after.balance == Decimal("40.00")
    assert len(entries) == 3
    assert sum(
        entry.amount for entry in entries if entry.direction == LedgerDirection.DEBIT.value
    ) == Decimal("42.00")
    assert sum(
        entry.amount for entry in entries if entry.direction == LedgerDirection.CREDIT.value
    ) == Decimal("42.00")


def test_higher_priority_fee_free_rule_waives_transfer_fee(
    api_client: ApiClient,
    db_session: Session,
) -> None:
    db_session.add_all(
        [
            FeeRuleModel(name="normal", fixed_fee=Decimal("5.00"), priority=10),
            FeeRuleModel(name="fee-free", is_fee_free=True, priority=100),
        ]
    )
    db_session.flush()
    user = register_user(api_client)

    response = api_client.post(
        "/api/v1/fees/calculate",
        headers=auth_headers(user),
        json={"amount": "100.00"},
    )

    assert response.status_code == 200
    assert response.json()["fee_amount"] == "0.00"
    assert response.json()["rule_name"] == "fee-free"


def test_reject_same_wallet_invalid_amount_and_unauthorized_source(
    api_client: ApiClient,
) -> None:
    owner = register_user(api_client)
    stranger = register_user(api_client)
    wallet = create_wallet(api_client, owner)

    same_wallet = api_client.post(
        "/api/v1/transfers",
        headers=auth_headers(owner),
        json={
            "source_wallet_id": wallet["id"],
            "destination_wallet_id": wallet["id"],
            "amount": "1.00",
        },
    )
    too_precise = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/deposits",
        headers=auth_headers(owner),
        json={"amount": "1.505"},
    )
    forbidden = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/withdrawals",
        headers=auth_headers(stranger),
        json={"amount": "1.00"},
    )

    assert same_wallet.status_code == 409
    assert same_wallet.json()["code"] == "SAME_WALLET_TRANSFER"
    assert too_precise.status_code == 422
    assert too_precise.json()["code"] == "INVALID_DOMAIN_VALUE"
    assert forbidden.status_code == 403


@pytest.mark.parametrize(
    "amount",
    ["0", "-0.01", "1.505", "1000000000000000000.00"],
)
def test_reject_invalid_deposit_boundaries(
    api_client: ApiClient,
    amount: str,
) -> None:
    user = register_user(api_client)
    wallet = create_wallet(api_client, user)

    response = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/deposits",
        headers=auth_headers(user, "invalid-amount-trace"),
        json={"amount": amount},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_DOMAIN_VALUE"
    assert response.json()["trace_id"] == "invalid-amount-trace"


def test_reject_json_number_for_money_and_invalid_email(api_client: ApiClient) -> None:
    user = register_user(api_client)
    wallet = create_wallet(api_client, user)

    numeric_amount = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/deposits",
        headers=auth_headers(user),
        json={"amount": 0.1},
    )
    invalid_email = api_client.post(
        "/api/v1/users",
        json={"email": "not-an-email"},
    )

    assert numeric_amount.status_code == 422
    assert numeric_amount.json()["code"] == "REQUEST_VALIDATION_FAILED"
    assert invalid_email.status_code == 422
    assert invalid_email.json()["code"] == "REQUEST_VALIDATION_FAILED"


def test_query_transaction_by_related_user_only(api_client: ApiClient) -> None:
    payer = register_user(api_client)
    payee = register_user(api_client)
    stranger = register_user(api_client)
    payer_wallet = create_wallet(api_client, payer)
    payee_wallet = create_wallet(api_client, payee)
    deposit(api_client, payer, payer_wallet, "10.00")
    transfer_response = api_client.post(
        "/api/v1/transfers",
        headers=auth_headers(payer),
        json={
            "source_wallet_id": payer_wallet["id"],
            "destination_wallet_id": payee_wallet["id"],
            "amount": "3.00",
        },
    )
    transaction_id = transfer_response.json()["id"]

    payee_query = api_client.get(
        f"/api/v1/transactions/{transaction_id}",
        headers=auth_headers(payee),
    )
    stranger_query = api_client.get(
        f"/api/v1/transactions/{transaction_id}",
        headers=auth_headers(stranger),
    )
    missing_query = api_client.get(
        f"/api/v1/transactions/{uuid4()}",
        headers=auth_headers(payer),
    )

    assert payee_query.status_code == 200
    assert payee_query.json()["id"] == transaction_id
    assert stranger_query.status_code == 403
    assert missing_query.status_code == 404


def test_same_idempotency_key_replays_deposit_without_second_money_effect(
    api_client: ApiClient,
    db_session: Session,
) -> None:
    user = register_user(api_client)
    wallet = create_wallet(api_client, user)
    idempotency_key = "deposit-retry-same-request"
    request_headers = auth_headers(user, idempotency_key=idempotency_key)

    first = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/deposits",
        headers=request_headers,
        json={"amount": "25.00"},
    )
    retried = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/deposits",
        headers=request_headers,
        json={"amount": "25.00"},
    )

    db_session.expire_all()
    persisted_wallet = db_session.get(WalletModel, UUID(wallet["id"]))
    records = db_session.scalars(
        select(IdempotencyRecordModel).where(
            IdempotencyRecordModel.user_id == UUID(user["id"]),
            IdempotencyRecordModel.idempotency_key == idempotency_key,
        )
    ).all()
    assert first.status_code == 201
    assert retried.status_code == 201
    assert retried.json()["id"] == first.json()["id"]
    assert persisted_wallet is not None
    assert persisted_wallet.balance == Decimal("25.00")
    assert len(records) == 1
    assert records[0].status == "COMPLETED"
    assert (
        len(
            db_session.scalars(
                select(LedgerEntryModel).where(
                    LedgerEntryModel.transaction_id == UUID(first.json()["id"])
                )
            ).all()
        )
        == 2
    )


def test_same_idempotency_key_with_different_payload_is_rejected(
    api_client: ApiClient,
    db_session: Session,
) -> None:
    user = register_user(api_client)
    wallet = create_wallet(api_client, user)
    idempotency_key = "deposit-key-cannot-change-payload"
    request_headers = auth_headers(user, idempotency_key=idempotency_key)

    first = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/deposits",
        headers=request_headers,
        json={"amount": "10.00"},
    )
    conflicting = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/deposits",
        headers=request_headers,
        json={"amount": "11.00"},
    )

    db_session.expire_all()
    persisted_wallet = db_session.get(WalletModel, UUID(wallet["id"]))
    assert first.status_code == 201
    assert conflicting.status_code == 409
    assert conflicting.json()["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert persisted_wallet is not None
    assert persisted_wallet.balance == Decimal("10.00")


def test_idempotency_replays_original_business_failure_after_balance_changes(
    api_client: ApiClient,
    db_session: Session,
) -> None:
    user = register_user(api_client)
    wallet = create_wallet(api_client, user)
    failed_key = "withdraw-original-failure"
    failed_headers = auth_headers(user, idempotency_key=failed_key)

    first_failure = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/withdrawals",
        headers=failed_headers,
        json={"amount": "5.00"},
    )
    deposit(api_client, user, wallet, "10.00")
    replayed_failure = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/withdrawals",
        headers=failed_headers,
        json={"amount": "5.00"},
    )

    db_session.expire_all()
    persisted_wallet = db_session.get(WalletModel, UUID(wallet["id"]))
    record = db_session.scalar(
        select(IdempotencyRecordModel).where(
            IdempotencyRecordModel.user_id == UUID(user["id"]),
            IdempotencyRecordModel.idempotency_key == failed_key,
        )
    )
    assert first_failure.status_code == 409
    assert first_failure.json()["code"] == "INSUFFICIENT_BALANCE"
    assert replayed_failure.status_code == 409
    assert replayed_failure.json()["code"] == "INSUFFICIENT_BALANCE"
    assert persisted_wallet is not None
    assert persisted_wallet.balance == Decimal("10.00")
    assert record is not None
    assert record.status == "FAILED"


def test_money_endpoint_requires_valid_idempotency_key(api_client: ApiClient) -> None:
    user = register_user(api_client)
    wallet = create_wallet(api_client, user)
    authorization_only = {"Authorization": f"Bearer {user['api_key']}"}

    missing = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/deposits",
        headers=authorization_only,
        json={"amount": "1.00"},
    )
    invalid = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/deposits",
        headers={**authorization_only, "Idempotency-Key": "bad key"},
        json={"amount": "1.00"},
    )

    assert missing.status_code == 422
    assert missing.json()["code"] == "REQUEST_VALIDATION_FAILED"
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "REQUEST_VALIDATION_FAILED"


def test_partial_and_full_refunds_restore_money_and_mark_original_refunded(
    api_client: ApiClient,
    db_session: Session,
) -> None:
    payer = register_user(api_client)
    payee = register_user(api_client)
    payer_wallet = create_wallet(api_client, payer)
    payee_wallet = create_wallet(api_client, payee)
    deposit(api_client, payer, payer_wallet, "100.00")
    transfer_response = api_client.post(
        "/api/v1/transfers",
        headers=auth_headers(payer),
        json={
            "source_wallet_id": payer_wallet["id"],
            "destination_wallet_id": payee_wallet["id"],
            "amount": "40.00",
        },
    )
    transfer_id = transfer_response.json()["id"]

    partial = api_client.post(
        f"/api/v1/transactions/{transfer_id}/refunds",
        headers=auth_headers(payer),
        json={"amount": "10.00"},
    )
    full = api_client.post(
        f"/api/v1/transactions/{transfer_id}/refunds",
        headers=auth_headers(payer),
        json={"amount": "30.00"},
    )
    exceeded = api_client.post(
        f"/api/v1/transactions/{transfer_id}/refunds",
        headers=auth_headers(payer),
        json={"amount": "0.01"},
    )

    db_session.expire_all()
    payer_after = db_session.get(WalletModel, UUID(payer_wallet["id"]))
    payee_after = db_session.get(WalletModel, UUID(payee_wallet["id"]))
    original = db_session.get(TransactionModel, UUID(transfer_id))
    refund_entries = db_session.scalars(
        select(LedgerEntryModel).where(
            LedgerEntryModel.transaction_id.in_(
                [UUID(partial.json()["id"]), UUID(full.json()["id"])]
            )
        )
    ).all()
    assert partial.status_code == 201
    assert partial.json()["parent_transaction_id"] == transfer_id
    assert full.status_code == 201
    assert exceeded.status_code == 409
    assert exceeded.json()["code"] == "REFUND_AMOUNT_EXCEEDED"
    assert payer_after is not None
    assert payee_after is not None
    assert original is not None
    assert payer_after.balance == Decimal("100.00")
    assert payee_after.balance == Decimal("0.00")
    assert original.status == "REFUNDED"
    assert len(refund_entries) == 4
    assert sum(
        entry.amount for entry in refund_entries if entry.direction == LedgerDirection.DEBIT.value
    ) == Decimal("40.00")
    assert sum(
        entry.amount for entry in refund_entries if entry.direction == LedgerDirection.CREDIT.value
    ) == Decimal("40.00")


def test_duplicate_refund_is_idempotent_and_non_payer_cannot_refund(
    api_client: ApiClient,
    db_session: Session,
) -> None:
    payer = register_user(api_client)
    payee = register_user(api_client)
    payer_wallet = create_wallet(api_client, payer)
    payee_wallet = create_wallet(api_client, payee)
    deposit(api_client, payer, payer_wallet, "20.00")
    transfer_response = api_client.post(
        "/api/v1/transfers",
        headers=auth_headers(payer),
        json={
            "source_wallet_id": payer_wallet["id"],
            "destination_wallet_id": payee_wallet["id"],
            "amount": "10.00",
        },
    )
    transfer_id = transfer_response.json()["id"]
    retry_key = "same-refund-must-only-run-once"
    retry_headers = auth_headers(payer, idempotency_key=retry_key)

    first = api_client.post(
        f"/api/v1/transactions/{transfer_id}/refunds",
        headers=retry_headers,
        json={"amount": "5.00"},
    )
    retry = api_client.post(
        f"/api/v1/transactions/{transfer_id}/refunds",
        headers=retry_headers,
        json={"amount": "5.00"},
    )
    forbidden = api_client.post(
        f"/api/v1/transactions/{transfer_id}/refunds",
        headers=auth_headers(payee),
        json={"amount": "1.00"},
    )

    db_session.expire_all()
    payer_after = db_session.get(WalletModel, UUID(payer_wallet["id"]))
    payee_after = db_session.get(WalletModel, UUID(payee_wallet["id"]))
    assert first.status_code == 201
    assert retry.status_code == 201
    assert retry.json()["id"] == first.json()["id"]
    assert forbidden.status_code == 403
    assert payer_after is not None
    assert payee_after is not None
    assert payer_after.balance == Decimal("15.00")
    assert payee_after.balance == Decimal("5.00")


def test_channel_deposit_success_and_duplicate_callback_have_one_money_effect(
    api_client: ApiClient,
    db_session: Session,
) -> None:
    user = register_user(api_client)
    wallet = create_wallet(api_client, user)
    started = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/channel-deposits",
        headers=auth_headers(user),
        json={"amount": "15.00"},
    )
    transaction_id = started.json()["id"]
    callback_body = {
        "event_id": "channel-event-success-001",
        "transaction_id": transaction_id,
        "status": "SUCCEEDED",
    }
    channel_headers = {"X-Channel-Token": "local-test-channel-token"}

    applied = api_client.post(
        "/api/v1/callbacks/channel",
        headers=channel_headers,
        json=callback_body,
    )
    duplicate = api_client.post(
        "/api/v1/callbacks/channel",
        headers=channel_headers,
        json=callback_body,
    )

    db_session.expire_all()
    persisted_wallet = db_session.get(WalletModel, UUID(wallet["id"]))
    entries = db_session.scalars(
        select(LedgerEntryModel).where(LedgerEntryModel.transaction_id == UUID(transaction_id))
    ).all()
    callback = db_session.scalar(
        select(ChannelCallbackModel).where(
            ChannelCallbackModel.event_id == callback_body["event_id"]
        )
    )
    assert started.status_code == 201
    assert started.json()["status"] == "PROCESSING"
    assert applied.status_code == 200
    assert applied.json()["outcome"] == "APPLIED"
    assert applied.json()["transaction_status"] == "SUCCEEDED"
    assert duplicate.status_code == 200
    assert duplicate.json()["outcome"] == "DUPLICATE"
    assert duplicate.json()["duplicate_count"] == 1
    assert persisted_wallet is not None
    assert persisted_wallet.balance == Decimal("15.00")
    assert len(entries) == 2
    assert callback is not None
    assert callback.duplicate_count == 1


def test_out_of_order_success_callback_is_ignored_after_channel_failure(
    api_client: ApiClient,
    db_session: Session,
) -> None:
    user = register_user(api_client)
    wallet = create_wallet(api_client, user)
    started = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/channel-deposits",
        headers=auth_headers(user),
        json={"amount": "8.00"},
    )
    transaction_id = started.json()["id"]
    channel_headers = {"X-Channel-Token": "local-test-channel-token"}

    failed = api_client.post(
        "/api/v1/callbacks/channel",
        headers=channel_headers,
        json={
            "event_id": "channel-event-failed-first",
            "transaction_id": transaction_id,
            "status": "FAILED",
        },
    )
    late_success = api_client.post(
        "/api/v1/callbacks/channel",
        headers=channel_headers,
        json={
            "event_id": "channel-event-success-late",
            "transaction_id": transaction_id,
            "status": "SUCCEEDED",
        },
    )

    db_session.expire_all()
    persisted_wallet = db_session.get(WalletModel, UUID(wallet["id"]))
    transaction = db_session.get(TransactionModel, UUID(transaction_id))
    assert failed.status_code == 200
    assert failed.json()["transaction_status"] == "FAILED"
    assert late_success.status_code == 200
    assert late_success.json()["outcome"] == "IGNORED_TERMINAL"
    assert late_success.json()["transaction_status"] == "FAILED"
    assert persisted_wallet is not None
    assert persisted_wallet.balance == Decimal("0.00")
    assert transaction is not None
    assert transaction.failure_code == "CHANNEL_REPORTED_FAILURE"


def test_injected_local_failure_rolls_back_and_same_callback_can_retry(
    api_client: ApiClient,
    db_session: Session,
) -> None:
    user = register_user(api_client)
    wallet = create_wallet(api_client, user)
    started = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/channel-deposits",
        headers=auth_headers(user),
        json={"amount": "12.00"},
    )
    transaction_id = started.json()["id"]
    callback_body = {
        "event_id": "channel-event-retry-after-fault",
        "transaction_id": transaction_id,
        "status": "SUCCEEDED",
    }
    channel_headers = {"X-Channel-Token": "local-test-channel-token"}

    injected_failure = api_client.post(
        "/api/v1/callbacks/channel",
        headers={**channel_headers, "X-Test-Fault": "BEFORE_LOCAL_UPDATE"},
        json=callback_body,
    )
    db_session.expire_all()
    before_retry_wallet = db_session.get(WalletModel, UUID(wallet["id"]))
    callback_before_retry = db_session.scalar(
        select(ChannelCallbackModel).where(
            ChannelCallbackModel.event_id == callback_body["event_id"]
        )
    )
    assert injected_failure.status_code == 500
    assert before_retry_wallet is not None
    assert before_retry_wallet.balance == Decimal("0.00")
    assert callback_before_retry is None

    retried = api_client.post(
        "/api/v1/callbacks/channel",
        headers=channel_headers,
        json=callback_body,
    )

    db_session.expire_all()
    after_retry_wallet = db_session.get(WalletModel, UUID(wallet["id"]))
    assert retried.status_code == 200
    assert retried.json()["outcome"] == "APPLIED"
    assert after_retry_wallet is not None
    assert after_retry_wallet.balance == Decimal("12.00")


def test_missing_callback_keeps_transaction_processing_without_fixed_sleep(
    api_client: ApiClient,
) -> None:
    user = register_user(api_client)
    wallet = create_wallet(api_client, user)
    started = api_client.post(
        f"/api/v1/wallets/{wallet['id']}/channel-deposits",
        headers=auth_headers(user),
        json={"amount": "3.00"},
    )

    queried = api_client.get(
        f"/api/v1/transactions/{started.json()['id']}",
        headers=auth_headers(user),
    )

    assert started.status_code == 201
    assert queried.status_code == 200
    assert queried.json()["status"] == "PROCESSING"
