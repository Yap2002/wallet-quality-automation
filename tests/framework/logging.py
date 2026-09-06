import logging


def configure_test_logging() -> None:
    """Configure readable test logs without exposing request credentials."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
