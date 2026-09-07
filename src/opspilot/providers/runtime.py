"""Narrow Superset REST and runtime Probe Providers with fixed read-only surfaces."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import ClassVar, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class ProviderFailure(RuntimeError):
    """Provider transport/configuration failure, never a target-health conclusion."""

    def __init__(self, error_type: str, message: str, correlation_id: str | None = None) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.correlation_id = correlation_id


class RestTransport(Protocol):
    def get(self, path: str) -> tuple[int, bytes, str | None]: ...


@dataclass(frozen=True)
class UrllibRestTransport:
    base_url: str
    bearer_token: str | None = None
    timeout_seconds: float = 5.0
    max_response_bytes: int = 32_768

    def get(self, path: str) -> tuple[int, bytes, str | None]:
        headers = {"Accept": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        request = Request(f"{self.base_url.rstrip('/')}{path}", headers=headers, method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read(self.max_response_bytes + 1)
                correlation = response.headers.get("X-Request-Id")
                status = response.status
        except HTTPError as exc:
            error_type = "AUTHENTICATION_FAILED" if exc.code in {401, 403} else "REST_HTTP_ERROR"
            raise ProviderFailure(error_type, "Superset REST request failed") from exc
        except TimeoutError as exc:
            raise ProviderFailure("TIMEOUT", "Superset REST request timed out") from exc
        except URLError as exc:
            raise ProviderFailure("CONNECTION_FAILED", "Superset REST connection failed") from exc
        if len(body) > self.max_response_bytes:
            raise ProviderFailure("RESPONSE_TOO_LARGE", "Superset REST response exceeded limit")
        return status, body, correlation


@dataclass(frozen=True)
class SupersetRestProvider:
    """Transform fixed Superset GET endpoints into stable provider envelopes."""

    transport: RestTransport
    target_version: str = "6.1.0"

    _RESOURCES: ClassVar[dict[str, tuple[str, str, str]]] = {
        "databases": ("database", "database_name", "DATABASE"),
        "datasets": ("dataset", "table_name", "DATASET"),
        "charts": ("chart", "slice_name", "CHART"),
        "dashboards": ("dashboard", "dashboard_title", "DASHBOARD"),
    }

    def invoke(self, upstream_tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        if upstream_tool_name == "application_health":
            status, body, correlation = self.transport.get("/health")
            healthy = status == 200 and body.decode("utf-8", "replace").strip().upper() == "OK"
            return self._envelope(
                "APPLICATION",
                {"status": "HEALTHY" if healthy else "UNHEALTHY", "detail": "Superset Web/API"},
                correlation,
            )
        if upstream_tool_name == "instance_summary":
            status, _, correlation = self.transport.get("/health")
            if status != 200:
                raise ProviderFailure("REST_HTTP_ERROR", "Superset instance endpoint failed")
            return self._envelope(
                "APPLICATION",
                {"product": "Apache Superset", "version": self.target_version},
                correlation,
            )
        action, _, suffix = upstream_tool_name.partition("_")
        if action == "list":
            resource_key = suffix
        elif action == "get":
            resource_key = next(
                (key for key, (api_name, _, _) in self._RESOURCES.items() if api_name == suffix),
                "",
            )
        else:
            resource_key = ""
        if resource_key not in self._RESOURCES:
            raise ProviderFailure("UPSTREAM_TOOL_REJECTED", "unapproved REST observation")
        api_name, name_field, resource_type = self._RESOURCES[resource_key]
        if action == "list":
            path = f"/api/v1/{api_name}/?q=(page_size:50)"
        else:
            path = f"/api/v1/{api_name}/{quote(self._external_id(arguments), safe='')}"
        return self._resource_response(path, resource_type, action, name_field)

    def _resource_response(
        self, path: str, resource_type: str, action: str, name_field: str
    ) -> dict[str, object]:
        _, body, correlation = self.transport.get(path)
        try:
            raw = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ProviderFailure(
                "RESPONSE_SCHEMA_INVALID", "Superset REST returned invalid JSON"
            ) from exc
        if not isinstance(raw, dict):
            raise ProviderFailure(
                "RESPONSE_SCHEMA_INVALID", "Superset REST response was not an object"
            )
        values = raw.get("result")
        rows = values if isinstance(values, list) else [values] if isinstance(values, dict) else []
        items = [self._item(row, resource_type, name_field) for row in rows]
        data: dict[str, object] = (
            {"items": items} if action == "list" else {"item": items[0]} if items else {}
        )
        return self._envelope("APPLICATION", data, correlation)

    @staticmethod
    def _item(row: object, resource_type: str, name_field: str) -> dict[str, str]:
        if not isinstance(row, dict) or "id" not in row or name_field not in row:
            raise ProviderFailure("RESPONSE_SCHEMA_INVALID", "Superset resource shape was invalid")
        return {
            "external_id": str(row["id"]),
            "name": str(row[name_field]),
            "resource_type": resource_type,
        }

    @staticmethod
    def _external_id(arguments: dict[str, object]) -> str:
        value = arguments.get("external_resource_id")
        if not isinstance(value, str) or not value:
            raise ProviderFailure("INPUT_TRANSFORM_FAILED", "external resource mapping is required")
        return value

    @staticmethod
    def _envelope(
        scope: str, data: dict[str, object], correlation: str | None
    ) -> dict[str, object]:
        return {"health_scope": scope, "data": data, "correlation_id": correlation}


@dataclass(frozen=True)
class RuntimeProbeProvider:
    """Bounded TCP reachability probe; UNKNOWN is returned where liveness cannot be proven."""

    endpoints: dict[str, tuple[str, int]]
    timeout_seconds: float = 1.0

    def invoke(self, upstream_tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        if upstream_tool_name != "runtime_health":
            raise ProviderFailure("UPSTREAM_TOOL_REJECTED", "unapproved runtime probe")
        component = arguments.get("component")
        if not isinstance(component, str) or component not in {"worker", "beat", "redis"}:
            raise ProviderFailure("INPUT_TRANSFORM_FAILED", "invalid runtime component")
        endpoint = self.endpoints.get(component)
        if endpoint is None:
            data = {
                "status": "UNKNOWN",
                "component": component,
                "detail": "no approved liveness endpoint",
            }
        else:
            try:
                with socket.create_connection(endpoint, timeout=self.timeout_seconds):
                    data = {
                        "status": "HEALTHY",
                        "component": component,
                        "detail": "TCP endpoint reachable",
                    }
            except (OSError, TimeoutError):
                data = {
                    "status": "UNHEALTHY",
                    "component": component,
                    "detail": "TCP endpoint unreachable",
                }
        return {"health_scope": "RUNTIME_COMPONENT", "data": data, "correlation_id": None}
