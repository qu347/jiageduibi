from typing import Protocol

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.catalog import get_db
from app.automation.run_service import (
    create_run,
    get_run,
    list_region_tasks,
    request_pause,
    request_stop,
    resume_run,
    retry_failed_regions,
)
from app.schemas.collection_runs import (
    AutomationEnvironmentView,
    CollectionRegionTaskView,
    CollectionRunView,
    CreateCollectionRun,
)


router = APIRouter(prefix="/api", tags=["automatic-collection"])


class Coordinator(Protocol):
    def submit(self, run_id: int) -> bool: ...


def api_error(
    message: str,
    cause: str,
    *,
    partial_saved: bool = False,
    next_action: str = "检查会话状态后重试",
) -> dict[str, object]:
    return {
        "what_happened": message,
        "possible_cause": cause,
        "partial_saved": partial_saved,
        "next_action": next_action,
    }


@router.post(
    "/search-sessions/{session_id}/collection-runs",
    response_model=CollectionRunView,
    status_code=status.HTTP_201_CREATED,
)
def post_collection_run(
    session_id: int,
    value: CreateCollectionRun,
    request: Request,
    db: Session = Depends(get_db),
) -> CollectionRunView:
    try:
        run = create_run(db, session_id, value.platform)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=api_error("创建自动采集任务失败", str(exc)),
        ) from exc
    _coordinator(request).submit(run.id)
    return run


@router.get("/collection-runs/{run_id}", response_model=CollectionRunView)
def get_collection_run(run_id: int, db: Session = Depends(get_db)) -> CollectionRunView:
    try:
        return get_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=api_error("读取自动采集任务失败", str(exc)),
        ) from exc


@router.get(
    "/collection-runs/{run_id}/tasks",
    response_model=list[CollectionRegionTaskView],
)
def get_collection_tasks(
    run_id: int,
    db: Session = Depends(get_db),
) -> list[CollectionRegionTaskView]:
    try:
        return list_region_tasks(db, run_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=api_error("读取地区采集进度失败", str(exc)),
        ) from exc


@router.post("/collection-runs/{run_id}/pause", response_model=CollectionRunView)
def pause_collection_run(run_id: int, db: Session = Depends(get_db)) -> CollectionRunView:
    return _control(db, run_id, request_pause, "暂停自动采集失败")


@router.post("/collection-runs/{run_id}/resume", response_model=CollectionRunView)
def resume_collection_run(
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> CollectionRunView:
    result = _control(db, run_id, resume_run, "继续自动采集失败")
    _coordinator(request).submit(run_id)
    return result


@router.post("/collection-runs/{run_id}/stop", response_model=CollectionRunView)
def stop_collection_run(run_id: int, db: Session = Depends(get_db)) -> CollectionRunView:
    return _control(db, run_id, request_stop, "停止自动采集失败")


@router.post("/collection-runs/{run_id}/retry-failed", response_model=CollectionRunView)
def retry_collection_regions(
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> CollectionRunView:
    result = _control(db, run_id, retry_failed_regions, "重试失败地区失败")
    _coordinator(request).submit(run_id)
    return result


@router.get("/automation/environment", response_model=AutomationEnvironmentView)
def get_automation_environment(request: Request) -> AutomationEnvironmentView:
    environment = request.app.state.browser_gateway_factory().diagnose()
    return AutomationEnvironmentView(
        agent_reach_available=environment.agent_reach_available,
        opencli_available=environment.opencli_available,
        browser_bridge_ready=environment.browser_bridge_ready,
        plugin_ready=environment.plugin_ready,
        safe_message=environment.safe_message,
    )


def _control(
    db: Session,
    run_id: int,
    operation,
    message: str,
) -> CollectionRunView:
    try:
        result = operation(db, run_id)
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=api_error(message, str(exc))) from exc


def _coordinator(request: Request) -> Coordinator:
    return request.app.state.collection_coordinator
