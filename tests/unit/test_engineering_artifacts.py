from pathlib import Path
from xml.etree import ElementTree

import yaml

from performance.quality_gate import PerformanceThresholds, quality_gate_violations
from scripts.run_jmeter import _failed_sample_count

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_jmeter_plan_is_valid_xml_and_contains_required_quality_elements() -> None:
    plan = PROJECT_ROOT / "performance/wallet-api.jmx"
    root = ElementTree.parse(plan).getroot()
    rendered = plan.read_text(encoding="utf-8")

    assert root.tag == "jmeterTestPlan"
    assert "JSONPostProcessor" in rendered
    assert "ResponseAssertion" in rendered
    assert "DurationAssertion" in rendered
    assert "Idempotency-Key" in rendered


def test_jmeter_result_gate_fails_when_any_sample_failed(tmp_path: Path) -> None:
    result_file = tmp_path / "result.jtl"
    result_file.write_text(
        "timeStamp,label,success\n1,healthy,true\n2,broken,false\n",
        encoding="utf-8",
    )

    assert _failed_sample_count(result_file) == 1


def test_locust_quality_gate_checks_errors_latency_and_throughput() -> None:
    thresholds = PerformanceThresholds(
        max_failure_ratio=0.01,
        max_p95_ms=500,
        min_requests_per_second=10,
    )

    violations = quality_gate_violations(
        request_count=100,
        failure_ratio=0.02,
        p95_ms=800,
        requests_per_second=8,
        thresholds=thresholds,
    )

    assert len(violations) == 3
    assert "failure ratio" in violations[0]
    assert "p95" in violations[1]
    assert "throughput" in violations[2]


def test_ci_configuration_uses_credentials_and_avoids_docker_socket() -> None:
    jenkinsfile = (PROJECT_ROOT / "Jenkinsfile").read_text(encoding="utf-8")
    quality_workflow = (PROJECT_ROOT / ".github/workflows/quality.yml").read_text(encoding="utf-8")
    performance_workflow = (PROJECT_ROOT / ".github/workflows/performance.yml").read_text(
        encoding="utf-8"
    )
    compose = yaml.safe_load((PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8"))
    jenkins_image = (PROJECT_ROOT / "docker/jenkins/Dockerfile").read_text(encoding="utf-8")
    jenkins_volumes = compose["services"]["jenkins"]["volumes"]

    assert "wallet-test-database-url" in jenkinsfile
    assert "Transaction concurrency gate" in jenkinsfile
    assert "Run transaction concurrency gate" in quality_workflow
    assert "redis://127.0.0.1:6379/0" in quality_workflow
    assert "TEST_REDIS_URL" in quality_workflow
    assert "Run Postman/Newman contract flow" in quality_workflow
    assert "Generate Allure HTML report" in quality_workflow
    assert "allure-report/" in quality_workflow
    assert "--junitxml=junit-results/regression.xml" in quality_workflow
    assert "PERF_MAX_P95_MS" in performance_workflow
    assert "schedule:" in performance_workflow
    assert "cleanWs" in jenkinsfile
    assert "redis://redis:6379/0" in jenkinsfile
    assert "TEST_REDIS_URL" in jenkinsfile
    assert "retry(3)" in jenkinsfile
    assert "npm ci --prefer-offline --no-audit --no-fund" in jenkinsfile
    assert "allure generate" in jenkinsfile
    assert "allure-report/**" in jenkinsfile
    assert "junit-results/*.xml" in jenkinsfile
    assert "--junitxml=test-results/" not in quality_workflow
    assert "--junitxml=test-results/" not in jenkinsfile
    assert all("docker.sock" not in volume for volume in jenkins_volumes)
    assert "jenkins-plugin-cli" in jenkins_image
    assert "    git \\\n" in jenkins_image
    assert "    timestamper \\\n" in jenkins_image


def test_compose_uses_expected_mysql_service_set() -> None:
    compose = yaml.safe_load((PROJECT_ROOT / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert "mysql" in services
    assert set(services) == {"mysql", "redis", "app", "jenkins"}
    assert services["mysql"]["image"].endswith("mysql:8.4")
    assert "mysqladmin" in services["mysql"]["healthcheck"]["test"][1]
    assert services["app"]["environment"]["DATABASE_URL"].startswith("mysql+pymysql://")
