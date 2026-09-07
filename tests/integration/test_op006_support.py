"""Actual PostgreSQL regressions for OP-006 isolation, concurrency and Gateway audit."""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from opspilot.db.enums import (
    HealthScope,
    ProviderType,
    SupportCaseStatus,
    ToolExecutionStatus,
    UserRole,
)
from opspilot.db.models import (
    AuditEvent,
    CaseMessage,
    Organization,
    ProviderCatalogSnapshot,
    SupportCase,
    TargetResource,
    TargetSystem,
    ToolDefinition,
    ToolExecution,
    ToolProviderBinding,
    User,
    UserResourceGrant,
    UserTargetScope,
)
from opspilot.db.session import create_database_engine
from opspilot.main import create_app
from opspilot.providers.runtime import ProviderFailure
from opspilot.security.auth import HmacBearerAuthenticator, issue_test_token
from opspilot.support.services import (
    AuthorizationContext,
    AuthorizationDenied,
    CaseConflict,
    create_case,
    load_context,
    transition_case,
)
from opspilot.tools.catalog import STABLE_READ_ONLY_TOOLS
from opspilot.tools.contracts import STABLE_TOOL_CONTRACTS
from opspilot.tools.gateway import GatewayRejected, ProviderUnavailable, ToolGateway
from opspilot.tools.seeding import REJECTION_TOOL_NAME, record_mcp_catalog, seed_stable_tools

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is required"),
]


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    assert DATABASE_URL is not None
    value = create_database_engine(DATABASE_URL)
    yield value
    value.dispose()


@dataclass(frozen=True)
class IdentityFixture:
    organization_a: uuid.UUID
    organization_b: uuid.UUID
    target_a: uuid.UUID
    target_a_other: uuid.UUID
    target_b: uuid.UUID
    alice: uuid.UUID
    alice_limited: uuid.UUID
    bob: uuid.UUID
    resources: dict[str, uuid.UUID]


