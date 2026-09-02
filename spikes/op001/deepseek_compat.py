from __future__ import annotations

import argparse
import json
import os
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ERROR_NAMES = {
    400: "invalid_format",
    401: "authentication_failed",
    402: "insufficient_balance",
    422: "invalid_parameters",
    429: "rate_limited",
    500: "server_error",
    503: "server_overloaded",
}


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def classify_error(status: int | None, reason: str | None = None) -> str:
    if status in ERROR_NAMES:
        return ERROR_NAMES[status]
    if reason == "timeout":
        return "timeout"
    return "transport_error" if status is None else "unexpected_http_error"


def request_json(url: str, key: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            return {"ok": True, "status": response.status, "latency_ms": (time.perf_counter() - started) * 1000, "body": body}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": classify_error(exc.code), "latency_ms": (time.perf_counter() - started) * 1000}
    except (TimeoutError, socket.timeout):
        return {"ok": False, "status": None, "error": classify_error(None, "timeout"), "latency_ms": (time.perf_counter() - started) * 1000}
    except urllib.error.URLError as exc:
        reason = "timeout" if isinstance(exc.reason, (TimeoutError, socket.timeout)) else "transport"
        return {"ok": False, "status": None, "error": classify_error(None, reason), "latency_ms": (time.perf_counter() - started) * 1000}


def redact_result(result: dict[str, Any], probe: str) -> dict[str, Any]:
    summary = {key: value for key, value in result.items() if key != "body"}
    body = result.get("body", {})
    if probe == "chat" and result.get("ok"):
        content = body["choices"][0]["message"].get("content", "")
        summary["content_matches"] = "OP001_OK" in content
    elif probe == "json" and result.get("ok"):
        content = body["choices"][0]["message"].get("content", "")
        try:
            parsed = json.loads(content)
            summary["json_valid"] = parsed.get("status") == "ok" and parsed.get("probe") == "op001"
        except (TypeError, json.JSONDecodeError):
            summary["json_valid"] = False
    elif probe == "tool" and result.get("ok"):
        calls = body["choices"][0]["message"].get("tool_calls", [])
        summary["tool_valid"] = bool(calls) and calls[0].get("function", {}).get("name") == "check_service_health"
        if calls:
            try:
                arguments = json.loads(calls[0]["function"]["arguments"])
                summary["arguments_valid"] = arguments == {"service": "superset"}
            except (KeyError, TypeError, json.JSONDecodeError):
                summary["arguments_valid"] = False
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    load_env(args.env)

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    key = os.getenv("DEEPSEEK_API_KEY", "")
    endpoint = f"{base_url}/chat/completions"

    result: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "base_url": base_url,
        "model": model,
        "timeout_seconds": timeout,
        "key_present": bool(key),
        "official_error_mapping": {str(code): name for code, name in ERROR_NAMES.items()},
        "mapping_assertions": all(classify_error(code) == name for code, name in ERROR_NAMES.items()),
    }

    invalid = request_json(endpoint, "op001-invalid-key", {"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}, timeout)
    result["invalid_key"] = redact_result(invalid, "invalid_key")

    timeout_probe = request_json("https://10.255.255.1/v1/chat/completions", "op001-timeout", {"model": model, "messages": []}, 0.25)
    result["timeout"] = redact_result(timeout_probe, "timeout")

    if key:
        probes = {
            "chat": {"model": model, "messages": [{"role": "user", "content": "Reply with exactly OP001_OK"}], "max_tokens": 16},
            "json": {"model": model, "messages": [{"role": "system", "content": "Return JSON only."}, {"role": "user", "content": 'Return this JSON object: {"status":"ok","probe":"op001"}'}], "response_format": {"type": "json_object"}, "max_tokens": 64},
            "tool": {"model": model, "messages": [{"role": "user", "content": "Check the health of the superset service."}], "tools": [{"type": "function", "function": {"name": "check_service_health", "description": "Read a service health status", "parameters": {"type": "object", "properties": {"service": {"type": "string", "enum": ["superset"]}}, "required": ["service"], "additionalProperties": False}}}], "tool_choice": "required", "max_tokens": 128},
        }
        result["probes"] = {name: redact_result(request_json(endpoint, key, payload, timeout), name) for name, payload in probes.items()}
    else:
        result["probes"] = {"status": "blocked_missing_local_key"}

    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
