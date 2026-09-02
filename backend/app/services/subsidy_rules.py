import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.subsidy import SubsidyRule
from app.schemas.subsidy import SubsidyRuleInput, SubsidyRuleView


def list_rules(db: Session) -> list[SubsidyRuleView]:
    rules = list(
        db.scalars(
            select(SubsidyRule)
            .where(SubsidyRule.deleted_at.is_(None))
            .order_by(SubsidyRule.region_code, SubsidyRule.category, SubsidyRule.id)
        )
    )
    return [rule_view(rule) for rule in rules]


def create_rule(db: Session, value: SubsidyRuleInput) -> SubsidyRuleView:
    now = datetime.now(UTC)
    rule = SubsidyRule(created_at=now, updated_at=now)
    apply_rule(rule, value)
    db.add(rule)
    db.commit()
    return rule_view(rule)


def update_rule(db: Session, rule_id: int, value: SubsidyRuleInput) -> SubsidyRuleView:
    rule = db.get(SubsidyRule, rule_id)
    if rule is None or rule.deleted_at is not None:
        raise ValueError("补贴规则不存在")
    apply_rule(rule, value)
    rule.updated_at = datetime.now(UTC)
    db.commit()
    return rule_view(rule)


def apply_rule(rule: SubsidyRule, value: SubsidyRuleInput) -> None:
    rule.region_code = value.region_code
    rule.category = value.category
    rule.valid_from = value.valid_from
    rule.valid_to = value.valid_to
    rule.max_unit_price_cents = value.max_unit_price_cents
    rule.subsidy_rate_basis_points = value.subsidy_rate_basis_points
    rule.subsidy_cap_cents = value.subsidy_cap_cents
    rule.participating_platforms_json = json.dumps(value.participating_platforms, ensure_ascii=False)
    rule.participating_shop_types_json = json.dumps(value.participating_shop_types, ensure_ascii=False)
    rule.notes = value.notes
    rule.source_url = value.source_url
    rule.verified_at = value.verified_at
    rule.active = value.active
    rule.deleted_at = None


def rule_view(rule: SubsidyRule) -> SubsidyRuleView:
    return SubsidyRuleView(
        id=rule.id,
        region_code=rule.region_code,
        category=rule.category,
        valid_from=rule.valid_from,
        valid_to=rule.valid_to,
        max_unit_price_cents=rule.max_unit_price_cents,
        subsidy_rate_basis_points=rule.subsidy_rate_basis_points,
        subsidy_cap_cents=rule.subsidy_cap_cents,
        participating_platforms=json.loads(rule.participating_platforms_json),
        participating_shop_types=json.loads(rule.participating_shop_types_json),
        notes=rule.notes,
        source_url=rule.source_url,
        verified_at=rule.verified_at,
        active=rule.active,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )
