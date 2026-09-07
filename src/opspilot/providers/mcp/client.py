"""Bounded read-only MCP client hidden behind the stable Tool Gateway."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from opspilot.providers.runtime import ProviderFailure
from opspilot.tools.contracts import MCP_ALLOWLIST, mcp_catalog_hash


@dataclass(frozen=True)
class SupersetMcpProvider:
    url: str
    bearer_token: str
    timeout_seconds: float = 5.0
    max_response_bytes: int = 32_768

    def catalog_hash(self) -> str:
        response = self._rpc("tools/list", 2)
        tools = (
            response.get("result", {}).get("tools")
            if isinstance(response.get("result"), dict)
            else None
        )
        if not isinstance(tools, list):
            raise ProviderFailure("CATALOG_SCHEMA_INVALID", "MCP tool catalog was invalid")
        names: list[str] = []
        for item in tools:
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str):
                    names.append(name)
        names.sort()
        return mcp_catalog_hash(names)

    def invoke(self, upstream_tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        if upstream_tool_name not in MCP_ALLOWLIST:
            raise ProviderFailure("MCP_ALLOWLIST_REJECTED", "MCP tool is not approved")
        params = self._arguments(upstream_tool_name, arguments)
        response = self._rpc("tools/call", 3, {"name": upstream_tool_name, "arguments": params})
        result = response.get("result")
        if not isinstance(result, dict) or result.get("isError") is True:
            raise ProviderFailure("MCP_TOOL_FAILED", "MCP tool returned an error")
        structured = result.get("structuredContent")
        value = structured.get("result") if isinstance(structured, dict) else None
        return self._normalize(upstream_tool_name, value)

    def _rpc(
        self, method: str, request_id: int, params: dict[str, object] | None = None
    ) -> dict[str, Any]:
        payload: dict[str, object] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        request = Request(
            self.url,
            data=json.dumps(payload).encode(),
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.bearer_token}",
                "MCP-Protocol-Version": "2025-03-26",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read(self.max_response_bytes + 1)
        except HTTPError as exc:
            error = "AUTHENTICATION_FAILED" if exc.code in {401, 403} else "MCP_HTTP_ERROR"
            raise ProviderFailure(error, "MCP request failed") from exc
        except TimeoutError as exc:
            raise ProviderFailure("TIMEOUT", "MCP request timed out") from exc
        except URLError as exc:
            raise ProviderFailure("CONNECTION_FAILED", "MCP connection failed") from exc
        if len(body) > self.max_response_bytes:
            raise ProviderFailure("RESPONSE_TOO_LARGE", "MCP response exceeded local limit")
        text = body.decode("utf-8", "replace")
        if text.startswith("event:"):
            lines = [line[6:] for line in text.splitlines() if line.startswith("data: ")]
            text = lines[-1] if lines else ""
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderFailure(
                "RESPONSE_SCHEMA_INVALID", "MCP response was invalid JSON"
            ) from exc
        if not isinstance(decoded, dict):
            raise ProviderFailure("RESPONSE_SCHEMA_INVALID", "MCP response was not an object")
        return decoded

    @staticmethod
    def _arguments(upstream_tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        external = arguments.get("external_resource_id")
        if upstream_tool_name.startswith("get_") and upstream_tool_name not in {
            "get_instance_info",
            "get_schema",
        }:
            if not isinstance(external, str) or not external.isdigit():
                raise ProviderFailure("INPUT_TRANSFORM_FAILED", "numeric resource id required")
            prefix = upstream_tool_name.removeprefix("get_").removesuffix("_info")
            return {f"{prefix}_id": int(external)}
        return {}

    @staticmethod
    def _normalize(upstream_tool_name: str, value: object) -> dict[str, object]:
        if upstream_tool_name == "health_check":
            return {
                "health_scope": "CONNECTOR",
                "data": {"status": "HEALTHY", "detail": "MCP connector reachable"},
                "correlation_id": None,
            }
        if upstream_tool_name == "get_instance_info":
            raw = value if isinstance(value, dict) else {}
            return {
                "health_scope": "APPLICATION",
                "data": {
                    "product": "Apache Superset",
                    "version": str(raw.get("version")) if raw.get("version") else None,
                },
                "correlation_id": None,
            }
        resource = (
            upstream_tool_name.removeprefix("list_")
            .removeprefix("get_")
            .removesuffix("_info")
            .upper()
        )
        rows = value if isinstance(value, list) else [value] if isinstance(value, dict) else []
        items = []
        for row in rows:
            if not isinstance(row, dict) or "id" not in row:
                raise ProviderFailure("RESPONSE_SCHEMA_INVALID", "MCP resource shape was invalid")
            name = next(
                (
                    row[key]
                    for key in (
                        "database_name",
                        "table_name",
                        "slice_name",
                        "dashboard_title",
                        "name",
                    )
                    if key in row
                ),
                None,
            )
            if name is None:
                raise ProviderFailure("RESPONSE_SCHEMA_INVALID", "MCP resource name was missing")
            items.append(
                {
                    "external_id": str(row["id"]),
                    "name": str(name),
                    "resource_type": resource.rstrip("S"),
                }
            )
        data: dict[str, object] = (
            {"items": items}
            if upstream_tool_name.startswith("list_")
            else {"item": items[0]}
            if items
            else {}
        )
        return {"health_scope": "APPLICATION", "data": data, "correlation_id": None}
