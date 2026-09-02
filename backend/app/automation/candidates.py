from collections import Counter
from dataclasses import dataclass

from app.automation.contracts import DiscoveredCandidate, ShopType
from app.matching.matcher import match_offer
from app.schemas.offers import MatchTarget, RawOffer


@dataclass(frozen=True, slots=True)
class SelectedCandidate:
    platform_sku_id: str
    title: str
    product_url: str
    shop_name: str
    platform_shop_id: str | None
    shop_type: ShopType
    initial_price_cents: int
    match_score: int


@dataclass(frozen=True, slots=True)
class CandidateSelection:
    selected: tuple[SelectedCandidate, ...]
    exclusions: dict[str, int]
    discovered_count: int


def build_search_query(target: MatchTarget) -> str:
    fields = (target.brand, target.model_name, target.storage)
    return " ".join(" ".join(fields).split())[:200]


def select_candidates(
    raw_candidates: list[DiscoveredCandidate],
    target: MatchTarget,
    limit: int = 15,
) -> CandidateSelection:
    if not 1 <= limit <= 50:
        raise ValueError("候选保留数量必须在 1 到 50 之间")

    exclusions: Counter[str] = Counter()
    matched: list[SelectedCandidate] = []
    for candidate in raw_candidates:
        match = match_offer(
            RawOffer(
                title=candidate.title,
                platform="jd",
                sale_price_cents=candidate.initial_price_cents,
                platform_product_id=candidate.platform_sku_id,
                platform_sku_id=candidate.platform_sku_id,
                platform_shop_id=candidate.platform_shop_id,
                shop_name=candidate.shop_name,
                shop_type=candidate.shop_type,
                product_url=candidate.product_url,
            ),
            target,
        )
        if not match.accepted:
            exclusions[match.excluded_reason or "low_confidence"] += 1
            continue
        matched.append(
            SelectedCandidate(
                platform_sku_id=candidate.platform_sku_id,
                title=candidate.title,
                product_url=candidate.product_url,
                shop_name=candidate.shop_name,
                platform_shop_id=candidate.platform_shop_id,
                shop_type=candidate.shop_type,
                initial_price_cents=candidate.initial_price_cents,
                match_score=match.score,
            )
        )

    matched.sort(key=lambda item: (item.initial_price_cents, item.platform_sku_id))
    selected: list[SelectedCandidate] = []
    seen_skus: set[str] = set()
    for candidate in matched:
        if candidate.platform_sku_id in seen_skus:
            exclusions["duplicate_sku"] += 1
            continue
        seen_skus.add(candidate.platform_sku_id)
        selected.append(candidate)
        if len(selected) == limit:
            break

    return CandidateSelection(
        selected=tuple(selected),
        exclusions=dict(sorted(exclusions.items())),
        discovered_count=len(raw_candidates),
    )
