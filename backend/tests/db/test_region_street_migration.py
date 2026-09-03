from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def migration_config(tmp_path: Path) -> Config:
    backend_root = Path(__file__).parents[2]
    config = Config(backend_root / "alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{(tmp_path / 'streets.db').as_posix()}")
    return config


def seed_collection_task(config: Config, region_code: str) -> None:
    command.upgrade(config, "0006_automatic_collection_runs")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with engine.begin() as connection:
        connection.execute(sa.text("PRAGMA foreign_keys=OFF"))
        connection.execute(sa.text("""
            INSERT INTO collection_runs (
                id, search_session_id, platform, status, stage, candidate_source,
                candidate_count, selected_candidate_count, completed_region_count,
                failed_region_count, skipped_region_count, pause_requested,
                stop_requested, updated_at
            ) VALUES (
                1, 1, 'jd', 'queued', 'verifying', 'browser',
                0, 0, 0, 0, 0, 0, 0, '2026-09-03 00:00:00'
            )
        """))
        connection.execute(sa.text("""
            INSERT INTO collection_region_tasks (
                collection_run_id, region_code, province, city, district,
                sequence, status, attempts, verified_candidate_count,
                accepted_offer_count
            ) VALUES (
                1, :region_code, '北京市', '北京市', '朝阳区',
                1, 'queued', 0, 0, 0
            )
        """), {"region_code": region_code})
    engine.dispose()


def test_region_street_migration_backfills_existing_task(tmp_path: Path) -> None:
    config = migration_config(tmp_path)
    seed_collection_task(config, "110100")

    command.upgrade(config, "head")

    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    columns = {item["name"]: item for item in inspect(engine).get_columns("collection_region_tasks")}
    with engine.connect() as connection:
        street = connection.scalar(sa.text(
            "SELECT street FROM collection_region_tasks WHERE region_code = '110100'"
        ))
    assert columns["street"]["nullable"] is False
    assert street == "奥运村街道"
    engine.dispose()


def test_region_street_migration_rejects_unknown_region_without_partial_schema(
    tmp_path: Path,
) -> None:
    config = migration_config(tmp_path)
    seed_collection_task(config, "999999")

    try:
        command.upgrade(config, "head")
    except RuntimeError as exc:
        assert str(exc) == "存在无法回填街道的地区任务: 999999"
    else:
        raise AssertionError("unknown region migration must fail")

    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    columns = {item["name"] for item in inspect(engine).get_columns("collection_region_tasks")}
    assert "street" not in columns
    engine.dispose()
