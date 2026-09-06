from decimal import Decimal

import allure
import requests

from tests.framework.database import LedgerEntrySnapshot, WalletSnapshot
from tests.framework.models import TransactionData


def assert_http_status(response: requests.Response, expected: int) -> None:
    with allure.step(f"断言HTTP状态码为 {expected}"):
        assert response.status_code == expected, (
            f"{response.request.method} {response.request.url} expected HTTP "
            f"{expected}, got {response.status_code}; response={response.text}"
        )


def assert_error_response(
    response: requests.Response,
    expected_status: int,
    expected_code: str,
) -> None:
    assert_http_status(response, expected_status)
    body = response.json()
    with allure.step(f"断言业务错误码为 {expected_code}"):
        assert body.get("code") == expected_code, (
            f"expected error code {expected_code}, got {body.get('code')}; response={body}"
        )
        assert body.get("trace_id"), f"error response has no trace_id: {body}"


def assert_succeeded_transaction(
    transaction: TransactionData,
    expected_type: str,
    expected_amount: Decimal,
) -> None:
    with allure.step("断言交易成功且金额正确"):
        assert transaction.status == "SUCCEEDED", (
            f"transaction {transaction.id} status is {transaction.status}"
        )
        assert transaction.type == expected_type, (
            f"transaction {transaction.id} type expected {expected_type}, got {transaction.type}"
        )
        assert transaction.amount == expected_amount, (
            f"transaction {transaction.id} amount expected {expected_amount}, "
            f"got {transaction.amount}"
        )
        assert transaction.completed_at is not None, (
            f"transaction {transaction.id} has no completed_at"
        )


def assert_wallet_balance(
    wallet: WalletSnapshot,
    expected: Decimal,
) -> None:
    with allure.step(f"断言数据库钱包余额为 {expected}"):
        assert wallet.balance == expected, (
            f"wallet {wallet.id} balance expected {expected}, got {wallet.balance}"
        )
        assert wallet.balance >= Decimal("0.00"), (
            f"wallet {wallet.id} has negative balance {wallet.balance}"
        )


def assert_balanced_entries(entries: list[LedgerEntrySnapshot]) -> None:
    with allure.step("断言账务分录借贷平衡"):
        debit = sum(
            (entry.amount for entry in entries if entry.direction == "DEBIT"),
            start=Decimal("0.00"),
        )
        credit = sum(
            (entry.amount for entry in entries if entry.direction == "CREDIT"),
            start=Decimal("0.00"),
        )
        assert entries, "transaction has no ledger entries"
        assert debit == credit, (
            f"ledger is not balanced: debit={debit}, credit={credit}, entries={entries}"
        )
