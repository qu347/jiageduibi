from collections.abc import Sequence
from datetime import datetime

from app.schemas.subsidy import SubsidyContext, SubsidyDecision, SubsidyRuleInput


def subsidy_amount(price_cents: int, rate_basis_points: int, cap_cents: int | None) -> int:
    calculated = price_cents * rate_basis_points // 10_000
    return min(calculated, cap_cents) if cap_cents is not None else calculated


def rule_specificity(rule: SubsidyRuleInput, region_code: str) -> int:
    if rule.region_code == region_code:
        return 2
    if rule.region_code[:2] == region_code[:2] and rule.region_code.endswith("0000"):
        return 1
    return 0


def verified_timestamp(value: datetime | None) -> float:
    return value.timestamp() if value else 0.0


def evaluate_subsidy(
    rules: Sequence[SubsidyRuleInput],
    context: SubsidyContext,
) -> SubsidyDecision:
    if context.region_code is None:
        return SubsidyDecision(status="unknown", reason="需要先选择省市")

    eligible = [
        rule
        for rule in rules
        if rule.active
        and rule.valid_from <= context.at_date <= rule.valid_to
        and rule.category == context.category
        and rule_specificity(rule, context.region_code) > 0
        and (rule.max_unit_price_cents is None or context.price_cents <= rule.max_unit_price_cents)
        and (not rule.participating_platforms or context.platform in rule.participating_platforms)
        and (not rule.participating_shop_types or context.shop_type in rule.participating_shop_types)
    ]
    if not eligible:
        return SubsidyDecision(status="unknown", reason="当前地区和商品没有可用规则")

    eligible.sort(
        key=lambda item: (
            rule_specificity(item, context.region_code or ""),
            item.verified_at is not None,
            verified_timestamp(item.verified_at),
        ),
        reverse=True,
    )
    selected = eligible[0]
    selected_rank = (
        rule_specificity(selected, context.region_code),
        selected.verified_at is not None,
        verified_timestamp(selected.verified_at),
    )
    tied = [
        item
        for item in eligible[1:]
        if (
            rule_specificity(item, context.region_code),
            item.verified_at is not None,
            verified_timestamp(item.verified_at),
        )
        == selected_rank
    ]
    if any(
        (item.subsidy_rate_basis_points, item.subsidy_cap_cents)
        != (selected.subsidy_rate_basis_points, selected.subsidy_cap_cents)
        for item in tied
    ):
        return SubsidyDecision(status="unknown", reason="同级规则存在冲突，请人工确认")

    calculated = subsidy_amount(
        context.price_cents,
        selected.subsidy_rate_basis_points,
        selected.subsidy_cap_cents,
    )
    level = "city" if rule_specificity(selected, context.region_code) == 2 else "province"
    if context.platform_confirmed and context.platform_sku_matches:
        return SubsidyDecision(
            status="confirmed",
            amount_cents=context.platform_subsidy_amount_cents or calculated,
            rule_level=level,
            reason="平台已对同一 SKU 确认补贴",
        )
    return SubsidyDecision(
        status="estimated",
        amount_cents=calculated,
        rule_level=level,
        reason="按已配置地区规则估算，结算页为准",
    )
