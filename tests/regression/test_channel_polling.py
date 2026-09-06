from uuid import UUID, uuid4

import pytest

from tests.framework.assertions import assert_http_status
from tests.framework.clients.wallet_api_client import WalletApiClient
from tests.framework.factories import TestDataFactory
from tests.framework.steps import WalletSteps

pytestmark = [pytest.mark.regression, pytest.mark.integration]


def test_channel_callback_is_observed_by_bounded_polling(
    test_data_factory: TestDataFactory,
    wallet_api_client: WalletApiClient,
    wallet_steps: WalletSteps,
) -> None:
    owner = test_data_factory.create_user_with_wallet("polling-owner")
    started_response = wallet_api_client.start_channel_deposit(
        owner.wallet.id,
        "6.00",
        owner.user.api_key,
    )
    assert_http_status(started_response, 201)
    transaction_id = UUID(started_response.json()["id"])
    callback = wallet_api_client.send_channel_callback(
        transaction_id,
        f"polling-event-{uuid4().hex}",
        "SUCCEEDED",
    )
    assert_http_status(callback, 200)

    transaction = wallet_steps.wait_for_transaction_status(
        transaction_id,
        owner.user,
        "SUCCEEDED",
        timeout_seconds=1,
        poll_interval_seconds=0.05,
    )

    assert transaction.status == "SUCCEEDED"
