from decimal import Decimal

import pytest
from playwright.sync_api import Page, expect

from tests.framework.factories import TestDataFactory
from tests.framework.steps import WalletSteps

pytestmark = [pytest.mark.ui, pytest.mark.integration, pytest.mark.smoke]


def open_wallet_console(
    page: Page,
    live_service_url: str,
    api_key: str,
    wallet_id: object,
) -> None:
    page.goto(f"{live_service_url}/wallet")
    page.get_by_test_id("api-key").fill(api_key)
    page.get_by_test_id("wallet-id").fill(str(wallet_id))


def test_query_wallet_balance_in_browser(
    page: Page,
    live_service_url: str,
    test_data_factory: TestDataFactory,
    wallet_steps: WalletSteps,
) -> None:
    owner = test_data_factory.create_user_with_wallet("ui-balance")
    wallet_steps.deposit(owner, "88.20")
    open_wallet_console(page, live_service_url, owner.user.api_key, owner.wallet.id)

    page.get_by_test_id("query-balance").click()

    expect(page.get_by_test_id("balance")).to_have_text("88.20")
    expect(page.get_by_test_id("result")).to_contain_text("余额查询成功")


def test_successful_transfer_in_browser(
    page: Page,
    live_service_url: str,
    test_data_factory: TestDataFactory,
    wallet_steps: WalletSteps,
) -> None:
    payer = test_data_factory.create_user_with_wallet("ui-payer")
    payee = test_data_factory.create_user_with_wallet("ui-payee")
    wallet_steps.deposit(payer, "50.00")
    open_wallet_console(page, live_service_url, payer.user.api_key, payer.wallet.id)
    page.get_by_test_id("destination-wallet-id").fill(str(payee.wallet.id))
    page.get_by_test_id("amount").fill("20.00")

    page.get_by_test_id("submit-transfer").click()

    expect(page.get_by_test_id("result")).to_contain_text("余额查询成功")
    expect(page.get_by_test_id("balance")).to_have_text("30.00")
    assert wallet_steps.get_wallet(payee).balance == Decimal("20.00")


def test_insufficient_balance_is_shown_in_browser(
    page: Page,
    live_service_url: str,
    test_data_factory: TestDataFactory,
) -> None:
    payer = test_data_factory.create_user_with_wallet("ui-empty-payer")
    payee = test_data_factory.create_user_with_wallet("ui-empty-payee")
    open_wallet_console(page, live_service_url, payer.user.api_key, payer.wallet.id)
    page.get_by_test_id("destination-wallet-id").fill(str(payee.wallet.id))
    page.get_by_test_id("amount").fill("1.00")

    page.get_by_test_id("submit-transfer").click()

    expect(page.get_by_test_id("result")).to_contain_text("INSUFFICIENT_BALANCE")
    expect(page.get_by_test_id("result")).to_have_attribute("data-kind", "error")
