"""Exercise the real Superset REST health, invalid-connection and RBAC fixtures."""

import argparse
import http.cookiejar
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).parent
RUNTIME_FILE = LAB_ROOT / ".runtime" / "op003.env"
BASE_URL = "http://127.0.0.1:8088"
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def runtime_values() -> dict[str, str]:
    return dict(line.split("=", maxsplit=1) for line in RUNTIME_FILE.read_text().splitlines())


def call(
    path: str,
    method: str = "GET",
    token: str | None = None,
    body: Any = None,
    csrf_token: str | None = None,
) -> tuple[int, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if csrf_token:
        headers["X-CSRFToken"] = csrf_token
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with OPENER.open(request, timeout=10) as response:
            raw = response.read()
            return response.status, decode_body(raw)
    except urllib.error.HTTPError as error:
        raw = error.read()
        return error.code, decode_body(raw)


def decode_body(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw.decode("utf-8", "replace")


def login(username: str, password: str, refresh: bool = False) -> str:
    status, payload = call(
        "/api/v1/security/login",
        method="POST",
        body={"username": username, "password": password, "provider": "db", "refresh": refresh},
    )
    if status != 200 or not isinstance(payload, dict):
        raise RuntimeError(f"login failed: HTTP {status}")
    return str(payload["access_token"])


def result_items(payload: Any) -> list[dict[str, Any]]:
    result = payload.get("result", []) if isinstance(payload, dict) else []
    return [item for item in result if isinstance(item, dict)]


def ensure_restricted_database(admin: str, database_uri: str) -> tuple[int, str, bool, str]:
    _, csrf_payload = call("/api/v1/security/csrf_token/", token=admin)
    csrf_token = str(csrf_payload["result"])
    _, databases = call("/api/v1/database/?q=(page_size:100)", token=admin)
    existing = next(
        (
            item
            for item in result_items(databases)
            if item.get("database_name") == "OP003 Restricted"
        ),
        None,
    )
    if existing is not None:
        return int(existing["id"]), str(existing["database_name"]), False, csrf_token
    status, _created = call(
        "/api/v1/database/",
        "POST",
        admin,
        {
            "database_name": "OP003 Restricted",
            "sqlalchemy_uri": database_uri,
            "configuration_method": "sqlalchemy_form",
            "extra": "{}",
            "expose_in_sqllab": False,
            "allow_run_async": False,
        },
        csrf_token,
    )
    if status not in {200, 201}:
        raise RuntimeError(f"fixture database creation failed: HTTP {status}")
    _, databases = call("/api/v1/database/?q=(page_size:100)", token=admin)
    created_database = next(
        (
            item
            for item in result_items(databases)
            if item.get("database_name") == "OP003 Restricted"
        ),
        None,
    )
    if created_database is None:
        raise RuntimeError("fixture database was not visible to the admin after creation")
    return int(created_database["id"]), "OP003 Restricted", True, csrf_token


def remove_restricted_database(admin: str, database_id: int, csrf_token: str) -> bool:
    status, _ = call(f"/api/v1/database/{database_id}", "DELETE", admin, csrf_token=csrf_token)
    return status in {200, 202}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    values = runtime_values()
    admin = login("op003_admin", values["OP003_ADMIN_PASSWORD"], refresh=True)
    reader = login("op003_reader", values["OP003_READER_PASSWORD"])
    database_uri = (
        f"postgresql+psycopg2://superset:{values['OP003_DB_PASSWORD']}@metadata-db:5432/superset"
    )
    database_id, database_name, created, csrf_token = ensure_restricted_database(
        admin, database_uri
    )
    db_runs: list[dict[str, Any]] = []
    auth_runs: list[dict[str, Any]] = []
    invalid_payload = {
        "database_name": "OP003 invalid connection fixture",
        "sqlalchemy_uri": "postgresql+psycopg2://invalid:invalid@127.0.0.1:1/invalid",
        "configuration_method": "sqlalchemy_form",
        "extra": "{}",
    }
    for repetition in range(1, 4):
        health = call("/health")[0]
        db_status, _ = call("/api/v1/database/test_connection/", "POST", admin, invalid_payload)
        reader_get_status, reader_get_payload = call(
            f"/api/v1/database/{database_id}", token=reader
        )
        reader_list_status, reader_list_payload = call(
            "/api/v1/database/?q=(page_size:100)", token=reader
        )
        get_denied = reader_get_status in {401, 403, 404}
        get_filtered = database_name not in json.dumps(reader_get_payload, ensure_ascii=False)
        list_denied = reader_list_status in {401, 403, 404}
        list_filtered = database_name not in json.dumps(reader_list_payload, ensure_ascii=False)
        db_runs.append(
            {
                "scenario_id": "F-DB-01",
                "repetition": repetition,
                "baseline": health == 200,
                "fault_active": db_status >= 400,
                "clean": health == 200,
                "status": db_status,
            }
        )
        auth_runs.append(
            {
                "scenario_id": "F-AUTH-01",
                "repetition": repetition,
                "baseline": health == 200,
                "fault_active": (get_denied or get_filtered) and (list_denied or list_filtered),
                "clean": health == 200,
                "target_resource": {
                    "name": database_name,
                    "get": f"/api/v1/database/{database_id}",
                    "list": "/api/v1/database/?q=(page_size:100)",
                },
                "get": {
                    "status": reader_get_status,
                    "denied": get_denied,
                    "filtered": get_filtered,
                },
                "list": {
                    "status": reader_list_status,
                    "denied": list_denied,
                    "filtered": list_filtered,
                },
            }
        )
    removed = remove_restricted_database(admin, database_id, csrf_token)
    report = {
        "schema_version": "1.0.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runs": db_runs + auth_runs,
        "cleanup": {"created_fixture": created, "removed": removed},
        "passed": all(
            run["baseline"] and run["fault_active"] and run["clean"] for run in db_runs + auth_runs
        )
        and removed,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
