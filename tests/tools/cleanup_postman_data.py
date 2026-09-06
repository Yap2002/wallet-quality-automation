import argparse

from sqlalchemy import create_engine

from tests.framework.database import DatabaseClient


def cleanup_postman_run(database_url: str, run_id: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        DatabaseClient(engine).cleanup_emails(
            {
                f"postman-payer-{run_id}@example.com",
                f"postman-payee-{run_id}@example.com",
            }
        )
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean one Newman test run")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-id", required=True)
    arguments = parser.parse_args()
    cleanup_postman_run(arguments.database_url, arguments.run_id)


if __name__ == "__main__":
    main()
