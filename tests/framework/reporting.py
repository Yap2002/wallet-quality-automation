import allure


def describe_test(title: str, story: str) -> None:
    """Apply Allure metadata behind one typed third-party boundary."""
    allure.dynamic.feature("电子钱包接口")  # type: ignore[no-untyped-call]
    allure.dynamic.story(story)  # type: ignore[no-untyped-call]
    allure.dynamic.title(title)  # type: ignore[no-untyped-call]