def seed_identities(engine: Engine) -> IdentityFixture:
    fixture = IdentityFixture(
        organization_a=uuid.uuid4(),
        organization_b=uuid.uuid4(),
        target_a=uuid.uuid4(),
        target_a_other=uuid.uuid4(),
        target_b=uuid.uuid4(),
        alice=uuid.uuid4(),
        alice_limited=uuid.uuid4(),
        bob=uuid.uuid4(),
        resources={key: uuid.uuid4() for key in ("database", "dataset", "chart", "dashboard")},
    )
    nonce = uuid.uuid4().hex
    with Session(engine) as session:
        session.add_all(
            [
                Organization(id=fixture.organization_a, slug=f"op006-a-{nonce}", name="A"),
                Organization(id=fixture.organization_b, slug=f"op006-b-{nonce}", name="B"),
            ]
        )
        session.flush()
        session.add_all(
            [
                TargetSystem(
                    id=fixture.target_a,
                    organization_id=fixture.organization_a,
                    system_key=f"target-a-{nonce}",
                    system_type="SUPERSET",
                    display_name="A",
                ),
                TargetSystem(
                    id=fixture.target_a_other,
                    organization_id=fixture.organization_a,
                    system_key=f"target-a-other-{nonce}",
                    system_type="SUPERSET",
                    display_name="A other",
                ),
                TargetSystem(
                    id=fixture.target_b,
                    organization_id=fixture.organization_b,
                    system_key=f"target-b-{nonce}",
                    system_type="SUPERSET",
                    display_name="B",
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                User(
                    id=fixture.alice,
                    organization_id=fixture.organization_a,
                    subject=f"op006-alice-{nonce}",
                    display_name="Alice",
                    role=UserRole.SUPPORT,
                ),
                User(
                    id=fixture.alice_limited,
                    organization_id=fixture.organization_a,
                    subject=f"op006-alice-limited-{nonce}",
                    display_name="Alice limited",
                    role=UserRole.SUPPORT,
                ),
                User(
                    id=fixture.bob,
                    organization_id=fixture.organization_b,
                    subject=f"op006-bob-{nonce}",
                    display_name="Bob",
                    role=UserRole.SUPPORT,
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                UserTargetScope(
                    organization_id=fixture.organization_a,
                    user_id=fixture.alice,
                    target_system_id=fixture.target_a,
                ),
                UserTargetScope(
                    organization_id=fixture.organization_a,
                    user_id=fixture.alice_limited,
                    target_system_id=fixture.target_a,
                ),
                UserTargetScope(
                    organization_id=fixture.organization_b,
                    user_id=fixture.bob,
                    target_system_id=fixture.target_b,
                ),
            ]
        )
        for resource_type, resource_id in fixture.resources.items():
            session.add(
                TargetResource(
                    id=resource_id,
                    organization_id=fixture.organization_a,
                    target_system_id=fixture.target_a,
                    resource_type=resource_type.upper(),
                    external_id="7",
                    display_name=f"{resource_type}-7",
                )
            )
            session.add(
                UserResourceGrant(
                    organization_id=fixture.organization_a,
                    target_system_id=fixture.target_a,
                    user_id=fixture.alice,
                    resource_id=resource_id,
                )
            )
        session.commit()
    return fixture


def context_for(session: Session, user_id: uuid.UUID) -> AuthorizationContext:
    subject = session.scalar(sa.select(User.subject).where(User.id == user_id))
    assert subject is not None
    return load_context(session, subject)


def test_two_organization_users_and_existing_dedupe_are_reauthorized(engine: Engine) -> None:
    fx = seed_identities(engine)
    with Session(engine) as session:
        alice = context_for(session, fx.alice)
        bob = context_for(session, fx.bob)
        limited = context_for(session, fx.alice_limited)
        key = f"scope-{uuid.uuid4()}"
        created = create_case(
            session,
            alice,
            target_system_id=fx.target_a,
            resource_id=fx.resources["dashboard"],
            title="Scoped",
            description="Scoped",
            deduplication_key=key,
        )
        session.commit()
        assert created.organization_id == fx.organization_a
        assert (
            create_case(
                session,
                alice,
                target_system_id=fx.target_a,
                resource_id=fx.resources["dashboard"],
                title="Ignored duplicate",
                description="Ignored duplicate",
                deduplication_key=key,
            ).id
            == created.id
        )
        with pytest.raises(CaseConflict):
            create_case(
                session,
                alice,
                target_system_id=fx.target_a,
                resource_id=fx.resources["chart"],
                title="Same key, another resource",
                description="Conflict",
                deduplication_key=key,
            )
        with pytest.raises(AuthorizationDenied):
            create_case(
                session,
                limited,
                target_system_id=fx.target_a,
                resource_id=fx.resources["dashboard"],
                title="No grant",
                description="No grant",
                deduplication_key=key,
            )
        bob_case = create_case(
            session,
            bob,
            target_system_id=fx.target_b,
            title="Same key, separate organization",
            description="Isolated",
            deduplication_key=key,
        )
        assert bob_case.id != created.id
        message = CaseMessage(
            organization_id=fx.organization_a,
            support_case_id=created.id,
            author_user_id=fx.alice,
            body="Append-only timeline",
        )
        session.add(message)
        session.flush()
        with pytest.raises(sa.exc.DBAPIError):
            with session.begin_nested():
                session.execute(
                    sa.update(CaseMessage)
                    .where(CaseMessage.id == message.id)
                    .values(body="rewritten")
                )
        with pytest.raises(AuthorizationDenied):
            create_case(
                session,
                alice,
                target_system_id=fx.target_a_other,
                title="Cross target",
                description="Cross target",
                deduplication_key=key,
            )
        with pytest.raises(AuthorizationDenied):
            create_case(
                session,
                bob,
                target_system_id=fx.target_a,
                title="Cross organization",
                description="Cross organization",
                deduplication_key=key,
            )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(SupportCase)
                .where(
                    SupportCase.organization_id == fx.organization_a,
                    SupportCase.deduplication_key == key,
                )
            )
            == 1
        )


