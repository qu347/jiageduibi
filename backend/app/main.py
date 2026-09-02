from pathlib import Path
from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import inspect, make_url, select

from app.api.catalog import router as catalog_router
from app.api.collection_runs import router as collection_runs_router
from app.api.extension import router as extension_router
from app.api.history import router as history_router
from app.api.offers import router as offers_router
from app.api.platforms import router as platforms_router
from app.api.search_sessions import router as search_sessions_router
from app.api.subsidy_rules import router as subsidy_rules_router
from app.core.config import DEFAULT_DATABASE_URL, PROJECT_ROOT
from app.automation.contracts import BrowserGateway
from app.automation.coordinator import CollectionCoordinator
from app.automation.executor import CollectionExecutor
from app.automation.opencli import OpenCliGateway, SubprocessCommandRunner
from app.automation.run_service import recover_interrupted_runs
from app.db.session import build_engine, session_factory
from app.db.models.automation import CollectionRun


APP_VERSION = "0.1.0"


CATALOG_TABLES = {
    "brands",
    "product_series",
    "product_models",
    "product_variants",
    "product_aliases",
}


def create_app(
    database_url: str | None = None,
    *,
    browser_gateway_factory: Callable[[], BrowserGateway] | None = None,
    collection_coordinator_factory: Callable[[CollectionExecutor], CollectionCoordinator] | None = None,
) -> FastAPI:
    app = FastAPI(title="个人国补比价工具", version=APP_VERSION)
    configured_database_url = database_url or DEFAULT_DATABASE_URL
    app.state.engine = build_engine(configured_database_url)
    app.state.session_factory = session_factory(app.state.engine)
    app.state.browser_gateway_factory = browser_gateway_factory or (
        lambda: OpenCliGateway(SubprocessCommandRunner())
    )
    queued_run_ids: list[int] = []
    if "collection_runs" in inspect(app.state.engine).get_table_names():
        with app.state.session_factory() as db:
            recover_interrupted_runs(db)
            queued_run_ids = list(
                db.scalars(
                    select(CollectionRun.id)
                    .where(CollectionRun.status == "queued")
                    .order_by(CollectionRun.id)
                )
            )
            db.commit()
    executor = CollectionExecutor(app.state.session_factory, app.state.browser_gateway_factory)
    app.state.collection_coordinator = (
        collection_coordinator_factory(executor)
        if collection_coordinator_factory is not None
        else CollectionCoordinator(executor)
    )
    for queued_run_id in queued_run_ids:
        app.state.collection_coordinator.submit(queued_run_id)
    app.router.add_event_handler("shutdown", app.state.collection_coordinator.close)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        causes = [f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "what_happened": "请求数据校验失败",
                    "possible_cause": "; ".join(causes),
                    "partial_saved": False,
                    "next_action": "修正标注字段后重新提交",
                }
            },
        )
    app.include_router(catalog_router)
    app.include_router(collection_runs_router)
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

    frontend_dist = PROJECT_ROOT / "frontend" / "dist"
    if frontend_dist.is_dir() and (frontend_dist / "index.html").is_file():
        @app.get("/{full_path:path}", include_in_schema=False)
        def frontend(full_path: str) -> FileResponse:
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API route not found")
            candidate = (frontend_dist / full_path).resolve()
            if candidate.is_relative_to(frontend_dist.resolve()) and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()
