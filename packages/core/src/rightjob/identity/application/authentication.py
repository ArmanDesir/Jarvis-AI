"""Provider-neutral authentication contracts and JWT claim mapping."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol


class AuthenticationErrorCode(str, Enum):
    MISSING = "missing_token"
    MALFORMED = "malformed_token"
    INVALID = "invalid_token"
    EXPIRED = "expired_token"
    UNAVAILABLE = "authentication_unavailable"


class AuthenticationError(Exception):
    def __init__(self, code: AuthenticationErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True)
class ExternalIdentity:
    provider: str
    subject: str


class JwtVerifier(Protocol):
    def verify(self, token: str) -> Mapping[str, object]: ...


class AuthenticationProvider(Protocol):
    def authenticate(self, token: str) -> ExternalIdentity: ...


class JwtAuthenticationProvider:
    """Map verified standard JWT claims to a provider-neutral external identity."""

    def __init__(self, provider: str, verifier: JwtVerifier) -> None:
        self._provider = provider.strip().lower()
        self._verifier = verifier
        if not self._provider:
            raise ValueError("authentication provider is required")

    def authenticate(self, token: str) -> ExternalIdentity:
        claims = self._verifier.verify(token)
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise AuthenticationError(AuthenticationErrorCode.INVALID)
        return ExternalIdentity(provider=self._provider, subject=subject)