def test_case_creation_and_transition_have_real_postgres_conflict_control(engine: Engine) -> None:
    fx = seed_identities(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    dedupe = f"concurrent-{uuid.uuid4()}"
    barrier = threading.Barrier(2)

    def create_worker() -> uuid.UUID:
        with factory() as session:
            context = context_for(session, fx.alice)
            barrier.wait(timeout=10)
            case = create_case(
                session,
                context,
                target_system_id=fx.target_a,
                resource_id=fx.resources["database"],
                title="Concurrent",
                description="Concurrent",
                deduplication_key=dedupe,
            )
            session.commit()
            return case.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: create_worker(), range(2)))
    assert ids[0] == ids[1]
    with Session(engine) as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(SupportCase)
                .where(
                    SupportCase.organization_id == fx.organization_a,
                    SupportCase.deduplication_key == dedupe,
                )
            )
            == 1
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.entity_id == str(ids[0]),
                    AuditEvent.event_type == "SUPPORT_CASE_CREATED",
                )
            )
            == 1
        )

    transition_barrier = threading.Barrier(2)

    def transition_worker() -> str:
        with factory() as session:
            context = context_for(session, fx.alice)
            transition_barrier.wait(timeout=10)
            try:
                transition_case(
                    session,
                    context,
                    case_id=ids[0],
                    expected_version=1,
                    next_status=SupportCaseStatus.DIAGNOSING,
                )
                session.commit()
                return "SUCCEEDED"
            except CaseConflict:
                session.rollback()
                return "CONFLICT"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: transition_worker(), range(2)))
    assert sorted(outcomes) == ["CONFLICT", "SUCCEEDED"]
    with Session(engine) as session:
        transitioned = session.get(SupportCase, ids[0])
        assert transitioned is not None
        assert transitioned.status is SupportCaseStatus.DIAGNOSING
        assert transitioned.version == 2
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.entity_id == str(ids[0]),
                    AuditEvent.event_type == "SUPPORT_CASE_TRANSITIONED",
                )
            )
            == 1
        )


def test_signed_api_subject_loads_real_server_authorization_context(engine: Engine) -> None:
    fx = seed_identities(engine)
    secret = "op006-integration-signing-secret-32-bytes"
    with Session(engine) as session:
        subject = session.scalar(sa.select(User.subject).where(User.id == fx.alice))
    assert subject is not None
    app = create_app()
    app.state.session_factory = sessionmaker(engine, expire_on_commit=False)
    app.state.authenticator = HmacBearerAuthenticator(
        secret, issuer="op006-test", audience="opspilot-api"
    )
    token = issue_test_token(
        secret,
        subject=subject,
        token_id=str(uuid.uuid4()),
        issuer="op006-test",
        audience="opspilot-api",
        expires_at=4_102_444_800,
        not_before=1,
    )
    client = TestClient(app)
    payload = {
        "target_system_id": str(fx.target_a),
        "resource_id": str(fx.resources["dataset"]),
        "title": "Signed API",
        "description": "Verified subject",
        "deduplication_key": f"api-{uuid.uuid4()}",
    }
    assert (
        client.post(
            "/api/v1/cases", headers={"Authorization": f"Bearer {token}"}, json=payload
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/cases",
            headers={"X-OpsPilot-Actor-Id": str(fx.alice)},
            json={**payload, "deduplication_key": f"header-{uuid.uuid4()}"},
        ).status_code
        == 401
    )
    tampered = f"{token[:-1]}{'A' if not token.endswith('A') else 'B'}"
    assert (
        client.post(
            "/api/v1/cases",
            headers={"Authorization": f"Bearer {tampered}"},
            json={**payload, "deduplication_key": f"tamper-{uuid.uuid4()}"},
        ).status_code
        == 401
    )


