from datetime import date

from sqlalchemy import select

from app.core.config import DEFAULT_DATABASE_URL
from app.db.models.subsidy import SubsidyRule
from app.db.seed_catalog import seed_catalog
from app.db.session import build_engine, session_factory
from app.schemas.subsidy import SubsidyRuleInput
from app.services.subsidy_rules import create_rule, update_rule


DEMO_SOURCE_URL = "https://example.invalid/rules/beijing-pdd"


def seed_demo(database_url: str = DEFAULT_DATABASE_URL) -> None:
    seed_catalog(database_url=database_url)
    engine = build_engine(database_url)
    try:
        with session_factory(engine)() as db:
            value = SubsidyRuleInput(
                region_code="110100",
                category="手机",
                valid_from=date(2026, 1, 1),
                valid_to=date(2026, 12, 31),
                max_unit_price_cents=600000,
                subsidy_rate_basis_points=1000,
                subsidy_cap_cents=30000,
                participating_platforms=["pdd"],
                participating_shop_types=["authorized"],
                notes="仅用于离线演示，不代表真实政策",
                source_url=DEMO_SOURCE_URL,
                verified_at=None,
                active=True,
            )
            existing = db.scalar(select(SubsidyRule).where(SubsidyRule.source_url == DEMO_SOURCE_URL))
            if existing is None:
                create_rule(db, value)
            else:
                update_rule(db, existing.id, value)
    finally:
        engine.dispose()


if __name__ == "__main__":
    seed_demo()
