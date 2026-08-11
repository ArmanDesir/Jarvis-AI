import pytest
from rightjob.shared.pagination import PageRequest
from rightjob.shared.result import Err, Ok


def test_pagination_is_bounded() -> None:
    assert PageRequest(limit=100).limit == 100
    with pytest.raises(ValueError, match="between 1 and 100"):
        PageRequest(limit=101)


def test_result_variants_are_explicit() -> None:
    assert Ok("ready").value == "ready"
    assert Err("not_ready").error == "not_ready"
