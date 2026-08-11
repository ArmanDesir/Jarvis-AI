"""Cursor pagination primitives without storage assumptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class PageRequest:
    cursor: str | None = None
    limit: int = 50

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 100:
            raise ValueError("limit must be between 1 and 100")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: Sequence[T]
    next_cursor: str | None = None
