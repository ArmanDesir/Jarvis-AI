"""Validated values shared by Identity/Tenancy entities."""

from __future__ import annotations

import re
import secrets
import time
from enum import Enum
from uuid import UUID

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class RecordStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class MembershipRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


def new_uuid7() -> UUID:
    """Create a UUIDv7 using the Python 3.11 standard library."""
    timestamp_ms = time.time_ns() // 1_000_000
    random_bits = secrets.randbits(74)
    value = (timestamp_ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= ((random_bits >> 62) & 0xFFF) << 64
    value |= 0b10 << 62
    value |= random_bits & ((1 << 62) - 1)
    return UUID(int=value)


def normalize_slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not 2 <= len(normalized) <= 63 or not _SLUG.fullmatch(normalized):
        raise ValueError("slug must contain 2-63 lowercase letters, numbers, or hyphens")
    return normalized


def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    local, separator, domain = normalized.partition("@")
    if not separator or not local or "." not in domain or len(normalized) > 320:
        raise ValueError("email must be a valid normalized address")
    return normalized


def normalize_provider(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized or len(normalized) > 100:
        raise ValueError("identity provider must contain 1-100 characters")
    return normalized
