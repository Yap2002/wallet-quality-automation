from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from tests.framework.assertions import assert_balanced_entries
from tests.framework.clients.wallet_api_client import WalletApiClient
from tests.framework.database import DatabaseClient
from tests.framework.factories import TestDataFactory
from tests.framework.steps import WalletSteps

pytestmark = [
    pytest.mark.concurrency,
    pytest.mark.integration,
    pytest.mark.regression,
]


def test_concurrent_withdrawals_never_overdraw_wallet(
    test_data_factory: TestDataFactory,
    wallet_steps: WalletSteps,
    wallet_api_client: WalletApiClient,
    database_client: DatabaseClient,
) -> None:
    owner = test_data_factory.create_user_with_wallet("concurrent-owner")
    wallet_steps.deposit(owner, "100.00")
    transaction_ids_before = set(database_client.get_transaction_ids_for_wallet(owner.wallet.id))

    def withdraw_once(index: int) -> int:
        response = wallet_api_client.withdraw(
            owner.wallet.id,
            "30.00",
            owner.user.api_key,
            idempotency_key=f"concurrent-withdrawal-{index:02d}",
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=10) as executor:
        statuses = list(executor.map(withdraw_once, range(10)))

    wallet_after = database_client.get_wallet(owner.wallet.id)
    transaction_ids_after = set(database_client.get_transaction_ids_for_wallet(owner.wallet.id))
    successful_withdrawal_ids = transaction_ids_after - transaction_ids_before
    assert statuses.count(201) == 3
    assert statuses.count(409) == 7
    assert wallet_after.balance == Decimal("10.00")
    assert wallet_after.balance >= Decimal("0.00")
    assert len(successful_withdrawal_ids) == 3
    for transaction_id in successful_withdrawal_ids:
        entries = database_client.get_entries(transaction_id)
        assert len(entries) == 2
        assert_balanced_entries(entries)
