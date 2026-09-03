from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


@pytest.fixture
def alembic_config(tmp_path: Path) -> Config:
    backend_root = Path(__file__).parents[2]
    config = Config(backend_root / "alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{(tmp_path / 'automatic.db').as_posix()}")
    return config


def test_automatic_collection_migration_adds_only_new_tables(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "0005_national_multiregion_sessions")
    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    before = set(inspect(engine).get_table_names())
    engine.dispose()

    command.upgrade(alembic_config, "0006_automatic_collection_runs")
    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    after = set(inspect(engine).get_table_names())
    assert after - before == {
        "collection_runs",
        "collection_candidates",
        "collection_region_tasks",
    }
    assert {"search_sessions", "offers", "price_snapshots"} <= after
    engine.dispose()


def test_automatic_collection_tables_have_recovery_identities(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "head")
    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    inspector = inspect(engine)

    run_constraints = {item["name"]: item["column_names"] for item in inspector.get_unique_constraints("collection_runs")}
    candidate_constraints = {
        item["name"]: item["column_names"]
        for item in inspector.get_unique_constraints("collection_candidates")
    }
    task_constraints = {
        item["name"]: item["column_names"]
        for item in inspector.get_unique_constraints("collection_region_tasks")
    }

    assert run_constraints["uq_collection_run_session_platform"] == ["search_session_id", "platform"]
    assert candidate_constraints["uq_collection_candidate_sku"] == [
        "collection_run_id",
        "platform_sku_id",
    ]
    assert task_constraints["uq_collection_task_region"] == ["collection_run_id", "region_code"]
    engine.dispose()


def test_automatic_collection_migration_downgrades_without_touching_offers(
    alembic_config: Config,
) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0005_national_multiregion_sessions")
    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    tables = set(inspect(engine).get_table_names())
    assert "collection_runs" not in tables
    assert "collection_candidates" not in tables
    assert "collection_region_tasks" not in tables
    assert {"search_sessions", "offers", "price_snapshots"} <= tables
    engine.dispose()