class ControlledRest:
    def invoke(self, upstream_tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        if upstream_tool_name == "application_health":
            data: dict[str, object] = {"status": "HEALTHY", "detail": "fixture"}
        elif upstream_tool_name == "instance_summary":
            data = {"product": "Apache Superset", "version": "6.1.0"}
        else:
            resource = upstream_tool_name.removeprefix("list_").removeprefix("get_").upper()
            resource = {
                "DATABASES": "DATABASE",
                "DATASETS": "DATASET",
                "CHARTS": "CHART",
                "DASHBOARDS": "DASHBOARD",
            }.get(resource, resource)
            item = {"external_id": "7", "name": f"{resource}-7", "resource_type": resource}
            data = {"items": [item]} if upstream_tool_name.startswith("list_") else {"item": item}
        return {"health_scope": "APPLICATION", "data": data, "correlation_id": "rest-ok"}


class ControlledProbe:
    def invoke(self, upstream_tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        return {
            "health_scope": "RUNTIME_COMPONENT",
            "data": {"status": "HEALTHY", "component": arguments["component"]},
            "correlation_id": "probe-ok",
        }


class ControlledMcp:
    def __init__(self, catalog_hash: str, failure: str | None = None) -> None:
        self.expected_hash = catalog_hash
        self.failure = failure

    def catalog_hash(self) -> str:
        if self.failure == "CATALOG_READ_FAILED":
            raise ProviderFailure("CONNECTION_FAILED", "offline")
        return self.expected_hash

    def invoke(self, upstream_tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
        if self.failure:
            raise ProviderFailure(
                self.failure, "controlled failure", correlation_id=f"{self.failure}-correlation"
            )
        if upstream_tool_name == "health_check":
            return {
                "health_scope": "CONNECTOR",
                "data": {"status": "HEALTHY", "detail": "fixture"},
                "correlation_id": "mcp-ok",
            }
        if upstream_tool_name == "get_instance_info":
            return {
                "health_scope": "APPLICATION",
                "data": {"product": "Apache Superset", "version": "6.1.0"},
                "correlation_id": "mcp-ok",
            }
        resource = (
            upstream_tool_name.removeprefix("list_")
            .removeprefix("get_")
            .removesuffix("_info")
            .rstrip("s")
            .upper()
        )
        item = {"external_id": "7", "name": f"{resource}-7", "resource_type": resource}
        data: dict[str, object] = (
            {"items": [item]} if upstream_tool_name.startswith("list_") else {"item": item}
        )
        return {"health_scope": "APPLICATION", "data": data, "correlation_id": "mcp-ok"}


def seed_gateway(session: Session, fx: IdentityFixture) -> tuple[AuthorizationContext, str]:
    tools: list[dict[str, object]] = [
        {"name": binding[1]}
        for contract in STABLE_TOOL_CONTRACTS.values()
        for binding in contract.provider_bindings
        if binding[0] == "MCP"
    ]
    snapshot = record_mcp_catalog(session, fx.organization_a, fx.target_a, tools)
    seed_stable_tools(session, fx.organization_a, fx.target_a, reviewed_mcp_catalog=snapshot)
    session.commit()
    return context_for(session, fx.alice), snapshot.catalog_hash


def arguments_for(stable_name: str, fx: IdentityFixture) -> dict[str, object]:
    if stable_name == "get_target_runtime_health":
        return {"component": "worker"}
    for resource_type, resource_id in fx.resources.items():
        if stable_name == f"get_target_{resource_type}_info":
            return {"resource_id": str(resource_id)}
    return {}


def test_every_supported_stable_tool_calls_a_controlled_provider_and_is_audited(
    engine: Engine,
) -> None:
    fx = seed_identities(engine)
    with Session(engine) as session:
        context, catalog_hash = seed_gateway(session, fx)
        bindings = list(
            session.execute(
                sa.select(
                    ToolDefinition.stable_name,
                    ToolProviderBinding.provider_type,
                    ToolProviderBinding.upstream_tool_name,
                    ToolProviderBinding.health_scope,
                )
                .join(ToolProviderBinding)
                .where(ToolProviderBinding.target_system_id == fx.target_a)
            )
        )
        expected = {
            (
                stable_name,
                ProviderType(provider_name),
                upstream_name,
                contract.health_scope,
            )
            for stable_name, contract in STABLE_TOOL_CONTRACTS.items()
            for provider_name, upstream_name, _ in contract.provider_bindings
        } | {
            (
                REJECTION_TOOL_NAME,
                ProviderType.INTERNAL,
                "gateway_rejection",
                HealthScope.CONNECTOR,
            )
        }
        assert set(bindings) == expected
        seed_stable_tools(
            session,
            fx.organization_a,
            fx.target_a,
            reviewed_mcp_catalog=session.scalar(
                sa.select(ProviderCatalogSnapshot).where(
                    ProviderCatalogSnapshot.catalog_hash == catalog_hash,
                    ProviderCatalogSnapshot.target_system_id == fx.target_a,
                )
            ),
        )
        assert len(
            list(
                session.scalars(
                    sa.select(ToolProviderBinding).where(
                        ToolProviderBinding.target_system_id == fx.target_a
                    )
                )
            )
        ) == len(expected)
        gateway = ToolGateway(
            session,
            {
                ProviderType.MCP: ControlledMcp(catalog_hash),
                ProviderType.REST: ControlledRest(),
                ProviderType.PROBE: ControlledProbe(),
            },
            mcp_enabled=True,
        )
        execution_ids = []
        for stable_name in sorted(STABLE_READ_ONLY_TOOLS):
            result = gateway.invoke(
                context,
                stable_name,
                fx.target_a,
                arguments_for(stable_name, fx),
                idempotency_key=f"all-{stable_name}-{uuid.uuid4()}",
            )
            execution_ids.append(result.execution_id)
        session.commit()
        assert len(execution_ids) == len(STABLE_READ_ONLY_TOOLS) == 12
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(ToolExecution)
                .where(
                    ToolExecution.id.in_(execution_ids),
                    ToolExecution.status == ToolExecutionStatus.SUCCEEDED,
                )
            )
            == 12
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.tool_execution_id.in_(execution_ids))
            )
            == 12
        )


