"""L0 authorization and case-state services; no Agent or Provider choices live here."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from opspilot.db.enums import AuditActorType, SupportCaseStatus, UserRole
from opspilot.db.models import (
    AuditEvent,
    SupportCase,
    TargetResource,
    User,
    UserResourceGrant,
    UserTargetScope,
)


class AuthorizationDenied(PermissionError):
    """The server-owned identity lacks the requested organization, target, or resource scope."""


class CaseConflict(RuntimeError):
    """A state transition used a stale optimistic version."""


class InvalidCaseTransition(ValueError):
    """The deterministic state machine does not allow this transition."""


@dataclass(frozen=True)
class AuthorizationContext:
    organization_id: uuid.UUID
    actor_user_id: uuid.UUID
    role: UserRole
    target_system_ids: frozenset[uuid.UUID]
    resource_ids: frozenset[uuid.UUID]


def _hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def load_context(session: Session, subject: str) -> AuthorizationContext:
    user = session.scalar(sa.select(User).where(User.subject == subject, User.active.is_(True)))
    if user is None:
        raise AuthorizationDenied("active server-authenticated user is required")
    targets = frozenset(
        session.scalars(
            sa.select(UserTargetScope.target_system_id).where(UserTargetScope.user_id == user.id)
        )
    )
    resources = frozenset(
        session.scalars(
            sa.select(UserResourceGrant.resource_id).where(UserResourceGrant.user_id == user.id)
        )
    )
    return AuthorizationContext(user.organization_id, user.id, user.role, targets, resources)


def require_scope(
    context: AuthorizationContext, target_system_id: uuid.UUID, resource_id: uuid.UUID | None = None
) -> None:
    if target_system_id not in context.target_system_ids:
        raise AuthorizationDenied("target system is outside the server-authorized scope")
    if resource_id is not None and resource_id not in context.resource_ids:
        raise AuthorizationDenied("resource is outside the server-authorized scope")


def _audit(
    session: Session,
    context: AuthorizationContext,
    target_system_id: uuid.UUID,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, object],
) -> None:
    session.add(
        AuditEvent(
            organization_id=context.organization_id,
            target_system_id=target_system_id,
            actor_type=AuditActorType.USER,
            actor_ref=str(context.actor_user_id),
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_summary=payload,
            payload_hash=_hash(payload),
            occurred_at=datetime.now(UTC),
        )
    )


def create_case(
    session: Session,
    context: AuthorizationContext,
    *,
    target_system_id: uuid.UUID,
    title: str,
    description: str,
    deduplication_key: str,
    resource_id: uuid.UUID | None = None,
    symptom_code: str | None = None,
) -> SupportCase:
    require_scope(context, target_system_id, resource_id)
    existing = session.scalar(
        sa.select(SupportCase).where(
            SupportCase.organization_id == context.organization_id,
            SupportCase.deduplication_key == deduplication_key,
        )
    )
    if existing is not None:
        require_scope(context, existing.target_system_id, existing.resource_id)
        if existing.target_system_id != target_system_id or existing.resource_id != resource_id:
            raise CaseConflict(
                "deduplication key is already bound to another target or resource"
            ) from None
        return existing
    if resource_id is not None:
        resource = session.scalar(
            sa.select(TargetResource).where(
                TargetResource.id == resource_id,
                TargetResource.organization_id == context.organization_id,
                TargetResource.target_system_id == target_system_id,
            )
        )
        if resource is None:
            raise AuthorizationDenied("resource is not in the requested target scope")
    case = SupportCase(
        organization_id=context.organization_id,
        target_system_id=target_system_id,
        reporter_user_id=context.actor_user_id,
        resource_id=resource_id,
        title=title,
        description=description,
        symptom_code=symptom_code,
        status=SupportCaseStatus.OPEN,
        deduplication_key=deduplication_key,
        version=1,
    )
    try:
        with session.begin_nested():
            session.add(case)
            session.flush()
    except IntegrityError:
        existing = session.scalar(
            sa.select(SupportCase).where(
                SupportCase.organization_id == context.organization_id,
                SupportCase.deduplication_key == deduplication_key,
            )
        )
        if existing is None:
            raise
        require_scope(context, existing.target_system_id, existing.resource_id)
        if existing.target_system_id != target_system_id or existing.resource_id != resource_id:
            raise CaseConflict(
                "deduplication key is already bound to another target or resource"
            ) from None
        return existing
    _audit(
        session,
        context,
        target_system_id,
        "SUPPORT_CASE_CREATED",
        "SupportCase",
        str(case.id),
        {"status": case.status},
    )
    return case


_TRANSITIONS: dict[SupportCaseStatus, frozenset[SupportCaseStatus]] = {
    SupportCaseStatus.OPEN: frozenset({SupportCaseStatus.DIAGNOSING, SupportCaseStatus.ESCALATED}),
    SupportCaseStatus.DIAGNOSING: frozenset(
        {SupportCaseStatus.WAITING_USER, SupportCaseStatus.ESCALATED}
    ),
    SupportCaseStatus.WAITING_USER: frozenset(
        {SupportCaseStatus.DIAGNOSING, SupportCaseStatus.ESCALATED}
    ),
    SupportCaseStatus.ESCALATED: frozenset(),
}


def transition_case(
    session: Session,
    context: AuthorizationContext,
    *,
    case_id: uuid.UUID,
    expected_version: int,
    next_status: SupportCaseStatus,
) -> SupportCase:
    case = session.scalar(
        sa.select(SupportCase).where(
            SupportCase.id == case_id, SupportCase.organization_id == context.organization_id
        )
    )
    if case is None:
        raise AuthorizationDenied("support case is outside the server-authorized organization")
    require_scope(context, case.target_system_id, case.resource_id)
    if context.role not in {UserRole.SUPPORT, UserRole.ADMIN}:
        raise AuthorizationDenied("only support roles may transition a support case")
    if case.version != expected_version:
        raise CaseConflict("support case version is stale")
    if next_status not in _TRANSITIONS[case.status]:
        raise InvalidCaseTransition(f"{case.status} cannot transition to {next_status}")
    previous = case.status
    updated = session.scalar(
        sa.update(SupportCase)
        .where(
            SupportCase.id == case.id,
            SupportCase.organization_id == context.organization_id,
            SupportCase.version == expected_version,
            SupportCase.status == previous,
        )
        .values(status=next_status, version=expected_version + 1)
        .returning(SupportCase)
    )
    if updated is None:
        raise CaseConflict("support case changed concurrently")
    _audit(
        session,
        context,
        updated.target_system_id,
        "SUPPORT_CASE_TRANSITIONED",
        "SupportCase",
        str(updated.id),
        {"from": previous, "to": next_status, "version": updated.version},
    )
    return updated
