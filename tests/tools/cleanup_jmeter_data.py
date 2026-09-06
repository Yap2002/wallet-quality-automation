import argparse

from sqlalchemy import create_engine

from tests.framework.database import DatabaseClient


def cleanup_jmeter_run(database_url: str, run_id: str, threads: int) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        DatabaseClient(engine).cleanup_emails(
            {f"jmeter-{run_id}-{index}@example.com" for index in range(1, threads + 1)}
        )
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean one JMeter test run")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--threads", required=True, type=int)
    arguments = parser.parse_args()
    cleanup_jmeter_run(arguments.database_url, arguments.run_id, arguments.threads)


if __name__ == "__main__":
    main()
