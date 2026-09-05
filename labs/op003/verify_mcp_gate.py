"""Probe only the isolated native Superset MCP server and write redacted evidence."""

import argparse
import base64
import hashlib
import hmac
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).parent
RUNTIME_FILE = LAB_ROOT / ".runtime" / "op003.env"
MCP_URL = "http://127.0.0.1:5008/mcp"
WEB_HEALTH_URL = "http://127.0.0.1:8088/health"
DANGEROUS_TOOL_PREFIXES = ("create_", "generate_", "update_", "save_", "execute_")
DANGEROUS_TOOL_NAMES = {"add_chart_to_existing_dashboard", "open_sql_lab_with_context"}


def load_runtime_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in RUNTIME_FILE.read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", maxsplit=1)
        values[key] = value
    return values


def base64_url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def jwt_for(subject: str, secret: str) -> str:
    header = base64_url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = base64_url(
        json.dumps(
            {
                "sub": subject,
                "scope": "superset:read",
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
            },
            separators=(",", ":"),
        ).encode()
    )
    signature = base64_url(
        hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


def decode_mcp_body(body: bytes) -> dict[str, Any] | None:
    text = body.decode("utf-8", "replace")
    if text.startswith("event:"):
        data_lines = [
            line.removeprefix("data: ") for line in text.splitlines() if line.startswith("data:")
        ]
        text = data_lines[-1] if data_lines else ""
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def request_mcp(
    payload: dict[str, Any], token: str | None, timeout_seconds: float = 10
) -> tuple[int, dict[str, Any] | None, int]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-03-26",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        MCP_URL,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
            return response.status, decode_mcp_body(body), len(body)
    except urllib.error.HTTPError as error:
        body = error.read()
        return error.code, decode_mcp_body(body), len(body)
    except (TimeoutError, urllib.error.URLError):
        return 0, None, 0


def request_web_health() -> int:
    try:
        with urllib.request.urlopen(WEB_HEALTH_URL, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def rpc(method: str, request_id: int, params: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def tool_names(response: dict[str, Any] | None) -> list[str]:
    if response is None:
        return []
    tools = response.get("result", {}).get("tools", [])
    return sorted(
        tool["name"]
        for tool in tools
        if isinstance(tool, dict) and isinstance(tool.get("name"), str)
    )


def is_dangerous_tool(name: str) -> bool:
    return name.startswith(DANGEROUS_TOOL_PREFIXES) or name in DANGEROUS_TOOL_NAMES


def docker_audit_observed() -> bool:
    completed = subprocess.run(
        ["docker", "logs", "--tail", "300", "opspilot-op003-superset-mcp"],
        capture_output=True,
        check=False,
    )
    output = (completed.stdout + completed.stderr).decode("utf-8", "replace")
    return "MCP tool call" in output or "mcp_tool_call" in output


def mcp_response_token_limit() -> int | None:
    completed = subprocess.run(
        [
            "docker",
            "exec",
            "opspilot-op003-superset-mcp",
            "printenv",
            "OP003_MCP_RESPONSE_TOKEN_LIMIT",
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    try:
        return int(completed.stdout.decode("utf-8", "replace").strip())
    except ValueError:
        return None


def result_count(response: dict[str, Any] | None) -> int | None:
    if response is None:
        return None
    structured = response.get("result", {}).get("structuredContent", {})
    result = structured.get("result") if isinstance(structured, dict) else None
    return len(result) if isinstance(result, list) else None


def tool_result_is_error(response: dict[str, Any] | None) -> bool:
    return bool(response and response.get("result", {}).get("isError"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--response-token-limit", required=True, type=int)
    parser.add_argument("--require-size-rejection", action="store_true")
    args = parser.parse_args()
    if args.response_token_limit < 1:
        raise ValueError("--response-token-limit must be positive")
    values = load_runtime_values()
    admin_token = jwt_for("op003_admin", values["OP003_MCP_JWT_SECRET"])
    reader_token = jwt_for("op003_reader", values["OP003_MCP_JWT_SECRET"])

    unauthenticated_status, _, _ = request_mcp(
        rpc(
            "initialize", 1, {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {}}
        ),
        None,
    )
    invalid_status, _, _ = request_mcp(
        rpc(
            "initialize", 2, {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {}}
        ),
        "invalid.token.value",
    )
    initialized_status, _, _ = request_mcp(
        rpc(
            "initialize", 3, {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {}}
        ),
        admin_token,
    )
    _, catalog, catalog_bytes = request_mcp(rpc("tools/list", 4), admin_token)
    names = tool_names(catalog)
    health_status, _, health_bytes = request_mcp(
        rpc("tools/call", 5, {"name": "health_check", "arguments": {}}), admin_token
    )
    size_status, size_response, size_bytes = request_mcp(
        rpc("tools/call", 7, {"name": "get_instance_info", "arguments": {}}), admin_token
    )
    timeout_status, _, _ = request_mcp(rpc("tools/list", 8), admin_token, 0.0001)
    reader_status, reader, _ = request_mcp(
        rpc("tools/call", 6, {"name": "list_databases", "arguments": {}}), reader_token
    )
    dangerous = [name for name in names if is_dangerous_tool(name)]
    size_guard_rejected = tool_result_is_error(size_response)
    container_token_limit = mcp_response_token_limit()
    size_guard_status = (
        "PASS"
        if size_guard_rejected
        and size_status == 200
        and container_token_limit == args.response_token_limit
        else "FAIL"
    )
    verification_status = (
        "FAIL" if args.require_size_rejection and size_guard_status != "PASS" else "PASS"
    )
    report = {
        "schema_version": "1.0.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target": {"image": "apache/superset:6.1.0-dev", "mcp_url": MCP_URL},
        "connector": {
            "initialize_status": initialized_status,
            "health_check_status": health_status,
            "health_check_response_bytes": health_bytes,
            "health_check_is_connector_evidence_only": True,
        },
        "application": {"web_health_status": request_web_health()},
        "runtime": {"profile": "target-mcp", "worker_beat_redis_status": "NOT_STARTED_BY_DESIGN"},
        "authentication": {
            "unauthenticated_status": unauthenticated_status,
            "invalid_jwt_status": invalid_status,
            "valid_jwt_status": initialized_status,
            "status": "PASS"
            if {unauthenticated_status, invalid_status} == {401} and initialized_status == 200
            else "FAIL",
        },
        "rbac": {
            "reader_list_databases_status": reader_status,
            "reader_response_has_error": bool(reader and "error" in reader),
            "reader_tool_is_error": tool_result_is_error(reader),
            "reader_database_count": result_count(reader),
            "status": "OBSERVED_REQUIRES_OP006_SERVER_POLICY",
        },
        "catalog": {
            "tool_count": len(names),
            "tool_names": names,
            "sha256": hashlib.sha256("\n".join(names).encode()).hexdigest(),
            "response_bytes": catalog_bytes,
            "dangerous_tools": dangerous,
            "native_read_only_gate": "PASS" if not dangerous else "FAIL",
        },
        "audit": {"native_log_observed": docker_audit_observed(), "status": "OBSERVED"},
        "response_and_timeout": {
            "response_size": {
                "request": {
                    "rpc_method": "tools/call",
                    "tool": "get_instance_info",
                    "arguments": {},
                },
                "configured_limit": {
                    "value": args.response_token_limit,
                    "unit": "tokens",
                    "container_environment_value": container_token_limit,
                    "matches_requested_value": container_token_limit == args.response_token_limit,
                },
                "tool": "get_instance_info",
                "status_code": size_status,
                "response_bytes": size_bytes,
                "size_guard_rejected": size_guard_rejected,
                "expected_outcome": (
                    "MCP tool result isError=true when the configured limit is exceeded"
                ),
                "status": size_guard_status,
                "fallback_direction": "Do not expose the raw catalog; OP-006 must use "
                "stable-tool allowlists and REST/read-only Probe fallback.",
            },
            "timeout": {
                "tool": "tools/list",
                "client_timeout_seconds": 0.0001,
                "status_code": timeout_status,
                "status": "PASS" if timeout_status == 0 else "FAIL",
            },
        },
        "fallback": {
            "status": "REQUIRED" if dangerous else "NOT_REQUIRED",
            "direction": (
                "OP-006 must use a fixed stable-tool allowlist with REST/read-only Probe "
                "fallback; do not expose this raw catalog."
            ),
        },
        "verification_gate": {
            "require_size_rejection": args.require_size_rejection,
            "status": verification_status,
            "process_exit_code": 1 if verification_status == "FAIL" else 0,
            "reason": (
                "The required response-size rejection was not observed."
                if verification_status == "FAIL"
                else "The required response-size rejection was observed or was not required."
            ),
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if verification_status == "FAIL":
        raise SystemExit("response-size verification gate failed; see the JSON report")


if __name__ == "__main__":
    main()
