from time import monotonic, sleep
from typing import Any, cast
from uuid import UUID

import allure

from tests.framework.assertions import assert_http_status
from tests.framework.clients.wallet_api_client import WalletApiClient
from tests.framework.models import (
    TransactionData,
    UserData,
    UserWallet,
    WalletData,
)


class WalletSteps:
    """Readable business actions composed from lower-level API calls."""

    def __init__(self, client: WalletApiClient) -> None:
        self._client = client

    @allure.step("创建用户：{email}")
    def create_user(self, email: str) -> UserData:
        response = self._client.create_user(email)
        assert_http_status(response, 201)
        return UserData.from_json(_json_object(response.json()))

    @allure.step("为用户创建CNY钱包")
    def create_wallet(self, user: UserData) -> WalletData:
        response = self._client.create_wallet(user.id, user.api_key)
        assert_http_status(response, 201)
        return WalletData.from_json(_json_object(response.json()))

    @allure.step("创建用户及钱包：{email}")
    def create_user_with_wallet(self, email: str) -> UserWallet:
        user = self.create_user(email)
        wallet = self.create_wallet(user)
        return UserWallet(user=user, wallet=wallet)

    @allure.step("充值 {amount} 元")
    def deposit(
        self,
        user_wallet: UserWallet,
        amount: str,
        trace_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> TransactionData:
        response = self._client.deposit(
            user_wallet.wallet.id,
            amount,
            user_wallet.user.api_key,
            trace_id,
            idempotency_key,
        )
        assert_http_status(response, 201)
        return TransactionData.from_json(_json_object(response.json()))

    @allure.step("提现 {amount} 元")
    def withdraw(
        self,
        user_wallet: UserWallet,
        amount: str,
        idempotency_key: str | None = None,
    ) -> TransactionData:
        response = self._client.withdraw(
            user_wallet.wallet.id,
            amount,
            user_wallet.user.api_key,
            idempotency_key,
        )
        assert_http_status(response, 201)
        return TransactionData.from_json(_json_object(response.json()))

    @allure.step("转账 {amount} 元")
    def transfer(
        self,
        payer: UserWallet,
        payee: UserWallet,
        amount: str,
        idempotency_key: str | None = None,
    ) -> TransactionData:
        response = self._client.transfer(
            payer.wallet.id,
            payee.wallet.id,
            amount,
            payer.user.api_key,
            idempotency_key,
        )
        assert_http_status(response, 201)
        return TransactionData.from_json(_json_object(response.json()))

    @allure.step("查询钱包")
    def get_wallet(self, user_wallet: UserWallet) -> WalletData:
        response = self._client.get_wallet(
            user_wallet.wallet.id,
            user_wallet.user.api_key,
        )
        assert_http_status(response, 200)
        return WalletData.from_json(_json_object(response.json()))

    @allure.step("查询交易")
    def get_transaction(
        self,
        transaction_id: UUID,
        user: UserData,
    ) -> TransactionData:
        response = self._client.get_transaction(transaction_id, user.api_key)
        assert_http_status(response, 200)
        return TransactionData.from_json(_json_object(response.json()))

    @allure.step("退款 {amount} 元")
    def refund(
        self,
        transaction: TransactionData,
        payer: UserWallet,
        amount: str,
        idempotency_key: str | None = None,
    ) -> TransactionData:
        response = self._client.refund(
            transaction.id,
            amount,
            payer.user.api_key,
            idempotency_key,
        )
        assert_http_status(response, 201)
        return TransactionData.from_json(_json_object(response.json()))

    @allure.step("等待交易进入 {expected_status}")
    def wait_for_transaction_status(
        self,
        transaction_id: UUID,
        user: UserData,
        expected_status: str,
        timeout_seconds: float = 3.0,
        poll_interval_seconds: float = 0.1,
    ) -> TransactionData:
        deadline = monotonic() + timeout_seconds
        last_status = "NOT_QUERIED"
        while monotonic() < deadline:
            transaction = self.get_transaction(transaction_id, user)
            last_status = transaction.status
            if last_status == expected_status:
                return transaction
            remaining = deadline - monotonic()
            if remaining > 0:
                sleep(min(poll_interval_seconds, remaining))
        raise AssertionError(
            f"transaction {transaction_id} did not reach {expected_status} "
            f"within {timeout_seconds}s; last_status={last_status}"
        )


def _json_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssertionError(f"expected a JSON object, got {type(value).__name__}")
    return cast(dict[str, Any], value)
