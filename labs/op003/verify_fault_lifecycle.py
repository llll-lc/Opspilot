"""Run the five OP-003 synthetic fault scenarios against only lab containers."""

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).parent
RUNTIME_FILE = LAB_ROOT / ".runtime" / "op003.env"
WEB_HEALTH_URL = "http://127.0.0.1:8088/health"
SCHEDULE_SERVICES = {
    "F-SCHED-01": "beat",
    "F-SCHED-02": "redis",
    "F-SCHED-03": "worker",
}
CONTAINER_NAMES = {
    "beat": "opspilot-op003-superset-beat",
    "redis": "opspilot-op003-superset-redis",
    "worker": "opspilot-op003-superset-worker",
}


def docker(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *arguments],
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def web_health_status() -> int:
    try:
        with urllib.request.urlopen(WEB_HEALTH_URL, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except urllib.error.URLError:
        return 0


def service_running(service: str) -> bool:
    result = docker("inspect", "--format", "{{.State.Running}}", CONTAINER_NAMES[service])
    if result.returncode != 0:
        return False
    return result.stdout.strip() == "true"


def run_scheduled_fault(scenario_id: str, service: str) -> list[dict[str, Any]]:
    repetitions: list[dict[str, Any]] = []
    for repetition in range(1, 4):
        docker("start", CONTAINER_NAMES[service])
        time.sleep(2)
        baseline = service_running(service) and web_health_status() == 200
        inject = docker("stop", CONTAINER_NAMES[service])
        time.sleep(1)
        active = (
            inject.returncode == 0 and not service_running(service) and web_health_status() == 200
        )
        recover = docker("start", CONTAINER_NAMES[service])
        time.sleep(2)
        clean = recover.returncode == 0 and service_running(service) and web_health_status() == 200
        repetitions.append(
            {
                "scenario_id": scenario_id,
                "repetition": repetition,
                "baseline": baseline,
                "fault_active": active,
                "clean": clean,
            }
        )
    return repetitions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if not RUNTIME_FILE.exists():
        raise SystemExit("Run prepare_lab.py before executing this lifecycle verifier.")

    all_runs: list[dict[str, Any]] = []
    for scenario_id, service in SCHEDULE_SERVICES.items():
        all_runs.extend(run_scheduled_fault(scenario_id, service))

    report = {
        "schema_version": "1.0.0",
        "suite_id": "op003-gate-a-synthetic-lab",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "profile": "target-reports",
        "scope": (
            "Only F-SCHED-01..03 use Docker test control; "
            "F-DB-01/F-AUTH-01 remain API/RBAC fixtures."
        ),
        "runs": all_runs,
        "passed": all(run["baseline"] and run["fault_active"] and run["clean"] for run in all_runs),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
