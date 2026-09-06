# GitHub Actions acceptance evidence

Repository: `Yap2002/wallet-quality-automation` (private)

## Quality workflow

- Run: `34029496130`
- Commit: `2a08456c9bcca0e9a7842d7cafa129155f7a1807`
- Result: SUCCESS
- API, database and financial regression: 115 passed
- Transaction concurrency gate: 1 passed
- Playwright UI smoke: 3 passed
- Newman: 10 requests, 10 assertions, 0 failed
- Ruff: passed
- Ruff format: 89 files checked
- mypy: 80 source files checked, no issues
- Allure HTML: generated
- Artifact: `wallet-quality-evidence`, approximately 1.75 MB

## Performance workflow

- Run: `34029702689`
- Result: SUCCESS
- Load: 10 users for 30 seconds
- Requests: 503
- Failures: 0
- Average response time: 13 ms
- P95 response time: 32 ms
- Throughput: approximately 17.07 requests per second
- Artifact: `locust-performance-results`, approximately 333 KB

The performance figures are a short baseline from one GitHub-hosted runner. They
demonstrate that the workload and thresholds execute correctly; they are not a
production capacity claim.
