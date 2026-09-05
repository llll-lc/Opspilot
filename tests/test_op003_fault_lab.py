"""Validate OP-003's declarative lab contract without starting Docker."""

import json
from pathlib import Path
from typing import Any, cast

LAB_ROOT = Path(__file__).parents[1] / "labs" / "op003"


def load_scenarios() -> dict[str, Any]:
    payload = json.loads((LAB_ROOT / "fault_scenarios.json").read_text(encoding="utf-8"))
    return cast(dict[str, Any], payload)


def test_gate_a_scenarios_are_machine_readable_and_safe() -> None:
    payload = load_scenarios()
    scenarios = payload["scenarios"]

    assert payload["schema_version"] == "1.0.0"
    assert payload["synthetic"] is True
    assert len(scenarios) == 5
    assert {scenario["id"] for scenario in scenarios} == {
        "F-DB-01",
        "F-AUTH-01",
        "F-SCHED-01",
        "F-SCHED-02",
        "F-SCHED-03",
    }
    assert all(scenario["synthetic"] is True for scenario in scenarios)
    assert all(scenario["required_observations"] for scenario in scenarios)
    assert all(scenario["forbidden_operations"] for scenario in scenarios)
    assert all(
        scenario["control"]["inject"] and scenario["control"]["recover"] for scenario in scenarios
    )


def test_health_scopes_keep_application_and_runtime_separate() -> None:
    scenarios = load_scenarios()["scenarios"]
    scheduled = [scenario for scenario in scenarios if scenario["family"] == "SCHEDULED_REPORT"]

    assert len(scheduled) == 3
    assert {scenario["root_cause_code"] for scenario in scheduled} == {
        "CELERY_BEAT_STOPPED",
        "CELERY_BROKER_UNAVAILABLE",
        "CELERY_WORKER_STOPPED",
    }
    assert all(scenario["health_scope"]["application"] == "HEALTHY" for scenario in scheduled)
    assert {scenario["health_scope"]["runtime"] for scenario in scheduled} == {
        "BEAT_UNHEALTHY",
        "REDIS_UNHEALTHY",
        "WORKER_UNHEALTHY",
    }


def test_mcp_lab_is_loopback_only_and_never_declares_native_write_tools_safe() -> None:
    compose = (LAB_ROOT / "compose.yml").read_text(encoding="utf-8")
    readme = (LAB_ROOT / "README.md").read_text(encoding="utf-8")
    verifier = (LAB_ROOT / "verify_mcp_gate.py").read_text(encoding="utf-8")
    lifecycle = (LAB_ROOT / "verify_fault_lifecycle.py").read_text(encoding="utf-8")

    assert '"127.0.0.1:5008:5008"' in compose
    assert "docker.sock" not in compose
    assert "execute_sql" in readme
    assert "原生只读闸门未通过" in readme
    assert "127.0.0.1:5008/mcp" in verifier
    assert "native_read_only_gate" in verifier
    assert '"response_size"' in verifier
    assert '"timeout"' in verifier
    assert "--response-token-limit" in verifier
    assert "--require-size-rejection" in verifier
    assert '"configured_limit"' in verifier
    assert "mcp_response_token_limit" in verifier
    assert '"container_environment_value"' in verifier
    assert '"size_guard_rejected"' in verifier
    assert '"verification_gate"' in verifier
    assert "PARTIAL_ONLY" not in verifier
    assert "SCHEDULE_SERVICES" in lifecycle
    assert "docker.sock" not in lifecycle


def test_auth_fixture_targets_a_named_database_and_removes_it_after_the_runs() -> None:
    verifier = (LAB_ROOT / "verify_api_fixtures.py").read_text(encoding="utf-8")

    assert "ensure_restricted_database" in verifier
    assert "remove_restricted_database" in verifier
    assert "OP003 Restricted" in verifier
    assert 'f"/api/v1/database/{database_id}"' in verifier
    assert '"/api/v1/database/?q=(page_size:100)"' in verifier
    assert '"target_resource"' in verifier
    assert '"denied"' in verifier
    assert '"filtered"' in verifier
    assert '"created_fixture"' in verifier
    assert '"removed"' in verifier
