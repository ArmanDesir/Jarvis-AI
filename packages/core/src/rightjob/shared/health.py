"""Health contracts shared by API and worker composition roots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DependencyState = Literal["ready", "unavailable", "disabled"]


@dataclass(frozen=True)
class DependencyHealth:
    name: str
    required: bool
    state: DependencyState
    detail: str
