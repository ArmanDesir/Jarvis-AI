"""Module registration metadata; wiring remains in composition roots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class ModuleDescriptor:
    name: str
    version: str
    public_contracts: Sequence[str] = ()


class ModuleRegistration(Protocol):
    @property
    def descriptor(self) -> ModuleDescriptor: ...
