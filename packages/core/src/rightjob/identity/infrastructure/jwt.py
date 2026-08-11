"""Strict provider-neutral JWT signature and registered-claim verification."""

from __future__ import annotations

from typing import Mapping, Sequence

import jwt

from rightjob.identity.application.authentication import (
    AuthenticationError,
    AuthenticationErrorCode,
)


class PyJwtVerifier:
    def __init__(
        self,
        verification_key: str,
        algorithms: Sequence[str],
        issuer: str | None = None,
        audience: str | None = None,
    ) -> None:
        if (
            not verification_key
            or not algorithms
            or "none" in {item.lower() for item in algorithms}
        ):
            raise ValueError("a verification key and explicit safe algorithms are required")
        self._key = verification_key
        self._algorithms = tuple(algorithms)
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> Mapping[str, object]:
        if token.count(".") != 2:
            raise AuthenticationError(AuthenticationErrorCode.MALFORMED)
        try:
            return jwt.decode(
                token,
                self._key,
                algorithms=self._algorithms,
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["exp", "sub"]},
            )
        except jwt.ExpiredSignatureError as error:
            raise AuthenticationError(AuthenticationErrorCode.EXPIRED) from error
        except jwt.InvalidSignatureError as error:
            raise AuthenticationError(AuthenticationErrorCode.INVALID) from error
        except jwt.DecodeError as error:
            raise AuthenticationError(AuthenticationErrorCode.MALFORMED) from error
        except jwt.InvalidTokenError as error:
            raise AuthenticationError(AuthenticationErrorCode.INVALID) from error
