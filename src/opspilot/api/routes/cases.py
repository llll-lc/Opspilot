"""Minimal deterministic case endpoints; no Agent behavior is exposed here."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from opspilot.api.dependencies import get_authorization_context, get_session
from opspilot.db.enums import SupportCaseStatus
from opspilot.support.services import (
    AuthorizationContext,
    AuthorizationDenied,
    CaseConflict,
    InvalidCaseTransition,
    create_case,
    transition_case,
)

router = APIRouter(prefix="/cases")


class CaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_system_id: uuid.UUID
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=10_000)
    deduplication_key: str = Field(min_length=1, max_length=200)
    resource_id: uuid.UUID | None = None
    symptom_code: str | None = Field(default=None, max_length=100)


class CaseTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_version: int = Field(ge=1)
    next_status: SupportCaseStatus


class CaseResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    target_system_id: uuid.UUID
    status: SupportCaseStatus
    version: int


def _response(case: object) -> CaseResponse:
    return CaseResponse.model_validate(case, from_attributes=True)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CaseResponse)
def create_support_case(
    payload: CaseCreateRequest,
    session: Session = Depends(get_session),  # noqa: B008
    context: AuthorizationContext = Depends(get_authorization_context),  # noqa: B008
) -> CaseResponse:
    try:
        case = create_case(session, context, **payload.model_dump())
        session.commit()
    except AuthorizationDenied as exc:
        session.rollback()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "requested scope is not authorized") from exc
    except CaseConflict as exc:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "support case deduplication conflict"
        ) from exc
    return _response(case)


@router.post("/{case_id}/transitions", response_model=CaseResponse)
def transition_support_case(
    case_id: uuid.UUID,
    payload: CaseTransitionRequest,
    session: Session = Depends(get_session),  # noqa: B008
    context: AuthorizationContext = Depends(get_authorization_context),  # noqa: B008
) -> CaseResponse:
    try:
        case = transition_case(session, context, case_id=case_id, **payload.model_dump())
        session.commit()
    except AuthorizationDenied as exc:
        session.rollback()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "requested scope is not authorized") from exc
    except CaseConflict as exc:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "support case version conflict") from exc
    except InvalidCaseTransition as exc:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid support case transition") from exc
    return _response(case)