def test_gateway_rejections_failures_fallback_scope_limit_and_redaction_are_audited(
    engine: Engine,
) -> None:
    fx = seed_identities(engine)
    with Session(engine) as session:
        context, catalog_hash = seed_gateway(session, fx)
        start = session.scalar(sa.select(sa.func.count()).select_from(ToolExecution)) or 0
        result = ToolGateway(
            session,
            {ProviderType.REST: ControlledRest()},
            mcp_enabled=False,
        ).invoke(context, "get_target_instance_summary", fx.target_a, {})
        assert result.degraded_chain == ("MCP_DISABLED_BY_POLICY",)

        drift = ToolGateway(
            session,
            {
                ProviderType.MCP: ControlledMcp("0" * 64),
                ProviderType.REST: ControlledRest(),
            },
            mcp_enabled=True,
        ).invoke(context, "get_target_instance_summary", fx.target_a, {})
        assert drift.degraded_chain == ("MCP_CATALOG_DRIFT",)

        for failure in (
            "AUTHENTICATION_FAILED",
            "CONNECTION_FAILED",
            "TIMEOUT",
            "RESPONSE_SCHEMA_INVALID",
            "RESPONSE_TOO_LARGE",
        ):
            degraded = ToolGateway(
                session,
                {
                    ProviderType.MCP: ControlledMcp(catalog_hash, failure),
                    ProviderType.REST: ControlledRest(),
                },
                mcp_enabled=True,
            ).invoke(context, "get_target_instance_summary", fx.target_a, {})
            assert degraded.degraded_chain == (failure,)

        with pytest.raises(ProviderUnavailable):
            ToolGateway(session, {}, mcp_enabled=False).invoke(
                context, "get_target_application_health", fx.target_a, {}
            )

        rejection_scenarios: list[tuple[str, dict[str, object], uuid.UUID]] = [
            ("execute_sql", {"token": "do-not-store"}, fx.target_a),
            ("get_target_application_health", {"url": "http://attacker"}, fx.target_a),
            ("get_target_application_health", {}, fx.target_a_other),
        ]
        for stable, arguments, target in rejection_scenarios:
            with pytest.raises(GatewayRejected):
                ToolGateway(session, {}, mcp_enabled=False).invoke(
                    context, stable, target, arguments
                )

        class UnsafeRest:
            def __init__(self, response: dict[str, object]) -> None:
                self.response = response

            def invoke(
                self, upstream_tool_name: str, arguments: dict[str, object]
            ) -> dict[str, object]:
                return self.response

        wrong_resource: dict[str, object] = {
            "health_scope": "APPLICATION",
            "data": {"item": {"external_id": "999", "name": "other", "resource_type": "DATABASE"}},
        }
        with pytest.raises(ProviderUnavailable):
            ToolGateway(session, {ProviderType.REST: UnsafeRest(wrong_resource)}).invoke(
                context,
                "get_target_database_info",
                fx.target_a,
                {"resource_id": str(fx.resources["database"])},
            )
        wrong_scope: dict[str, object] = {
            "health_scope": "CONNECTOR",
            "data": {"status": "HEALTHY", "detail": "wrong"},
        }
        with pytest.raises(ProviderUnavailable):
            ToolGateway(session, {ProviderType.REST: UnsafeRest(wrong_scope)}).invoke(
                context, "get_target_application_health", fx.target_a, {}
            )
        invalid_schema: dict[str, object] = {
            "health_scope": "APPLICATION",
            "data": {"status": "HEALTHY", "extra": "forbidden"},
        }
        with pytest.raises(ProviderUnavailable):
            ToolGateway(session, {ProviderType.REST: UnsafeRest(invalid_schema)}).invoke(
                context, "get_target_application_health", fx.target_a, {}
            )
        oversized: dict[str, object] = {
            "health_scope": "APPLICATION",
            "data": {"status": "HEALTHY", "detail": "x" * 40_000},
        }
        with pytest.raises(ProviderUnavailable):
            ToolGateway(session, {ProviderType.REST: UnsafeRest(oversized)}).invoke(
                context, "get_target_application_health", fx.target_a, {}
            )
        session.commit()

        attempts = list(
            session.scalars(
                sa.select(ToolExecution).order_by(ToolExecution.started_at, ToolExecution.id)
            )
        )[start:]
        assert len(attempts) == 23
        assert all(attempt.status in ToolExecutionStatus for attempt in attempts)
        assert any(attempt.error_type == "MCP_DISABLED_BY_POLICY" for attempt in attempts)
        assert any(attempt.error_type == "MCP_CATALOG_DRIFT" for attempt in attempts)
        assert any(attempt.error_type == "RESOURCE_SCOPE_MISMATCH" for attempt in attempts)
        assert any(attempt.error_type == "HEALTH_SCOPE_MISMATCH" for attempt in attempts)
        assert any(attempt.error_type == "RESPONSE_TOO_LARGE" for attempt in attempts)
        assert any(attempt.error_type == "PROVIDER_NOT_CONFIGURED" for attempt in attempts)
        assert any(
            attempt.status is ToolExecutionStatus.SUCCEEDED
            and attempt.fallback_reason == "AUTHENTICATION_FAILED"
            for attempt in attempts
        )
        assert all(attempt.request_correlation_id for attempt in attempts)
        unknown = next(
            attempt for attempt in attempts if attempt.error_type == "UNKNOWN_STABLE_TOOL"
        )
        assert unknown.request_summary["arguments"]["token"] == "[REDACTED]"
        attempt_ids = [attempt.id for attempt in attempts]
        events = list(
            session.scalars(
                sa.select(AuditEvent).where(AuditEvent.tool_execution_id.in_(attempt_ids))
            )
        )
        assert len(events) == len(attempts)
        assert any(event.correlation_id == "CONNECTION_FAILED-correlation" for event in events)
