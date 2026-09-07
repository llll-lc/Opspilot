from __future__ import annotations

import json
import time
import uuid
from email.message import Message
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from opspilot.api import dependencies
from opspilot.api.dependencies import get_authorization_context, get_session
from opspilot.api.routes import cases
from opspilot.db.enums import HealthScope, ProviderType, UserRole
from opspilot.main import create_app
from opspilot.providers import runtime
from opspilot.providers.mcp import client as mcp_client
from opspilot.providers.mcp.client import SupersetMcpProvider
from opspilot.providers.runtime import (
    ProviderFailure,
    RuntimeProbeProvider,
    SupersetRestProvider,
    UrllibRestTransport,
)
from opspilot.security.auth import AuthenticationFailed, HmacBearerAuthenticator, issue_test_token
from opspilot.support.services import AuthorizationContext, AuthorizationDenied, CaseConflict
from opspilot.tools.catalog import STABLE_READ_ONLY_TOOLS, health_scope_for
from opspilot.tools.contracts import mcp_catalog_hash
from opspilot.tools.seeding import canonical_hash, record_mcp_catalog


class FakeTransport:
    def __init__(self) -> None:
        self.paths: list[str] = []

    def get(self, path: str) -> tuple[int, bytes, str | None]:
        self.paths.append(path)
        if path == "/health":
            return 200, b"OK", "rest-correlation"
        api_name = path.split("/")[3]
        fields = {
            "database": "database_name",
            "dataset": "table_name",
            "chart": "slice_name",
            "dashboard": "dashboard_title",
        }
        name_field = fields[api_name]
        result = {"result": [{"id": 7, name_field: f"{api_name}-7"}]}
        return 200, json.dumps(result).encode(), None


def test_rest_and_probe_providers_cover_every_supported_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = FakeTransport()
    provider = SupersetRestProvider(transport)
    assert provider.invoke("application_health", {})["health_scope"] == "APPLICATION"
    assert provider.invoke("instance_summary", {})["data"] == {
        "product": "Apache Superset",
        "version": "6.1.0",
    }
    for plural, singular, resource_type in (
        ("databases", "database", "DATABASE"),
        ("datasets", "dataset", "DATASET"),
        ("charts", "chart", "CHART"),
        ("dashboards", "dashboard", "DASHBOARD"),
    ):
        listed = provider.invoke(f"list_{plural}", {})
        fetched = provider.invoke(f"get_{singular}", {"external_resource_id": "7"})
        listed_data = cast(dict[str, Any], listed["data"])
        fetched_data = cast(dict[str, Any], fetched["data"])
        assert listed_data["items"][0]["resource_type"] == resource_type
        assert fetched_data["item"]["external_id"] == "7"
    with pytest.raises(ProviderFailure, match="unapproved"):
        provider.invoke("delete_all", {})

    monkeypatch.setattr(
        "opspilot.providers.runtime.socket.create_connection", lambda *args, **kwargs: MagicMock()
    )
    probe = RuntimeProbeProvider({"worker": ("127.0.0.1", 9000)})
    assert probe.invoke("runtime_health", {"component": "worker"})["data"] == {
        "status": "HEALTHY",
        "component": "worker",
        "detail": "TCP endpoint reachable",
    }
    beat_data = cast(dict[str, Any], probe.invoke("runtime_health", {"component": "beat"})["data"])
    assert beat_data["status"] == "UNKNOWN"


class Response:
    def __init__(self, body: bytes, *, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.headers = {"X-Request-Id": "upstream-id"}

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        return self.body[:size]


def test_rest_transport_classifies_auth_connection_timeout_and_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "urlopen", lambda request, timeout: Response(b"OK"))
    assert UrllibRestTransport("http://target", "secret").get("/health") == (
        200,
        b"OK",
        "upstream-id",
    )
    for failure, expected in (
        (HTTPError("x", 401, "", Message(), None), "AUTHENTICATION_FAILED"),
        (URLError("offline"), "CONNECTION_FAILED"),
        (TimeoutError(), "TIMEOUT"),
    ):

        def fail(request: object, timeout: float, error: Exception = failure) -> Response:
            raise error

        monkeypatch.setattr(runtime, "urlopen", fail)
        with pytest.raises(ProviderFailure) as caught:
            UrllibRestTransport("http://target").get("/health")
        assert caught.value.error_type == expected
    monkeypatch.setattr(runtime, "urlopen", lambda request, timeout: Response(b"12345"))
    with pytest.raises(ProviderFailure) as oversized:
        UrllibRestTransport("http://target", max_response_bytes=4).get("/health")
    assert oversized.value.error_type == "RESPONSE_TOO_LARGE"


