from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.automation.regions import MAINLAND_REGION_TARGETS
from app.db.models.automation import CollectionRegionTask, CollectionRun
from app.db.models.offers import SearchSession
from app.schemas.collection_runs import CollectionRegionTaskView, CollectionRunView


def create_run(
    db: Session,
    search_session_id: int,
    platform: str = "jd",
) -> CollectionRunView:
    if platform != "jd":
        raise ValueError("第一阶段仅支持京东自动采集")

    search = db.get(SearchSession, search_session_id)
    if search is None:
        raise ValueError("搜索会话不存在")
    if search.comparison_scope != "national":
        raise ValueError("只有全国比价会话可以启动自动采集")
    if search.status != "collecting":
        raise ValueError("只有采集中的搜索会话可以启动自动采集")
    existing = db.scalar(
        select(CollectionRun).where(
            CollectionRun.search_session_id == search_session_id,
            CollectionRun.platform == platform,
        )
    )
    if existing is not None:
        raise ValueError("该搜索会话已有京东采集任务")

    now = datetime.now(UTC)
    run = CollectionRun(
        search_session_id=search_session_id,
        platform=platform,
        status="queued",
        stage="discovering",
        candidate_source="browser",
        candidate_count=0,
        selected_candidate_count=0,
        completed_region_count=0,
        failed_region_count=0,
        skipped_region_count=0,
        current_region_code=None,
        pause_requested=False,
        stop_requested=False,
        last_error_code=None,
        last_error_summary=None,
        started_at=None,
        updated_at=now,
        finished_at=None,
    )
    db.add(run)
    db.flush()
    db.add_all(
        CollectionRegionTask(
            collection_run_id=run.id,
            region_code=target.region_code,
            province=target.province,
            city=target.city,
            district=target.district,
            sequence=target.sequence,
            status="queued",
            attempts=0,
            verified_candidate_count=0,
            accepted_offer_count=0,
            error_code=None,
            error_summary=None,
            started_at=None,
            finished_at=None,
        )
        for target in MAINLAND_REGION_TARGETS
    )
    db.flush()
    return run_view(run)


def get_run(db: Session, run_id: int) -> CollectionRunView:
    return run_view(require_run(db, run_id))


def list_region_tasks(db: Session, run_id: int) -> list[CollectionRegionTaskView]:
    require_run(db, run_id)
    tasks = db.scalars(
        select(CollectionRegionTask)
        .where(CollectionRegionTask.collection_run_id == run_id)
        .order_by(CollectionRegionTask.sequence)
    ).all()
    return [region_task_view(task) for task in tasks]


def get_task(db: Session, run_id: int, region_code: str) -> CollectionRegionTaskView:
    task = db.scalar(
        select(CollectionRegionTask).where(
            CollectionRegionTask.collection_run_id == run_id,
            CollectionRegionTask.region_code == region_code,
        )
    )
    if task is None:
        raise ValueError("地区采集任务不存在")
    return region_task_view(task)


def request_pause(db: Session, run_id: int) -> CollectionRunView:
    run = require_run(db, run_id)
    if run.status not in _TERMINAL_RUN_STATUSES:
        run.pause_requested = True
        run.updated_at = datetime.now(UTC)
        db.flush()
    return run_view(run)


def resume_run(db: Session, run_id: int) -> CollectionRunView:
    run = require_run(db, run_id)
    run.pause_requested = False
    if run.status in {"paused", "waiting_user"}:
        run.status = "queued"
        run.current_region_code = None
        run.last_error_code = None
        run.last_error_summary = None
        db.flush()
        waiting_tasks = db.scalars(
            select(CollectionRegionTask).where(
                CollectionRegionTask.collection_run_id == run_id,
                CollectionRegionTask.status == "waiting_user",
            )
        ).all()
        for task in waiting_tasks:
            _requeue_task(task)
    run.updated_at = datetime.now(UTC)
    db.flush()
    return run_view(run)


def request_stop(db: Session, run_id: int) -> CollectionRunView:
    run = require_run(db, run_id)
    if run.status not in _TERMINAL_RUN_STATUSES:
        run.stop_requested = True
        run.updated_at = datetime.now(UTC)
        db.flush()
    return run_view(run)


def retry_failed_regions(db: Session, run_id: int) -> CollectionRunView:
    run = require_run(db, run_id)
    db.flush()
    failed_tasks = db.scalars(
        select(CollectionRegionTask).where(
            CollectionRegionTask.collection_run_id == run_id,
            CollectionRegionTask.status == "failed",
        )
    ).all()
    for task in failed_tasks:
        _requeue_task(task)
    run.status = "queued"
    run.pause_requested = False
    run.stop_requested = False
    run.current_region_code = None
    run.last_error_code = None
    run.last_error_summary = None
    run.finished_at = None
    run.updated_at = datetime.now(UTC)
    db.flush()
    return refresh_run_counts(db, run_id)


def refresh_run_counts(db: Session, run_id: int) -> CollectionRunView:
    run = require_run(db, run_id)
    db.flush()
    counts = dict(
        db.execute(
            select(CollectionRegionTask.status, func.count(CollectionRegionTask.id))
            .where(CollectionRegionTask.collection_run_id == run_id)
            .group_by(CollectionRegionTask.status)
        ).all()
    )
    run.completed_region_count = counts.get("completed", 0)
    run.failed_region_count = counts.get("failed", 0)
    run.skipped_region_count = counts.get("skipped", 0)
    run.updated_at = datetime.now(UTC)
    db.flush()
    return run_view(run)


def recover_interrupted_runs(db: Session) -> int:
    db.flush()
    runs = db.scalars(select(CollectionRun).where(CollectionRun.status == "running")).all()
    now = datetime.now(UTC)
    for run in runs:
        interrupted_tasks = db.scalars(
            select(CollectionRegionTask).where(
                CollectionRegionTask.collection_run_id == run.id,
                CollectionRegionTask.status == "running",
            )
        ).all()
        for task in interrupted_tasks:
            _requeue_task(task)
        run.status = "queued"
        run.current_region_code = None
        run.updated_at = now
    db.flush()
    return len(runs)


def require_run(db: Session, run_id: int) -> CollectionRun:
    run = db.get(CollectionRun, run_id)
    if run is None:
        raise ValueError("采集任务不存在")
    return run


def run_view(run: CollectionRun) -> CollectionRunView:
    return CollectionRunView.model_validate(run, from_attributes=True)


def region_task_view(task: CollectionRegionTask) -> CollectionRegionTaskView:
    return CollectionRegionTaskView.model_validate(task, from_attributes=True)


def _requeue_task(task: CollectionRegionTask) -> None:
    task.status = "queued"
    task.error_code = None
    task.error_summary = None
    task.started_at = None
    task.finished_at = None


_TERMINAL_RUN_STATUSES = {
    "completed",
    "completed_partial",
    "stopped",
    "failed",
}
