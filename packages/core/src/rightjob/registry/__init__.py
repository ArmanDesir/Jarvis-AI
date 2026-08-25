"""Department Registry boundary: manifests and Capability metadata only."""

from rightjob.registry.catalog import (
    BUILT_IN_CAPABILITIES,
    BuiltInCapabilityRegistry,
    CapabilityDisabledError,
    CapabilityNotFoundError,
)
from rightjob.registry.departments import (
    BUILT_IN_DEPARTMENTS,
    BuiltInDepartmentRegistry,
    DepartmentDisabledError,
    DepartmentNotFoundError,
)
from rightjob.registry.handlers import (
    CapabilityHandlerNotFoundError,
    CapabilityHandlerResolver,
)
from rightjob.registry.routing import (
    DepartmentRouteAmbiguousError,
    DepartmentRouteNotFoundError,
    DepartmentRouter,
)

__all__ = [
    "BUILT_IN_CAPABILITIES",
    "BUILT_IN_DEPARTMENTS",
    "BuiltInCapabilityRegistry",
    "CapabilityDisabledError",
    "CapabilityHandlerNotFoundError",
    "CapabilityHandlerResolver",
    "CapabilityNotFoundError",
    "BuiltInDepartmentRegistry",
    "DepartmentDisabledError",
    "DepartmentNotFoundError",
    "DepartmentRouteAmbiguousError",
    "DepartmentRouteNotFoundError",
    "DepartmentRouter",
]
