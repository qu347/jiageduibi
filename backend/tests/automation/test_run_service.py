from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.automation.run_service import (
    create_run,
    get_run,
    get_task,
    list_region_tasks,
    recover_interrupted_runs,
    refresh_run_counts,
    request_pause,
    request_stop,
    resume_run,
    retry_failed_regions,
)
from app.db.base import Base
from app.db.models import (
    Brand,
    CollectionRegionTask,
    CollectionRun,
    ProductModel,
    ProductSeries,
    ProductVariant,
    SearchSession,
)
from app.db.session import build_engine, session_factory


@pytest.fixture
def db(tmp_path) -> Session:
    engine = build_engine(f"sqlite:///{(tmp_path / 'run-service.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def variant_id(db: Session) -> int:
    brand = Brand(name="海尔", deleted_at=None)
    db.add(brand)
    db.flush()
    series = ProductSeries(brand_id=brand.id, name="空调", active=True, deleted_at=None)
    db.add(series)
    db.flush()
    model = ProductModel(
        series_id=series.id,
        model_name="海尔空调",
        model_code="KFR-35GW/TEST",
        category="空调",
        active=True,
        deleted_at=None,
    )
    db.add(model)
    db.flush()
    variant = ProductVariant(
        model_id=model.id,
        sku_code="KFR-35GW/TEST-1",
        storage="标准",
        memory=None,
        color="白色",
        region_version="中国大陆",
        condition="全新",
        active=True,
        deleted_at=None,
    )
    db.add(variant)
    db.commit()
    return variant.id


def add_search(
    db: Session,
    variant_id: int,
    *,
    scope: str = "national",
    status: str = "collecting",
) -> int:
    search = SearchSession(
        variant_id=variant_id,
        region_code="110100" if scope == "regional" else None,
        comparison_scope=scope,
        include_conditional=False,
        status=status,
        created_at=datetime.now(UTC),
        finalized_at=datetime.now(UTC) if status == "completed" else None,
    )
    db.add(search)
    db.commit()
    return search.id


def test_create_run_builds_31_ordered_tasks_for_national_collecting_session(
    db: Session,
    variant_id: int,
) -> None:
    search_id = add_search(db, variant_id)

    view = create_run(db, search_id, "jd")
    db.commit()
    tasks = list_region_tasks(db, view.id)

    assert view.status == "queued"
    assert view.stage == "discovering"
    assert view.total_region_count == 31
    assert len(tasks) == 31
    assert [task.sequence for task in tasks] == list(range(1, 32))
    assert tasks[0].region_code == "110100"
    assert tasks[-1].region_code == "650100"


def test_create_run_rejects_invalid_sessions_platform_and_duplicate(
    db: Session,
    variant_id: int,
) -> None:
    regional_id = add_search(db, variant_id, scope="regional")
    completed_id = add_search(db, variant_id, status="completed")
    national_id = add_search(db, variant_id)

    with pytest.raises(ValueError, match="全国"):
        create_run(db, regional_id, "jd")
    with pytest.raises(ValueError, match="采集中"):
        create_run(db, completed_id, "jd")
    with pytest.raises(ValueError, match="京东"):
        create_run(db, national_id, "pdd")

    create_run(db, national_id, "jd")
    db.commit()
    with pytest.raises(ValueError, match="已有"):
        create_run(db, national_id, "jd")


def test_pause_resume_stop_and_retry_are_idempotent(
    db: Session,
    variant_id: int,
) -> None:
    run_id = create_run(db, add_search(db, variant_id), "jd").id
    request_pause(db, run_id)
    request_pause(db, run_id)
    assert get_run(db, run_id).pause_requested is True

    stored_run = db.get(CollectionRun, run_id)
    assert stored_run is not None
    stored_run.status = "waiting_user"
    waiting_task = list_region_tasks(db, run_id)[0]
    stored_task = db.get(CollectionRegionTask, waiting_task.id)
    assert stored_task is not None
    stored_task.status = "waiting_user"
    stored_task.error_code = "LOGIN_REQUIRED"
    stored_task.error_summary = "请登录"

    resume_run(db, run_id)
    resume_run(db, run_id)
    assert get_run(db, run_id).status == "queued"
    assert get_run(db, run_id).pause_requested is False
    assert get_task(db, run_id, waiting_task.region_code).status == "queued"
    assert get_task(db, run_id, waiting_task.region_code).error_code is None

    all_tasks = list_region_tasks(db, run_id)
    failed = db.get(CollectionRegionTask, all_tasks[1].id)
    completed = db.get(CollectionRegionTask, all_tasks[2].id)
    assert failed is not None and completed is not None
    failed.status = "failed"
    failed.error_code = "NETWORK_ERROR"
    completed.status = "completed"
    request_stop(db, run_id)
    request_stop(db, run_id)
    retry_failed_regions(db, run_id)
    retry_failed_regions(db, run_id)

    assert get_run(db, run_id).stop_requested is False
    assert get_task(db, run_id, failed.region_code).status == "queued"
    assert get_task(db, run_id, failed.region_code).error_code is None
    assert get_task(db, run_id, completed.region_code).status == "completed"


def test_refresh_counts_derives_values_from_region_tasks(
    db: Session,
    variant_id: int,
) -> None:
    run_id = create_run(db, add_search(db, variant_id)).id
    tasks = list_region_tasks(db, run_id)
    for index, status in enumerate(("completed", "completed", "failed", "skipped")):
        task = db.get(CollectionRegionTask, tasks[index].id)
        assert task is not None
        task.status = status

    view = refresh_run_counts(db, run_id)

    assert view.completed_region_count == 2
    assert view.failed_region_count == 1
    assert view.skipped_region_count == 1


def test_recovery_requeues_only_interrupted_work(
    db: Session,
    variant_id: int,
) -> None:
    run_id = create_run(db, add_search(db, variant_id)).id
    run = db.get(CollectionRun, run_id)
    assert run is not None
    run.status = "running"
    run.stage = "verifying"
    run.current_region_code = "310100"
    tasks = list_region_tasks(db, run_id)
    completed = db.get(CollectionRegionTask, tasks[0].id)
    running = db.get(CollectionRegionTask, tasks[8].id)
    assert completed is not None and running is not None
    completed.status = "completed"
    running.status = "running"
    running.error_code = "TRANSIENT"

    assert recover_interrupted_runs(db) == 1

    assert get_run(db, run_id).status == "queued"
    assert get_run(db, run_id).current_region_code is None
    assert get_task(db, run_id, completed.region_code).status == "completed"
    recovered = get_task(db, run_id, running.region_code)
    assert recovered.status == "queued"
    assert recovered.error_code is None