def test_mcp_provider_has_fixed_allowlist_catalog_and_bounded_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def respond(request: Any, timeout: float) -> Response:
        payload = json.loads(request.data)
        calls.append(payload)
        if payload["method"] == "tools/list":
            body: dict[str, object] = {"result": {"tools": [{"name": "health_check"}]}}
        else:
            body = {"result": {"structuredContent": {"result": {"status": "ok"}}}}
        return Response(json.dumps(body).encode())

    monkeypatch.setattr(mcp_client, "urlopen", respond)
    provider = SupersetMcpProvider("http://mcp", "signed-token")
    assert provider.catalog_hash() == mcp_catalog_hash(["health_check"])
    assert provider.invoke("health_check", {})["health_scope"] == "CONNECTOR"
    assert calls[-1]["params"]["name"] == "health_check"
    with pytest.raises(ProviderFailure) as forbidden:
        provider.invoke("execute_sql", {})
    assert forbidden.value.error_type == "MCP_ALLOWLIST_REJECTED"

    monkeypatch.setattr(mcp_client, "urlopen", lambda request, timeout: Response(b"xxxxx"))
    with pytest.raises(ProviderFailure) as oversized:
        SupersetMcpProvider("http://mcp", "token", max_response_bytes=4).catalog_hash()
    assert oversized.value.error_type == "RESPONSE_TOO_LARGE"


def test_mcp_provider_resource_shapes_and_transport_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def respond(request: Any, timeout: float) -> Response:
        payload = json.loads(request.data)
        name = payload.get("params", {}).get("name")
        value: object = (
            [{"id": 7, "table_name": "dataset-7"}]
            if name == "list_datasets"
            else {"id": 7, "dashboard_title": "dashboard-7"}
        )
        body = {"result": {"structuredContent": {"result": value}}}
        return Response(json.dumps(body).encode())

    monkeypatch.setattr(mcp_client, "urlopen", respond)
    provider = SupersetMcpProvider("http://mcp", "token")
    listed = provider.invoke("list_datasets", {})
    fetched = provider.invoke("get_dashboard_info", {"external_resource_id": "7"})
    assert cast(dict[str, Any], listed["data"])["items"][0]["resource_type"] == "DATASET"
    assert cast(dict[str, Any], fetched["data"])["item"]["name"] == "dashboard-7"
    with pytest.raises(ProviderFailure) as bad_identifier:
        provider.invoke("get_dashboard_info", {"external_resource_id": "not-numeric"})
    assert bad_identifier.value.error_type == "INPUT_TRANSFORM_FAILED"

    failures: list[tuple[object, str]] = [
        (HTTPError("x", 403, "", Message(), None), "AUTHENTICATION_FAILED"),
        (URLError("offline"), "CONNECTION_FAILED"),
        (TimeoutError(), "TIMEOUT"),
    ]
    for failure, expected in failures:

        def fail(request: object, timeout: float, error: object = failure) -> Response:
            raise cast(BaseException, error)

        monkeypatch.setattr(mcp_client, "urlopen", fail)
        with pytest.raises(ProviderFailure) as caught:
            provider.catalog_hash()
        assert caught.value.error_type == expected
    for body in (b"not-json", b"[]", b'{"result":{"tools":"bad"}}'):
        monkeypatch.setattr(
            mcp_client, "urlopen", lambda request, timeout, value=body: Response(value)
        )
        with pytest.raises(ProviderFailure):
            provider.catalog_hash()


def test_signed_bearer_authentication_precedes_server_scope_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "s" * 32
    now = int(time.time())
    token = issue_test_token(
        secret,
        subject="tenant-a/alice",
        token_id="login-1",
        issuer="opspilot",
        audience="opspilot-api",
        expires_at=now + 60,
        not_before=now - 1,
    )
    authenticator = HmacBearerAuthenticator(secret, issuer="opspilot", audience="opspilot-api")
    assert authenticator.verify(token, now=now).subject == "tenant-a/alice"
    tampered = f"{token[:-1]}{'A' if not token.endswith('A') else 'B'}"
    with pytest.raises(AuthenticationFailed):
        authenticator.verify(tampered, now=now)

    expected = AuthorizationContext(
        uuid.uuid4(), uuid.uuid4(), UserRole.SUPPORT, frozenset({uuid.uuid4()}), frozenset()
    )
    loader = MagicMock(return_value=expected)
    monkeypatch.setattr(dependencies, "load_context", loader)
    session = MagicMock()
    request = SimpleNamespace(
        headers={"Authorization": f"Bearer {token}"},
        app=SimpleNamespace(state=SimpleNamespace(authenticator=authenticator)),
    )
    assert get_authorization_context(cast(Any, request), session) is expected
    loader.assert_called_once_with(session, "tenant-a/alice")
    for headers in (
        {},
        {"X-OpsPilot-Actor-Id": str(uuid.uuid4())},
        {"Authorization": "Bearer bad"},
    ):
        request.headers = headers
        with pytest.raises(HTTPException) as rejected:
            get_authorization_context(cast(Any, request), MagicMock())
        assert rejected.value.status_code == 401


