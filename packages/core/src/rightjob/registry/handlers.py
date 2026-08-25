"""Explicit code-owned Capability handler resolution."""

from __future__ import annotations

from types import MappingProxyType
from typing import Generic, Mapping, TypeVar

from rightjob.contracts.capabilities import CapabilityDefinition

Handler = TypeVar("Handler")


class CapabilityHandlerNotFoundError(LookupError):
    """No approved handler is registered for the definition's stable key."""


class CapabilityHandlerResolver(Generic[Handler]):
    def __init__(self, handlers: Mapping[str, Handler]) -> None:
        self._handlers = MappingProxyType(dict(handlers))

    def resolve(self, definition: CapabilityDefinition) -> Handler:
        try:
            return self._handlers[definition.handler_key]
        except KeyError as error:
            raise CapabilityHandlerNotFoundError("capability handler is unavailable") from error
