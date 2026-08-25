"""Planning-owned proposal and deterministic-validation application seam."""

from rightjob.contracts.ai import AIProviderError, AIProviderFailureKind
from rightjob.contracts.planning import (
    ExecutionPlan,
    Planner,
    PlanningApplicationError,
    PlanningContext,
    PlanningFailure,
    PlanningRequest,
)
from rightjob.planner.validation import PlanValidationError, PlanValidator


class PlanningApplicationService:
    def __init__(self, planner: Planner, validator: PlanValidator) -> None:
        self._planner = planner
        self._validator = validator

    def plan(self, request: PlanningRequest, context: PlanningContext) -> ExecutionPlan:
        try:
            proposal = self._planner.plan(request, context)
            return self._validator.validate(request, context, proposal)
        except AIProviderError as error:
            failures = {
                AIProviderFailureKind.TRANSIENT: PlanningFailure.PROVIDER_TRANSIENT,
                AIProviderFailureKind.CONFIGURATION: PlanningFailure.PROVIDER_CONFIGURATION,
                AIProviderFailureKind.REJECTED_OUTPUT: PlanningFailure.PROVIDER_REJECTED_OUTPUT,
                AIProviderFailureKind.INVALID_OUTPUT: PlanningFailure.PROVIDER_INVALID_OUTPUT,
            }
            raise PlanningApplicationError(failures[error.kind]) from error
        except (PlanValidationError, LookupError, StopIteration, ValueError) as error:
            raise PlanningApplicationError(PlanningFailure.PROPOSAL_REJECTED) from error
