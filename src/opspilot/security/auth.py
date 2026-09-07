"""Small HS256 bearer verifier for the local/API authentication boundary."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


class AuthenticationFailed(PermissionError):
    """A bearer credential failed deterministic verification."""


@dataclass(frozen=True)
class VerifiedPrincipal:
    subject: str
    token_id: str


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, UnicodeError) as exc:
        raise AuthenticationFailed("malformed bearer credential") from exc


class HmacBearerAuthenticator:
    """Verify issuer, audience, lifetime and signature before exposing a subject."""

    def __init__(self, secret: str, *, issuer: str, audience: str) -> None:
        if len(secret.encode()) < 32:
            raise ValueError("authentication secret must contain at least 32 bytes")
        self._secret = secret.encode()
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str, *, now: int | None = None) -> VerifiedPrincipal:
        try:
            encoded_header, encoded_payload, encoded_signature = token.split(".")
            signed = f"{encoded_header}.{encoded_payload}".encode()
            expected = hmac.new(self._secret, signed, hashlib.sha256).digest()
            if not hmac.compare_digest(_decode(encoded_signature), expected):
                raise AuthenticationFailed("invalid bearer signature")
            header = json.loads(_decode(encoded_header))
            payload = json.loads(_decode(encoded_payload))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AuthenticationFailed("malformed bearer credential") from exc
        if not isinstance(header, dict) or header != {"alg": "HS256", "typ": "JWT"}:
            raise AuthenticationFailed("unsupported bearer algorithm")
        if not isinstance(payload, dict):
            raise AuthenticationFailed("malformed bearer credential")
        current = int(time.time()) if now is None else now
        if payload.get("iss") != self._issuer or payload.get("aud") != self._audience:
            raise AuthenticationFailed("invalid bearer claims")
        if type(payload.get("exp")) is not int or payload["exp"] <= current:
            raise AuthenticationFailed("expired bearer credential")
        if type(payload.get("nbf")) is not int or payload["nbf"] > current:
            raise AuthenticationFailed("bearer credential is not active")
        subject, token_id = payload.get("sub"), payload.get("jti")
        if (
            not isinstance(subject, str)
            or not subject
            or not isinstance(token_id, str)
            or not token_id
        ):
            raise AuthenticationFailed("bearer subject is missing")
        return VerifiedPrincipal(subject=subject, token_id=token_id)


def issue_test_token(
    secret: str,
    *,
    subject: str,
    token_id: str,
    issuer: str,
    audience: str,
    expires_at: int,
    not_before: int,
) -> str:
    """Create deterministic credentials for tests only; no production route exposes minting."""
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(
        json.dumps(
            {
                "sub": subject,
                "jti": token_id,
                "iss": issuer,
                "aud": audience,
                "exp": expires_at,
                "nbf": not_before,
            },
            separators=(",", ":"),
        ).encode()
    )
    signed = f"{header}.{payload}".encode()
    return (
        f"{header}.{payload}.{_encode(hmac.new(secret.encode(), signed, hashlib.sha256).digest())}"
    )
