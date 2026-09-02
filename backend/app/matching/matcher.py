from app.matching.exclusions import explicit_offer_exclusion
from app.matching.extractors import (
    extract_model_code,
    extract_storage,
    title_has_brand,
    title_has_mainland_region,
    title_has_new_condition,
    title_has_other_region,
)
from app.schemas.offers import MatchResult, MatchTarget, RawOffer


WEIGHTS = {"brand": 20, "model": 35, "storage": 20, "region": 15, "condition": 10}


def classify_score(score: int) -> tuple[bool, bool]:
    if score >= 85:
        return True, score < 95
    if score >= 70:
        return False, True
    return False, False


def excluded(reason: str) -> MatchResult:
    return MatchResult(
        score=0,
        accepted=False,
        review_required=False,
        reasons=[],
        excluded_reason=reason,
    )


def match_offer(raw: RawOffer, target: MatchTarget) -> MatchResult:
    title = raw.title
    reason = explicit_offer_exclusion(title)
    if reason:
        return excluded(reason)

    model_code = extract_model_code(title)
    if model_code is not None and model_code != target.model_code:
        return excluded("model_mismatch")

    storage = extract_storage(title)
    if storage is not None and storage.casefold() != target.storage.casefold():
        return excluded("storage_mismatch")

    if title_has_other_region(title) and "国行" in target.region_version:
        return excluded("region_mismatch")

    score = 0
    reasons: list[str] = []

    if title_has_brand(title, target.brand):
        score += WEIGHTS["brand"]
        reasons.append("品牌匹配")
    else:
        reasons.append("标题未明确品牌")

    if model_code == target.model_code:
        score += WEIGHTS["model"]
        reasons.append("型号完全匹配")
    else:
        reasons.append("标题未明确型号")

    if storage is not None and storage.casefold() == target.storage.casefold():
        score += WEIGHTS["storage"]
        reasons.append("容量匹配")
    else:
        reasons.append("标题未明确容量")

    if title_has_mainland_region(title) and "国行" in target.region_version:
        score += WEIGHTS["region"]
        reasons.append("版本匹配")
    else:
        reasons.append("标题未明确版本")

    if title_has_new_condition(title) and target.condition == "全新":
        score += WEIGHTS["condition"]
        reasons.append("成色匹配")
    else:
        reasons.append("标题未明确成色")

    accepted, review_required = classify_score(score)
    return MatchResult(
        score=score,
        accepted=accepted,
        review_required=review_required,
        reasons=reasons,
    )
