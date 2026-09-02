from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def insert_legacy_offer(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO platforms (id, code, name, enabled) VALUES (1, 'jd', '京东', 1)")
            )
            connection.execute(
                text(
                    """
                    INSERT INTO search_sessions
                        (id, variant_id, region_code, include_conditional, status, created_at, finalized_at)
                    VALUES
                        (1, 1, NULL, 0, 'collecting', '2026-09-02 00:00:00', NULL),
                        (2, 1, '310100', 0, 'completed', '2026-09-02 00:00:00', '2026-09-02 00:01:00')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO offers
                        (id, search_session_id, platform_id, platform_sku_id, title, product_url,
                         merchant_discount_cents, platform_coupon_cents, member_discount_cents,
                         payment_discount_cents, subsidy_amount_cents, shipping_fee_cents,
                         installation_fee_cents, price_type, price_conditions_json, stock_status,
                         subsidy_status, region_code, region_name, match_confidence, source_type,
                         adapter_version, captured_at)
                    VALUES
                        (1, 1, 1, 'sku-1', 'iPhone 17 上海', 'https://example.invalid/jd/1',
                         0, 0, 0, 0, 0, 0, 0, 'total', '[]', 'in_stock', 'unknown',
                         '310100', '上海市', 100, 'fixture', 'fixture-v1', '2026-09-02 00:00:00')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO price_snapshots
                        (id, offer_id, comparable_price_cents, estimated_final_price_cents,
                         subsidy_status, captured_at, source_type)
                    VALUES (1, 1, 509900, NULL, 'unknown', '2026-09-02 00:00:00', 'fixture')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO offer_matches
                        (id, offer_id, score, accepted, review_required, reasons_json,
                         excluded_reason, rule_version, created_at)
                    VALUES (1, 1, 100, 1, 0, '[]', NULL, 'matcher-v1', '2026-09-02 00:00:00')
                    """
                )
            )
    finally:
        engine.dispose()


def insert_second_region_offer(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO offers
                        (id, search_session_id, platform_id, platform_sku_id, region_key,
                         title, product_url, merchant_discount_cents, platform_coupon_cents,
                         member_discount_cents, payment_discount_cents, subsidy_amount_cents,
                         shipping_fee_cents, installation_fee_cents, price_type,
                         price_conditions_json, stock_status, subsidy_status, region_code,
                         region_name, match_confidence, source_type, adapter_version, captured_at)
                    VALUES
                        (2, 1, 1, 'sku-1', 'code:110100', 'iPhone 17 北京',
                         'https://example.invalid/jd/1', 0, 0, 0, 0, 0, 0, 0, 'total', '[]',
                         'in_stock', 'unknown', '110100', '北京市', 100, 'fixture', 'fixture-v1',
                         '2026-09-02 00:01:00')
                    """
                )
            )
    finally:
        engine.dispose()


def test_upgrade_from_0004_backfills_scope_and_region_identity(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'upgrade.db').as_posix()}"
    config = alembic_config(database_url)
    command.upgrade(config, "0004_offer_regions")
    insert_legacy_offer(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            scopes = connection.execute(
                text("SELECT id, comparison_scope FROM search_sessions ORDER BY id")
            ).all()
            offer = connection.execute(
                text("SELECT region_key, region_code, region_name FROM offers WHERE id = 1")
            ).one()
            assert scopes == [(1, "national"), (2, "regional")]
            assert offer == ("code:310100", "310100", "上海市")
            assert connection.scalar(text("SELECT COUNT(*) FROM price_snapshots")) == 1
            assert connection.scalar(text("SELECT COUNT(*) FROM offer_matches")) == 1
        columns = {column["name"]: column for column in inspect(engine).get_columns("offers")}
        constraints = {item["name"]: item["column_names"] for item in inspect(engine).get_unique_constraints("offers")}
        assert columns["region_key"]["nullable"] is False
        assert constraints["uq_offers_session_platform_sku_region"] == [
            "search_session_id",
            "platform_id",
            "platform_sku_id",
            "region_key",
        ]
    finally:
        engine.dispose()

    insert_second_region_offer(database_url)


def test_downgrade_without_cross_region_duplicates_restores_0004(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'safe-downgrade.db').as_posix()}"
    config = alembic_config(database_url)
    command.upgrade(config, "0004_offer_regions")
    insert_legacy_offer(database_url)
    command.upgrade(config, "head")

    command.downgrade(config, "0004_offer_regions")

    engine = create_engine(database_url)
    try:
        assert "comparison_scope" not in {item["name"] for item in inspect(engine).get_columns("search_sessions")}
        assert "region_key" not in {item["name"] for item in inspect(engine).get_columns("offers")}
        constraints = {item["name"] for item in inspect(engine).get_unique_constraints("offers")}
        assert "uq_offers_session_platform_sku" in constraints
    finally:
        engine.dispose()


def test_downgrade_blocks_cross_region_duplicates_without_data_loss(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'blocked-downgrade.db').as_posix()}"
    config = alembic_config(database_url)
    command.upgrade(config, "0004_offer_regions")
    insert_legacy_offer(database_url)
    command.upgrade(config, "head")
    insert_second_region_offer(database_url)

    with pytest.raises(RuntimeError, match="存在跨地区重复报价"):
        command.downgrade(config, "0004_offer_regions")

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT COUNT(*) FROM offers")) == 2
        assert "region_key" in {item["name"] for item in inspect(engine).get_columns("offers")}
    finally:
        engine.dispose()
