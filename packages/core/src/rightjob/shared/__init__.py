"""Framework-neutral shared primitives."""

from rightjob.shared.clock import Clock, SystemClock
from rightjob.shared.errors import ErrorCode, Problem
from rightjob.shared.identifiers import CorrelationId, RequestId
from rightjob.shared.pagination import Page, PageRequest
from rightjob.shared.result import Err, Ok, Result

__all__ = [
    "Clock",
    "CorrelationId",
    "Err",
    "ErrorCode",
    "Ok",
    "Page",
    "PageRequest",
    "Problem",
    "RequestId",
    "Result",
    "SystemClock",
]
