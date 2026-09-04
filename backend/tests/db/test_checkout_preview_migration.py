from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def config_for(tmp_path: Path) -> Config:
    config = Config(Path(__file__).parents[2] / "alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{(tmp_path / 'checkout-preview.db').as_posix()}")
    return config


def test_checkout_preview_migration_adds_unique_resumable_tasks(tmp_path: Path) -> None:
    config = config_for(tmp_path)
    command.upgrade(config, "0008_price_sheet_batches")

    command.upgrade(config, "head")

    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    inspector = inspect(engine)
    assert {"price_sheet_checkout_tasks", "price_sheet_checkout_results"} <= set(inspector.get_table_names())
    assert {item["name"] for item in inspector.get_unique_constraints("price_sheet_checkout_tasks")} == {
        "uq_price_sheet_checkout_item_region_sku",
    }
    assert {item["name"] for item in inspector.get_unique_constraints("price_sheet_checkout_results")} == {
        "uq_price_sheet_checkout_result_task",
    }
    assert {column["name"] for column in inspector.get_columns("price_sheet_checkout_results")} >= {
        "quantity",
        "target_only",
        "payable_price_cents",
        "price_status",
        "region_confirmed",
        "cart_restored",
    }
    engine.dispose()


def test_checkout_preview_downgrade_preserves_existing_price_sheet_tables(tmp_path: Path) -> None:
    config = config_for(tmp_path)
    command.upgrade(config, "head")

    command.downgrade(config, "0008_price_sheet_batches")

    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    tables = set(inspect(engine).get_table_names())
    assert "price_sheet_batches" in tables
    assert "price_sheet_region_results" in tables
    assert "price_sheet_checkout_tasks" not in tables
    assert "price_sheet_checkout_results" not in tables
    engine.dispose()
