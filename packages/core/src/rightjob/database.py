"""Database composition root for module-owned SQLAlchemy mappings."""

from sqlalchemy import MetaData

from rightjob.shared.sqlalchemy import Base


def register_sqlalchemy_mappings() -> MetaData:
    from rightjob.audit.infrastructure import models as audit_models  # noqa: F401
    from rightjob.identity.infrastructure import models as identity_models  # noqa: F401
    from rightjob.orchestration.infrastructure import models as orchestration_models  # noqa: F401
    from rightjob.policy.infrastructure import models as policy_models  # noqa: F401

    return Base.metadata
