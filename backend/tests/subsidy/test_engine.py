from datetime import UTC, date, datetime

from app.schemas.subsidy import SubsidyContext, SubsidyRuleInput
from app.subsidy.engine import evaluate_subsidy


def rule(region_code: str, rate_basis_points: int = 1000) -> SubsidyRuleInput:
    return SubsidyRuleInput(
        region_code=region_code,
        category="手机",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
        subsidy_rate_basis_points=rate_basis_points,
        subsidy_cap_cents=None,
        participating_platforms=["jd"],
        participating_shop_types=["self_operated"],
        notes="测试规则，不代表真实政策",
        source_url="https://example.invalid/rules/test",
        verified_at=None,
        active=True,
    )


def context(**changes: object) -> SubsidyContext:
    values: dict[str, object] = {
        "region_code": "110100",
        "category": "手机",
        "platform": "jd",
        "shop_type": "self_operated",
        "price_cents": 500000,
        "at_date": date(2026, 9, 2),
    }
    values.update(changes)
    return SubsidyContext.model_validate(values)


def test_city_rule_beats_province_rule_for_estimate() -> None:
    decision = evaluate_subsidy(
        rules=[rule("110000", 1000), rule("110100", 1500)],
        context=context(),
    )

    assert decision.status == "estimated"
    assert decision.amount_cents == 75000
    assert decision.rule_level == "city"


def test_missing_region_returns_unknown() -> None:
    decision = evaluate_subsidy(rules=[rule("110000")], context=context(region_code=None))

    assert decision.status == "unknown"
    assert decision.reason == "该报价未提供适用地区，无法匹配地区补贴规则"


def test_platform_confirmation_overrides_estimate_only_for_same_sku() -> None:
    decision = evaluate_subsidy(
        rules=[rule("110100")],
        context=context(
            platform_confirmed=True,
            platform_sku_matches=True,
            platform_subsidy_amount_cents=42000,
        ),
    )

    assert decision.status == "confirmed"
    assert decision.amount_cents == 42000


def test_verified_timestamp_breaks_same_level_tie() -> None:
    older = rule("110100", 1000).model_copy(update={"verified_at": datetime(2026, 8, 1, tzinfo=UTC)})
    newer = rule("110100", 1200).model_copy(update={"verified_at": datetime(2026, 9, 1, tzinfo=UTC)})

    decision = evaluate_subsidy([older, newer], context())

    assert decision.amount_cents == 60000
    assert decision.status == "estimated"
