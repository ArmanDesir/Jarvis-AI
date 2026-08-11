"""Opaque request and correlation identifiers."""

from __future__ import annotations

from typing import NewType
from uuid import uuid4

RequestId = NewType("RequestId", str)
CorrelationId = NewType("CorrelationId", str)


def new_request_id() -> RequestId:
    return RequestId(str(uuid4()))


def new_correlation_id() -> CorrelationId:
    return CorrelationId(str(uuid4()))
