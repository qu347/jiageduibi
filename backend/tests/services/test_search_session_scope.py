import pytest
from pydantic import ValidationError

from app.schemas.search_sessions import CreateSearchSession


def test_scope_is_inferred_from_region() -> None:
    assert CreateSearchSession(variant_id=1).comparison_scope == "national"
    assert CreateSearchSession(variant_id=1, region_code="310100").comparison_scope == "regional"


@pytest.mark.parametrize(
    "payload, message",
    [
        (
            {"variant_id": 1, "comparison_scope": "national", "region_code": "310100"},
            "全国会话不能设置统一地区",
        ),
        (
            {"variant_id": 1, "comparison_scope": "regional", "region_code": None},
            "地区会话必须设置地区",
        ),
    ],
)
def test_scope_conflicts_are_rejected(payload: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        CreateSearchSession.model_validate(payload)
