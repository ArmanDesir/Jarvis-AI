"""Structured, transport-neutral error model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class ErrorCode(str, Enum):
    CONFIGURATION_INVALID = "configuration_invalid"
    NOT_READY = "not_ready"
    INTERNAL = "internal"


@dataclass(frozen=True)
class Problem:
    code: ErrorCode
    title: str
    detail: str
    metadata: Mapping[str, str] = field(default_factory=dict)
