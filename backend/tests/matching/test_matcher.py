import pytest

from app.matching.matcher import match_offer
from app.schemas.offers import MatchTarget, RawOffer


@pytest.fixture
def target() -> MatchTarget:
    return MatchTarget(
        brand="Apple",
        model_code="APPLE_IPHONE_17",
        model_name="iPhone 17",
        storage="256GB",
        region_version="中国大陆国行",
        condition="全新",
    )


@pytest.mark.parametrize(
    ("title", "reason"),
    [
        ("iPhone 17 手机壳 透明防摔", "accessory"),
        ("iPhone 17 Pro 256GB 国行全新", "model_mismatch"),
        ("iPhone 17 512GB 国行全新", "storage_mismatch"),
        ("iPhone 17 256GB 港版全新", "region_mismatch"),
        ("二手 iPhone 17 256GB 国行", "condition_mismatch"),
        ("iPhone 17 256GB 每月 199 元", "installment_only"),
        ("以旧换新至高抵扣后 3999 元", "trade_in_only"),
    ],
)
def test_rejects_non_comparable_offer(title: str, reason: str, target: MatchTarget) -> None:
    result = match_offer(
        RawOffer(title=title, platform="jd", listed_price_cents=None, sale_price_cents=499900),
        target,
    )

    assert result.accepted is False
    assert result.excluded_reason == reason


def test_accepts_exact_new_mainland_256gb_offer(target: MatchTarget) -> None:
    result = match_offer(
        RawOffer(
            title="Apple iPhone 17 256GB 黑色 全新国行",
            platform="jd",
            sale_price_cents=519900,
        ),
        target,
    )

    assert result.score >= 95
    assert result.accepted is True
    assert result.review_required is False
    assert "型号完全匹配" in result.reasons
