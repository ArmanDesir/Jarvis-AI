from uuid import UUID

import pytest
from rightjob.identity.domain.entities import User, Workspace
from rightjob.identity.domain.values import new_uuid7, normalize_email, normalize_slug


def test_uuid7_and_normalized_identity_values() -> None:
    identifier = new_uuid7()
    assert isinstance(identifier, UUID)
    assert identifier.version == 7
    assert normalize_slug(" Rightjob Solutions ") == "rightjob-solutions"
    assert normalize_email(" OWNER@Example.COM ") == "owner@example.com"


def test_entities_normalize_at_the_domain_boundary() -> None:
    workspace = Workspace(name="Rightjob", slug="Rightjob Solutions")
    user = User(
        external_identity_provider="OIDC",
        external_subject="subject-1",
        email="OWNER@EXAMPLE.COM",
        display_name="Owner",
    )
    assert workspace.slug == "rightjob-solutions"
    assert user.external_identity_provider == "oidc"
    assert user.email == "owner@example.com"


@pytest.mark.parametrize("value", ["", "-", "a"])
def test_invalid_slug_fails(value: str) -> None:
    with pytest.raises(ValueError, match="slug"):
        normalize_slug(value)
