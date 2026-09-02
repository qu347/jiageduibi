from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import inspect, make_url

from app.api.catalog import router as catalog_router
from app.api.extension import router as extension_router
from app.api.history import router as history_router
from app.api.offers import router as offers_router
from app.api.platforms import router as platforms_router
from app.api.search_sessions import router as search_sessions_router
from app.api.subsidy_rules import router as subsidy_rules_router
from app.core.config import DEFAULT_DATABASE_URL
from app.db.session import build_engine, session_factory


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
    app.state.engine = build_engine(configured_database_url)
    app.state.session_factory = session_factory(app.state.engine)
    app.include_router(catalog_router)
    app.include_router(extension_router)
    app.include_router(history_router)
    app.include_router(search_sessions_router)
    app.include_router(offers_router)
    app.include_router(platforms_router)
    app.include_router(subsidy_rules_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        database_path = make_url(configured_database_url).database
        if database_path and database_path != ":memory:" and not Path(database_path).parent.exists():
            database_status = "pending"
        else:
            database_status = (
                "ok" if CATALOG_TABLES <= set(inspect(app.state.engine).get_table_names()) else "pending"
            )
        return {"status": "ok", "version": APP_VERSION, "database": database_status}

    return app


app = create_app()
