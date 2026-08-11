from datetime import datetime, timedelta, timezone

import jwt
import pytest
from rightjob.identity.application.authentication import (
    AuthenticationError,
    AuthenticationErrorCode,
    JwtAuthenticationProvider,
)
from rightjob.identity.infrastructure.jwt import PyJwtVerifier

KEY = "phase22-test-signing-key-at-least-32-bytes"


def _token(
    subject: str = "subject-1",
    expires_in: int = 60,
    key: str = KEY,
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    claims = {"sub": subject, "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in)}
    if issuer:
        claims["iss"] = issuer
    if audience:
        claims["aud"] = audience
    return jwt.encode(
        claims,
        key,
        algorithm="HS256",
    )


def _provider() -> JwtAuthenticationProvider:
    return JwtAuthenticationProvider("test-oidc", PyJwtVerifier(KEY, ("HS256",)))


def test_valid_token_resolves_external_identity() -> None:
    identity = _provider().authenticate(_token())
    assert identity.provider == "test-oidc"
    assert identity.subject == "subject-1"


@pytest.mark.parametrize(
    ("token", "code"),
    [
        (_token(key="wrong-signing-key-at-least-32-bytes"), AuthenticationErrorCode.INVALID),
        (_token(expires_in=-1), AuthenticationErrorCode.EXPIRED),
        ("not-a-jwt", AuthenticationErrorCode.MALFORMED),
    ],
)
def test_invalid_tokens_fail_closed(token: str, code: AuthenticationErrorCode) -> None:
    with pytest.raises(AuthenticationError) as caught:
        _provider().authenticate(token)
    assert caught.value.code is code


@pytest.mark.parametrize(
    "token",
    [
        _token(issuer="wrong", audience="rightjob-api"),
        _token(issuer="rightjob", audience="wrong"),
    ],
)
def test_wrong_issuer_or_audience_fails_closed(token: str) -> None:
    provider = JwtAuthenticationProvider(
        "test-oidc",
        PyJwtVerifier(KEY, ("HS256",), issuer="rightjob", audience="rightjob-api"),
    )
    with pytest.raises(AuthenticationError) as caught:
        provider.authenticate(token)
    assert caught.value.code is AuthenticationErrorCode.INVALID
