import pytest

from app.services.region_identity import build_region_key, normalize_region_name


@pytest.mark.parametrize(
    ("region_code", "region_name", "expected"),
    [
        ("310100", "上海市", "code:310100"),
        (None, "  上 海市  ", "name:上 海市"),
        (None, "全国", "national"),
        (None, None, "unknown"),
    ],
)
def test_build_region_key_is_deterministic(
    region_code: str | None,
    region_name: str | None,
    expected: str,
) -> None:
    assert build_region_key(region_code, region_name) == expected


def test_normalize_region_name_collapses_whitespace_and_casefolds() -> None:
    assert normalize_region_name("  New   REGION  ") == "new region"


def test_region_code_conflicts_with_national_name() -> None:
    with pytest.raises(ValueError, match="地区代码不能与全国适用同时出现"):
        build_region_key("310100", "全国")
