from decimal import Decimal
from uuid import uuid4

import pytest

from tests.framework.assertions import (
    assert_balanced_entries,
    assert_error_response,
    assert_http_status,
    assert_succeeded_transaction,
    assert_wallet_balance,
)
from tests.framework.clients.wallet_api_client import WalletApiClient
from tests.framework.database import DatabaseClient
from tests.framework.factories import TestDataFactory
from tests.framework.reporting import describe_test
from tests.framework.steps import WalletSteps

pytestmark = [
    pytest.mark.regression,
    pytest.mark.integration,
]


def test_deposit_and_withdrawal_consistency(
    test_data_factory: TestDataFactory,
    wallet_steps: WalletSteps,
    database_client: DatabaseClient,
) -> None:
    describe_test(
        "充值和提现后接口余额、数据库余额及账务分录一致",
        "充值与提现",
    )
    owner = test_data_factory.create_user_with_wallet("owner")

    deposit = wallet_steps.deposit(owner, "100.25", trace_id="regression-deposit")
    withdrawal = wallet_steps.withdraw(owner, "20.00")
    wallet_from_api = wallet_steps.get_wallet(owner)
    wallet_from_database = database_client.get_wallet(owner.wallet.id)

    assert_succeeded_transaction(deposit, "DEPOSIT", Decimal("100.25"))
    assert_succeeded_transaction(withdrawal, "WITHDRAWAL", Decimal("20.00"))
    assert wallet_from_api.balance == Decimal("80.25")
    assert_wallet_balance(wallet_from_database, Decimal("80.25"))
    assert_balanced_entries(database_client.get_entries(deposit.id))
    assert_balanced_entries(database_client.get_entries(withdrawal.id))


def test_transfer_conserves_wallet_total(
    test_data_factory: TestDataFactory,
    wallet_steps: WalletSteps,
    database_client: DatabaseClient,
) -> None:
    describe_test(
        "转账保持系统资金总额不变且付款方和收款方都能查询交易",
        "钱包转账",
    )
    payer = test_data_factory.create_user_with_wallet("payer")
    payee = test_data_factory.create_user_with_wallet("payee")
    wallet_steps.deposit(payer, "100.00")

    transfer = wallet_steps.transfer(payer, payee, "40.00")
    payer_after = database_client.get_wallet(payer.wallet.id)
    payee_after = database_client.get_wallet(payee.wallet.id)
    payer_view = wallet_steps.get_transaction(transfer.id, payer.user)
    payee_view = wallet_steps.get_transaction(transfer.id, payee.user)

    assert_succeeded_transaction(transfer, "TRANSFER", Decimal("40.00"))
    assert_wallet_balance(payer_after, Decimal("60.00"))
    assert_wallet_balance(payee_after, Decimal("40.00"))
    assert payer_after.balance + payee_after.balance == Decimal("100.00")
    assert payer_view.id == transfer.id
    assert payee_view.id == transfer.id
    assert_balanced_entries(database_client.get_entries(transfer.id))


def test_wallet_authentication_and_permission(
    test_data_factory: TestDataFactory,
    wallet_api_client: WalletApiClient,
) -> None:
    describe_test("未认证用户和无关用户不能查询他人钱包", "认证与权限")
    owner = test_data_factory.create_user_with_wallet("owner")
    stranger = test_data_factory.create_user("stranger")

    missing_auth = wallet_api_client.get_wallet(owner.wallet.id, api_key=None)
    stranger_access = wallet_api_client.get_wallet(
        owner.wallet.id,
        api_key=stranger.api_key,
    )

    assert_error_response(missing_auth, 401, "AUTHENTICATION_REQUIRED")
    assert_error_response(stranger_access, 403, "PERMISSION_DENIED")


def test_insufficient_withdrawal_has_no_money_effect(
    test_data_factory: TestDataFactory,
    wallet_api_client: WalletApiClient,
    database_client: DatabaseClient,
) -> None:
    describe_test("余额不足的提现不产生余额、交易或账务影响", "异常交易")
    owner = test_data_factory.create_user_with_wallet("owner")
    transaction_count_before = database_client.count_transactions_for_wallet(owner.wallet.id)

    response = wallet_api_client.withdraw(
        owner.wallet.id,
        "0.01",
        owner.user.api_key,
    )

    assert_error_response(response, 409, "INSUFFICIENT_BALANCE")
    assert_wallet_balance(
        database_client.get_wallet(owner.wallet.id),
        Decimal("0.00"),
    )
    assert (
        database_client.count_transactions_for_wallet(owner.wallet.id) == transaction_count_before
    )


def test_duplicate_user_and_wallet_are_rejected(
    test_data_factory: TestDataFactory,
    wallet_api_client: WalletApiClient,
) -> None:
    describe_test("重复邮箱和同一用户重复创建CNY钱包被拒绝", "重复资源")
    email = test_data_factory.unique_email("duplicate")
    user = test_data_factory.create_user(email=email)
    first_wallet = wallet_api_client.create_wallet(user.id, user.api_key)
    duplicate_user = wallet_api_client.create_user(email.upper())
    duplicate_wallet = wallet_api_client.create_wallet(user.id, user.api_key)

    assert_http_status(first_wallet, 201)
    assert_error_response(duplicate_user, 409, "EMAIL_ALREADY_EXISTS")
    assert_error_response(duplicate_wallet, 409, "WALLET_ALREADY_EXISTS")


@pytest.mark.parametrize(
    "amount",
    ["0", "-0.01", "1.505", "1000000000000000000.00", 0.1],
    ids=["zero", "negative", "too-many-decimals", "too-large", "json-float"],
)
def test_invalid_deposit_amount_does_not_change_balance(
    amount: str | float,
    test_data_factory: TestDataFactory,
    wallet_api_client: WalletApiClient,
    database_client: DatabaseClient,
) -> None:
    describe_test("非法充值金额被拒绝且钱包保持零余额", "金额边界")
    owner = test_data_factory.create_user_with_wallet("boundary")

    response = wallet_api_client.deposit(
        owner.wallet.id,
        amount,
        owner.user.api_key,
    )

    assert response.status_code == 422
    assert response.json()["code"] in {
        "INVALID_DOMAIN_VALUE",
        "REQUEST_VALIDATION_FAILED",
    }
    assert_wallet_balance(
        database_client.get_wallet(owner.wallet.id),
        Decimal("0.00"),
    )
    assert database_client.count_transactions_for_wallet(owner.wallet.id) == 0


def test_same_wallet_transfer_is_rejected(
    test_data_factory: TestDataFactory,
    wallet_api_client: WalletApiClient,
) -> None:
    describe_test("禁止向同一个钱包转账", "非法转账")
    owner = test_data_factory.create_user_with_wallet("owner")

    response = wallet_api_client.transfer(
        owner.wallet.id,
        owner.wallet.id,
        "1.00",
        owner.user.api_key,
    )

    assert_error_response(response, 409, "SAME_WALLET_TRANSFER")


def test_missing_wallet_returns_clear_error(
    test_data_factory: TestDataFactory,
    wallet_api_client: WalletApiClient,
) -> None:
    describe_test("查询不存在的钱包返回明确错误", "不存在的资源")
    user = test_data_factory.create_user("query")

    response = wallet_api_client.get_wallet(uuid4(), user.api_key)

    assert_error_response(response, 404, "RESOURCE_NOT_FOUND")
