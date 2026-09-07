from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from opspilot.db.enums import SupportCaseStatus, UserRole
from opspilot.support.services import (
    AuthorizationContext,
    AuthorizationDenied,
    CaseConflict,
    InvalidCaseTransition,
    create_case,
    load_context,
    require_scope,
    transition_case,
)
from opspilot.tools.contracts import STABLE_TOOL_CONTRACTS, validate_input, validate_output


def test_context_and_scope_reject_ungranted_values() -> None:
    session = cast(Any, MagicMock())
    user = SimpleNamespace(id=uuid.uuid4(), organization_id=uuid.uuid4(), role=UserRole.REPORTER)
    target, resource = uuid.uuid4(), uuid.uuid4()
    session.scalar.return_value = user
    session.scalars.side_effect = [[target], [resource]]
    loaded = load_context(session, "verified-subject")
    assert loaded.target_system_ids == frozenset({target})
    assert loaded.resource_ids == frozenset({resource})
    require_scope(loaded, target, resource)
    with pytest.raises(AuthorizationDenied):
        require_scope(loaded, uuid.uuid4())
    with pytest.raises(AuthorizationDenied):
        require_scope(loaded, target, uuid.uuid4())
    session.scalar.return_value = None
    with pytest.raises(AuthorizationDenied):
        load_context(session, "verified-subject")


def test_case_creation_is_idempotent_and_reauthorizes_existing_scope() -> None:
    target, resource = uuid.uuid4(), uuid.uuid4()
    ctx = AuthorizationContext(
        uuid.uuid4(), uuid.uuid4(), UserRole.SUPPORT, frozenset({target}), frozenset({resource})
    )
    session = cast(Any, MagicMock())
    session.scalar.side_effect = [None, SimpleNamespace(id=resource)]
    created = create_case(
        session,
        ctx,
        target_system_id=target,
        resource_id=resource,
        title="t",
        description="d",
        deduplication_key="dedupe",
    )
    assert created.status is SupportCaseStatus.OPEN
    existing = cast(
        Any, SimpleNamespace(id=uuid.uuid4(), target_system_id=target, resource_id=resource)
    )
    session.scalar.side_effect = [existing]
    assert (
        create_case(
            session,
            ctx,
            target_system_id=target,
            resource_id=resource,
            title="t",
            description="d",
            deduplication_key="dedupe",
        )
        is existing
    )
    session.scalar.side_effect = [existing]
    with pytest.raises(AuthorizationDenied):
        create_case(
            session,
            AuthorizationContext(
                ctx.organization_id,
                ctx.actor_user_id,
                ctx.role,
                frozenset({target}),
                frozenset(),
            ),
            target_system_id=target,
            title="t",
            description="d",
            deduplication_key="dedupe",
        )
    session.scalar.side_effect = [existing]
    with pytest.raises(CaseConflict):
        create_case(
            session,
            ctx,
            target_system_id=target,
            title="t",
            description="d",
            deduplication_key="dedupe",
        )


def test_case_transitions_require_role_version_and_allowed_edge() -> None:
    target, resource = uuid.uuid4(), uuid.uuid4()
    ctx = AuthorizationContext(
        uuid.uuid4(), uuid.uuid4(), UserRole.SUPPORT, frozenset({target}), frozenset({resource})
    )
    case = SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=ctx.organization_id,
        target_system_id=target,
        resource_id=resource,
        status=SupportCaseStatus.OPEN,
        version=1,
    )
    moved = SimpleNamespace(
        **{**case.__dict__, "status": SupportCaseStatus.DIAGNOSING, "version": 2}
    )
    session = cast(Any, MagicMock())
    session.scalar.side_effect = [case, moved]
    result = transition_case(
        session,
        ctx,
        case_id=case.id,
        expected_version=1,
        next_status=SupportCaseStatus.DIAGNOSING,
    )
    assert result.version == 2

    stale_session = cast(Any, MagicMock())
    stale_session.scalar.return_value = moved
    with pytest.raises(CaseConflict):
        transition_case(
            stale_session,
            ctx,
            case_id=case.id,
            expected_version=1,
            next_status=SupportCaseStatus.ESCALATED,
        )
    invalid_session = cast(Any, MagicMock())
    invalid_session.scalar.return_value = moved
    with pytest.raises(InvalidCaseTransition):
        transition_case(
            invalid_session,
            ctx,
            case_id=case.id,
            expected_version=2,
            next_status=SupportCaseStatus.OPEN,
        )
    reporter = AuthorizationContext(
        ctx.organization_id,
        ctx.actor_user_id,
        UserRole.REPORTER,
        ctx.target_system_ids,
        ctx.resource_ids,
    )
    role_session = cast(Any, MagicMock())
    role_session.scalar.return_value = moved
    with pytest.raises(AuthorizationDenied):
        transition_case(
            role_session,
            reporter,
            case_id=case.id,
            expected_version=2,
            next_status=SupportCaseStatus.ESCALATED,
        )


def test_stable_contracts_reject_extra_input_and_wrong_output_scope_shape() -> None:
    assert set(STABLE_TOOL_CONTRACTS) == {
        "check_target_connector_health",
        "get_target_application_health",
        "get_target_runtime_health",
        "get_target_instance_summary",
        "list_target_databases",
        "get_target_database_info",
        "list_target_datasets",
        "get_target_dataset_info",
        "list_target_charts",
        "get_target_chart_info",
        "list_target_dashboards",
        "get_target_dashboard_info",
    }
    with pytest.raises(ValueError):
        validate_input("get_target_application_health", {"url": "http://attacker"})
    with pytest.raises(ValueError):
        validate_output(
            "get_target_application_health",
            {"health_scope": "APPLICATION", "data": {"status": "HEALTHY", "password": "x"}},
        )
