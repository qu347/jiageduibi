import json
from pathlib import Path

from app.core.config import DEFAULT_DATABASE_URL, PROJECT_ROOT
from app.db.session import build_engine, session_factory
from app.schemas.catalog import CatalogImport
from app.services.catalog import import_catalog


DEFAULT_FIXTURE = PROJECT_ROOT / "fixtures" / "catalog" / "iphone17.json"


def seed_catalog(
    database_url: str = DEFAULT_DATABASE_URL,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> dict[str, int]:
    payload = CatalogImport.model_validate(json.loads(fixture_path.read_text(encoding="utf-8")))
    engine = build_engine(database_url)
    try:
        with session_factory(engine)() as db:
            return import_catalog(db, payload)
    finally:
        engine.dispose()


if __name__ == "__main__":
    seed_catalog()
