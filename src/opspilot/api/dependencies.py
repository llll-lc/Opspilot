"""HTTP dependencies that turn a verified server principal into scoped L0 context."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from opspilot.security.auth import AuthenticationFailed, HmacBearerAuthenticator
from opspilot.support.services import AuthorizationContext, AuthorizationDenied, load_context


def get_session(request: Request) -> Generator[Session, None, None]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "database is not configured")
    session_factory: sessionmaker[Session] = factory
    with session_factory() as session:
        yield session


def get_authorization_context(
    request: Request,
    session: Session = Depends(get_session),  # noqa: B008
) -> AuthorizationContext:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authenticated principal is required")
    try:
        authenticator: HmacBearerAuthenticator = request.app.state.authenticator
    except AttributeError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "authentication is not configured"
        ) from exc
    try:
        principal = authenticator.verify(token)
    except AuthenticationFailed as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid bearer credential") from exc
    try:
        return load_context(session, principal.subject)
    except AuthorizationDenied as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "principal is not authorized") from exc
