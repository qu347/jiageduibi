from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.main import create_app


CATALOG_TABLES = {
    "brands",
    "product_series",
    "product_models",
    "product_variants",
    "product_aliases",
}


def test_catalog_migration_upgrades_and_downgrades(tmp_path: Path) -> None:
    database = tmp_path / "catalog.db"
    database_url = f"sqlite:///{database.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    assert CATALOG_TABLES <= set(inspect(engine).get_table_names())
    engine.dispose()

    response = TestClient(create_app(database_url=database_url)).get("/api/health")
    assert response.json()["database"] == "ok"

    command.downgrade(config, "base")

    engine = create_engine(database_url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()
