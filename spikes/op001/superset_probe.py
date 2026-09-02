from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(
    url: str,
    method: str = "GET",
    token: str | None = None,
    csrf_token: str | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[int, bytes]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if csrf_token:
        headers["X-CSRFToken"] = csrf_token
    request = urllib.request.Request(
        url,
        data=None if body is None else json.dumps(body).encode("utf-8"),
        headers=headers,
        method=method,
    )
    try:
        with OPENER.open(request, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8088")
    parser.add_argument("--username", default="op001_admin")
    parser.add_argument("--password", default="op001-admin-local-only")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    started = time.perf_counter()
    health_status, health_body = call(f"{base}/health")
    login_status, login_body = call(
        f"{base}/api/v1/security/login",
        method="POST",
        body={"username": args.username, "password": args.password, "provider": "db", "refresh": True},
    )
    if login_status != 200:
        raise SystemExit(f"login failed with HTTP {login_status}")
    token = json.loads(login_body)["access_token"]
    csrf_status, csrf_body = call(f"{base}/api/v1/security/csrf_token/", token=token)
    if csrf_status != 200:
        raise SystemExit(f"csrf token failed with HTTP {csrf_status}")
    csrf_token = json.loads(csrf_body)["result"]

    list_status, list_body = call(f"{base}/api/v1/database/?q={urllib.parse.quote('(page_size:100)')}", token=token)
    databases = json.loads(list_body).get("result", []) if list_status == 200 else []
    seed = next((item for item in databases if item.get("database_name") == "OP001 Target"), None)
    create_status: int | str = "already_present"
    create_error: dict[str, Any] | None = None
    if seed is None:
        create_status, create_body = call(
            f"{base}/api/v1/database/",
            method="POST",
            token=token,
            csrf_token=csrf_token,
            body={
                "database_name": "OP001 Target",
                "sqlalchemy_uri": "postgresql+psycopg2://superset:op001-local-only@metadata-db:5432/op001_target",
                "configuration_method": "sqlalchemy_form",
                "extra": "{}",
                "expose_in_sqllab": False,
                "allow_run_async": False,
            },
        )
        if create_status >= 400:
            try:
                raw_error = json.loads(create_body)
                create_error = {
                    "message": raw_error.get("message"),
                    "error_fields": sorted((raw_error.get("errors") or {}).keys()),
                }
            except (json.JSONDecodeError, AttributeError):
                create_error = {"message": "non-JSON API error", "error_fields": []}

    final_status, final_body = call(f"{base}/api/v1/database/?q={urllib.parse.quote('(page_size:100)')}", token=token)
    final_databases = json.loads(final_body).get("result", []) if final_status == 200 else []
    openapi_status, openapi_body = call(f"{base}/api/v1/_openapi", token=token)
    if openapi_status != 200:
        openapi_status, openapi_body = call(f"{base}/swagger/v1", token=token)
    openapi_paths: set[str] = set()
    if openapi_status == 200:
        try:
            openapi_paths = set(json.loads(openapi_body).get("paths", {}))
        except (json.JSONDecodeError, AttributeError):
            pass

    def has_openapi_path(fragment: str) -> bool:
        return any(fragment in path for path in openapi_paths)

    result = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "elapsed_seconds": time.perf_counter() - started,
        "health": {"status": health_status, "body": health_body.decode("utf-8", "replace")[:100]},
        "login_status": login_status,
        "csrf_status": csrf_status,
        "database_list_status": final_status,
        "seed_create_status": create_status,
        "seed_create_error": create_error,
        "seed_visible_via_api": any(item.get("database_name") == "OP001 Target" for item in final_databases),
        "openapi_status": openapi_status,
        "openapi_bytes": len(openapi_body),
        "openapi_sha256": hashlib.sha256(openapi_body).hexdigest() if openapi_status == 200 else None,
        "openapi_capabilities": {
            "dashboards": has_openapi_path("/dashboard"),
            "databases": has_openapi_path("/database"),
            "datasets": has_openapi_path("/dataset"),
            "report_schedules": has_openapi_path("/report"),
            "roles": has_openapi_path("/security/roles"),
            "users": has_openapi_path("/security/users"),
        },
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
