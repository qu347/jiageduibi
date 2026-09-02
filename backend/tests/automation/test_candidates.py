from app.automation.candidates import build_search_query, select_candidates
from app.automation.contracts import DiscoveredCandidate
from app.schemas.offers import MatchTarget


def target() -> MatchTarget:
    return MatchTarget(
        brand="Apple",
        model_code="APPLE_IPHONE_17",
        model_name="iPhone 17",
        storage="256GB",
        region_version="中国大陆国行",
        condition="全新",
    )


def candidate(
    sku: str,
    title: str,
    price: int,
) -> DiscoveredCandidate:
    return DiscoveredCandidate(
        platform_sku_id=sku,
        title=title,
        product_url=f"https://item.jd.com/{sku}.html",
        shop_name="京东自营",
        platform_shop_id="jd-self",
        shop_type="self_operated",
        initial_price_cents=price,
    )


def test_build_search_query_uses_human_model_fields() -> None:
    assert build_search_query(target()) == "Apple iPhone 17 256GB"


def test_selection_filters_wrong_models_deposits_and_duplicate_skus() -> None:
    selection = select_candidates(
        [
            candidate("next", "Apple iPhone 17 256GB 全新国行", 509900),
            candidate("cheap", "Apple iPhone 17 256GB 全新国行", 499900),
            candidate("cheap", "Apple iPhone 17 256GB 全新国行", 500000),
            candidate("deposit", "Apple iPhone 17 256GB 全新国行 定金", 10000),
            candidate("wrong", "Apple iPhone 17 Pro 256GB 全新国行", 489900),
        ],
        target(),
    )

    assert [item.platform_sku_id for item in selection.selected] == ["cheap", "next"]
    assert selection.exclusions == {
        "deposit_only": 1,
        "duplicate_sku": 1,
        "model_mismatch": 1,
    }
    assert selection.discovered_count == 5


def test_selection_uses_initial_price_only_for_candidate_cutoff() -> None:
    raw = [
        candidate(str(index), "Apple iPhone 17 256GB 全新国行", 500000 + index)
        for index in range(20, 0, -1)
    ]

    selected = select_candidates(raw, target(), limit=15).selected

    assert len(selected) == 15
    assert [item.initial_price_cents for item in selected] == sorted(
        item.initial_price_cents for item in selected
    )
    assert [item.platform_sku_id for item in selected[:2]] == ["1", "2"]
