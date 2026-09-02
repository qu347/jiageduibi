from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import inspect, make_url

from app.core.config import DEFAULT_DATABASE_URL
from app.db.session import build_engine


APP_VERSION = "0.1.0"


CATALOG_TABLES = {
    "brands",
    "product_series",
    "product_models",
    "product_variants",
    "product_aliases",
}


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="个人国补比价工具", version=APP_VERSION)
    configured_database_url = database_url or DEFAULT_DATABASE_URL

    @app.get("/api/health")
    def health() -> dict[str, str]:
        database_path = make_url(configured_database_url).database
        if database_path and database_path != ":memory:" and not Path(database_path).parent.exists():
            database_status = "pending"
        else:
            engine = build_engine(configured_database_url)
            try:
                database_status = "ok" if CATALOG_TABLES <= set(inspect(engine).get_table_names()) else "pending"
            finally:
                engine.dispose()
        return {"status": "ok", "version": APP_VERSION, "database": database_status}

    return app


app = create_app()