def test_bearer_claim_and_dependency_configuration_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "z" * 32
    now = int(time.time())
    with pytest.raises(ValueError):
        HmacBearerAuthenticator("short", issuer="issuer", audience="audience")
    verifier = HmacBearerAuthenticator(secret, issuer="issuer", audience="audience")

    def token(**overrides: object) -> str:
        values: dict[str, object] = {
            "subject": "subject",
            "token_id": "token-id",
            "issuer": "issuer",
            "audience": "audience",
            "expires_at": now + 60,
            "not_before": now - 1,
        }
        values.update(overrides)
        return issue_test_token(secret, **cast(Any, values))

    for invalid in (
        token(issuer="wrong"),
        token(expires_at=now),
        token(not_before=now + 1),
        token(subject=""),
        "one.two",
    ):
        with pytest.raises(AuthenticationFailed):
            verifier.verify(invalid, now=now)

    request = SimpleNamespace(
        headers={"Authorization": f"Bearer {token()}"}, app=SimpleNamespace(state=SimpleNamespace())
    )
    with pytest.raises(HTTPException) as unconfigured:
        get_authorization_context(cast(Any, request), MagicMock())
    assert unconfigured.value.status_code == 503
    request.app.state.authenticator = verifier
    monkeypatch.setattr(
        dependencies,
        "load_context",
        lambda session, subject: (_ for _ in ()).throw(AuthorizationDenied()),
    )
    with pytest.raises(HTTPException) as forbidden:
        get_authorization_context(cast(Any, request), MagicMock())
    assert forbidden.value.status_code == 403

    missing_db = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    with pytest.raises(HTTPException) as unavailable:
        next(get_session(cast(Any, missing_db)))
    assert unavailable.value.status_code == 503


def test_http_case_routes_use_injected_verified_context(monkeypatch: pytest.MonkeyPatch) -> None:
    target, actor = uuid.uuid4(), uuid.uuid4()
    context = AuthorizationContext(
        uuid.uuid4(), actor, UserRole.SUPPORT, frozenset({target}), frozenset()
    )
    fake_session = MagicMock()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: fake_session
    app.dependency_overrides[get_authorization_context] = lambda: context
    created = SimpleNamespace(id=uuid.uuid4(), target_system_id=target, status="OPEN", version=1)
    monkeypatch.setattr(cases, "create_case", lambda *args, **kwargs: created)
    client = TestClient(app)
    payload = {
        "target_system_id": str(target),
        "title": "t",
        "description": "d",
        "deduplication_key": "k",
    }
    assert client.post("/api/v1/cases", json=payload).status_code == 201
    monkeypatch.setattr(
        cases, "create_case", lambda *args, **kwargs: (_ for _ in ()).throw(AuthorizationDenied())
    )
    assert (
        client.post("/api/v1/cases", json={**payload, "deduplication_key": "k2"}).status_code == 403
    )
    monkeypatch.setattr(
        cases, "transition_case", lambda *args, **kwargs: (_ for _ in ()).throw(CaseConflict())
    )
    assert (
        client.post(
            f"/api/v1/cases/{uuid.uuid4()}/transitions",
            json={"expected_version": 1, "next_status": "DIAGNOSING"},
        ).status_code
        == 409
    )


def test_catalog_vocabulary_and_hash_are_fixed() -> None:
    assert "execute_sql" not in STABLE_READ_ONLY_TOOLS
    assert "get_target_report_run_history" not in STABLE_READ_ONLY_TOOLS
    assert health_scope_for("check_target_connector_health") is HealthScope.CONNECTOR
    assert canonical_hash({"b": 2, "a": 1}) == canonical_hash({"a": 1, "b": 2})
    session = cast(Any, MagicMock())
    session.scalar.return_value = None
    snapshot = record_mcp_catalog(
        session,
        uuid.uuid4(),
        uuid.uuid4(),
        [{"name": "execute_sql"}, {"name": "health_check"}],
    )
    assert snapshot.provider_type is ProviderType.MCP
    assert snapshot.catalog_hash == mcp_catalog_hash(["execute_sql", "health_check"])
