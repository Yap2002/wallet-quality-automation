from uuid import uuid4

import allure

from tests.framework.database import DatabaseClient
from tests.framework.models import UserData, UserWallet
from tests.framework.steps import WalletSteps


class TestDataFactory:
    """Create unique API data and clean it from the isolated test database."""

    __test__ = False

    def __init__(self, steps: WalletSteps, database: DatabaseClient) -> None:
        self._steps = steps
        self._database = database
        self._emails: set[str] = set()

    def unique_email(self, role: str = "user") -> str:
        return f"auto-{role}-{uuid4()}@example.com"

    @allure.step("准备测试用户：{role}")
    def create_user(
        self,
        role: str = "user",
        email: str | None = None,
    ) -> UserData:
        test_email = email or self.unique_email(role)
        self._emails.add(test_email.strip().lower())
        return self._steps.create_user(test_email)

    @allure.step("准备测试用户和钱包：{role}")
    def create_user_with_wallet(self, role: str = "user") -> UserWallet:
        email = self.unique_email(role)
        self._emails.add(email)
        return self._steps.create_user_with_wallet(email)

    @allure.step("清理当前用例创建的测试数据")
    def cleanup(self) -> None:
        self._database.cleanup_emails(self._emails)
