"""Deterministic code-owned synthetic Policy evaluation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import UUID

from rightjob.contracts.capabilities import CapabilityCatalog, EffectClassification, SemanticVersion
from rightjob.contracts.departments import DepartmentCatalog
from rightjob.contracts.events import ActorType
from rightjob.contracts.policy import (
    PolicyAction,
    PolicyContext,
    PolicyDecision,
    PolicyEvaluation,
    PolicyEvaluationError,
    PolicyReasonCode,
    PolicyRuleReference,
    PolicySetReference,
    PolicySubject,
)

POLICY_VERSION = SemanticVersion.parse("1.0.0")
SYNTHETIC_POLICY_SET = PolicySetReference(
    UUID("03100000-0000-4000-8000-000000000001"),
    "synthetic.foundation.policy",
    POLICY_VERSION,
)
_VALIDATION_RULE = PolicyRuleReference(
    SYNTHETIC_POLICY_SET, "synthetic.validate_action", POLICY_VERSION
)
_SUBJECT_RULE = PolicyRuleReference(
    SYNTHETIC_POLICY_SET, "synthetic.authorize_subject", POLICY_VERSION
)
_EFFECT_RULE = PolicyRuleReference(
    SYNTHETIC_POLICY_SET, "synthetic.classify_effect", POLICY_VERSION
)
_VALIDITY = timedelta(minutes=5)


class SyntheticPolicyEvaluator:
    def __init__(
        self,
        capabilities: CapabilityCatalog,
        departments: DepartmentCatalog,
        id_factory: Callable[[], UUID],
        clock: Callable[[], datetime],
    ) -> None:
        self._capabilities = capabilities
        self._departments = departments
        self._id = id_factory
        self._clock = clock

    def evaluate(
        self,
        subject: PolicySubject,
        action: PolicyAction,
        context: PolicyContext,
    ) -> PolicyEvaluation:
        self._validate_provenance(subject, action, context)
        try:
            department = self._departments.get_enabled(
                action.department.department_key, action.department.semantic_version
            )
            capability = self._capabilities.get_enabled(
                action.capability.capability_key, action.capability.semantic_version
            )
        except LookupError as error:
            raise PolicyEvaluationError(
                "Policy action references an unavailable definition"
            ) from error
        if department.reference != action.department:
            raise PolicyEvaluationError("Policy Department identity does not match catalog")
        if capability.reference != action.capability:
            raise PolicyEvaluationError("Policy Capability identity does not match catalog")
        if action.capability not in department.capability_references:
            raise PolicyEvaluationError("Policy Capability does not belong to Department")
        if action.work_category not in department.work_categories:
            raise PolicyEvaluationError("Policy work category does not belong to Department")
        if action.effect_classification is not capability.effect_classification:
            raise PolicyEvaluationError("Policy effect classification does not match Capability")

        membership = subject.membership
        if (
            subject.actor.type is not ActorType.USER
            or membership is None
            or not membership.active
            or membership.user_id.hex != subject.actor.id.replace("-", "")
        ):
            return self._result(
                subject,
                action,
                context,
                PolicyDecision.DENY,
                PolicyReasonCode.SUBJECT_NOT_AUTHORIZED,
                (_VALIDATION_RULE, _SUBJECT_RULE),
            )
        if action.effect_classification in {
            EffectClassification.CONSEQUENTIAL,
            EffectClassification.EXTERNAL_EFFECT,
        }:
            return self._result(
                subject,
                action,
                context,
                PolicyDecision.REQUIRE_APPROVAL,
                PolicyReasonCode.APPROVAL_REQUIRED_FOR_EFFECT,
                (_VALIDATION_RULE, _SUBJECT_RULE, _EFFECT_RULE),
            )
        return self._result(
            subject,
            action,
            context,
            PolicyDecision.ALLOW,
            PolicyReasonCode.SYNTHETIC_NONCONSEQUENTIAL_ALLOWED,
            (_VALIDATION_RULE, _SUBJECT_RULE, _EFFECT_RULE),
        )

    @staticmethod
    def _validate_provenance(
        subject: PolicySubject, action: PolicyAction, context: PolicyContext
    ) -> None:
        if subject.workspace_id != context.workspace_id:
            raise PolicyEvaluationError("Policy subject and context Workspaces do not match")
        if action.plan_id != context.plan_id:
            raise PolicyEvaluationError("Policy action and context plan IDs do not match")

    def _result(
        self,
        subject: PolicySubject,
        action: PolicyAction,
        context: PolicyContext,
        decision: PolicyDecision,
        reason: PolicyReasonCode,
        rules: tuple[PolicyRuleReference, ...],
    ) -> PolicyEvaluation:
        evaluated_at = self._clock()
        return PolicyEvaluation(
            self._id(),
            subject,
            action,
            context,
            decision,
            (reason,),
            SYNTHETIC_POLICY_SET,
            rules,
            evaluated_at,
            evaluated_at + _VALIDITY,
        )
