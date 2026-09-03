from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.automation.regions import MAINLAND_REGION_TARGETS
from app.db.models.price_sheets import PriceSheetBatch, PriceSheetItem, PriceSheetRegionTask
from app.price_sheets.contracts import ParsedPriceSheet
from app.schemas.price_sheets import (
    PriceSheetBatchDetail,
    PriceSheetBatchView,
    PriceSheetItemInput,
    PriceSheetItemView,
    PriceSheetRegionTaskView,
)


def create_batch(db: Session, file_name: str, parsed: ParsedPriceSheet) -> PriceSheetBatchDetail:
    now = datetime.now(UTC)
    batch = PriceSheetBatch(
        file_name=file_name,
        price_date=parsed.price_date,
        date_inferred=parsed.date_inferred,
        status="reviewing",
        recognized_count=len(parsed.items),
        selected_count=len(parsed.items),
        completed_item_count=0,
        partial_item_count=0,
        failed_item_count=0,
        lower_price_count=0,
        current_item_id=None,
        pause_requested=False,
        stop_requested=False,
        last_error_code=None,
        last_error_summary=None,
        created_at=now,
        updated_at=now,
        started_at=None,
        finished_at=None,
    )
    db.add(batch)
    db.flush()
    for sequence, item in enumerate(parsed.items, start=1):
        db.add(PriceSheetItem(
            batch_id=batch.id,
            sequence=sequence,
            selected=True,
            brand=item.brand,
            model_name=item.model_name,
            storage=item.storage,
            color=item.color,
            today_price_cents=item.today_price_cents,
            raw_text=item.raw_text,
            confidence=item.confidence,
            review_required=item.review_required,
            status="reviewing",
            candidates_json=None,
            candidate_count=0,
            total_region_count=0,
            completed_region_count=0,
            failed_region_count=0,
            lowest_price_cents=None,
            last_error_code=None,
            last_error_summary=None,
            started_at=None,
            finished_at=None,
        ))
    db.flush()
    return get_batch_detail(db, batch.id)


def get_batch_detail(db: Session, batch_id: int) -> PriceSheetBatchDetail:
    batch = _require_batch(db, batch_id)
    items = db.scalars(
        select(PriceSheetItem).where(PriceSheetItem.batch_id == batch_id).order_by(PriceSheetItem.sequence)
    ).all()
    item_ids = [item.id for item in items]
    tasks = [] if not item_ids else db.scalars(
        select(PriceSheetRegionTask)
        .where(PriceSheetRegionTask.price_sheet_item_id.in_(item_ids))
        .order_by(PriceSheetRegionTask.price_sheet_item_id, PriceSheetRegionTask.sequence)
    ).all()
    return PriceSheetBatchDetail(
        batch=PriceSheetBatchView.model_validate(batch, from_attributes=True),
        items=[PriceSheetItemView.model_validate(item, from_attributes=True) for item in items],
        tasks=[PriceSheetRegionTaskView.model_validate(task, from_attributes=True) for task in tasks],
    )


def replace_items(
    db: Session,
    batch_id: int,
    price_date: date,
    values: list[PriceSheetItemInput | dict[str, object]],
) -> PriceSheetBatchDetail:
    batch = _require_batch(db, batch_id)
    if batch.status != "reviewing":
        raise ValueError("只有待校对批次可以修改")
    items = [PriceSheetItemInput.model_validate(value) for value in values]
    identities = [(item.model_name, item.storage, item.color) for item in items]
    if len(set(identities)) != len(identities):
        raise ValueError("同一批次存在重复的型号、容量和颜色")

    db.execute(delete(PriceSheetItem).where(PriceSheetItem.batch_id == batch_id))
    for sequence, item in enumerate(items, start=1):
        db.add(PriceSheetItem(
            batch_id=batch_id,
            sequence=sequence,
            **item.model_dump(),
            status="reviewing",
            candidates_json=None,
            candidate_count=0,
            total_region_count=0,
            completed_region_count=0,
            failed_region_count=0,
            lowest_price_cents=None,
            last_error_code=None,
            last_error_summary=None,
            started_at=None,
            finished_at=None,
        ))
    batch.price_date = price_date
    batch.date_inferred = False
    batch.recognized_count = len(items)
    batch.selected_count = sum(item.selected for item in items)
    batch.updated_at = datetime.now(UTC)
    db.flush()
    return get_batch_detail(db, batch_id)


def start_batch(db: Session, batch_id: int) -> PriceSheetBatchDetail:
    batch = _require_batch(db, batch_id)
    if batch.status != "reviewing":
        return get_batch_detail(db, batch_id)
    items = db.scalars(
        select(PriceSheetItem).where(PriceSheetItem.batch_id == batch_id).order_by(PriceSheetItem.sequence)
    ).all()
    selected = [item for item in items if item.selected]
    if not selected:
        raise ValueError("至少选择一个完整规格后才能开始比价")

    for item in items:
        item.status = "queued" if item.selected else "skipped"
        if not item.selected:
            continue
        item.total_region_count = len(MAINLAND_REGION_TARGETS)
        for target in MAINLAND_REGION_TARGETS:
            db.add(PriceSheetRegionTask(
                price_sheet_item_id=item.id,
                region_code=target.region_code,
                province=target.province,
                city=target.city,
                district=target.district,
                street=target.street,
                sequence=target.sequence,
                status="queued",
                attempts=0,
                verified_candidate_count=0,
                lowest_result_cents=None,
                error_code=None,
                error_summary=None,
                started_at=None,
                finished_at=None,
            ))
    batch.status = "queued"
    batch.selected_count = len(selected)
    batch.pause_requested = False
    batch.stop_requested = False
    batch.updated_at = datetime.now(UTC)
    db.flush()
    return get_batch_detail(db, batch_id)


def request_pause(db: Session, batch_id: int) -> PriceSheetBatchDetail:
    batch = _require_batch(db, batch_id)
    if batch.status not in {"completed", "completed_partial", "stopped", "failed"}:
        batch.pause_requested = True
        batch.updated_at = datetime.now(UTC)
        db.flush()
    return get_batch_detail(db, batch_id)


def resume_batch(db: Session, batch_id: int) -> PriceSheetBatchDetail:
    batch = _require_batch(db, batch_id)
    batch.pause_requested = False
    if batch.status in {"paused", "waiting_user"}:
        batch.status = "queued"
        batch.last_error_code = None
        batch.last_error_summary = None
        item_ids = db.scalars(select(PriceSheetItem.id).where(PriceSheetItem.batch_id == batch_id)).all()
        if item_ids:
            tasks = db.scalars(select(PriceSheetRegionTask).where(
                PriceSheetRegionTask.price_sheet_item_id.in_(item_ids),
                PriceSheetRegionTask.status == "waiting_user",
            )).all()
            for task in tasks:
                task.status = "queued"
                task.error_code = None
                task.error_summary = None
    batch.updated_at = datetime.now(UTC)
    db.flush()
    return get_batch_detail(db, batch_id)


def request_stop(db: Session, batch_id: int) -> PriceSheetBatchDetail:
    batch = _require_batch(db, batch_id)
    if batch.status not in {"completed", "completed_partial", "stopped", "failed"}:
        batch.stop_requested = True
        batch.updated_at = datetime.now(UTC)
        db.flush()
    return get_batch_detail(db, batch_id)


def retry_failed(db: Session, batch_id: int) -> PriceSheetBatchDetail:
    batch = _require_batch(db, batch_id)
    item_ids = db.scalars(select(PriceSheetItem.id).where(PriceSheetItem.batch_id == batch_id)).all()
    if item_ids:
        tasks = db.scalars(select(PriceSheetRegionTask).where(
            PriceSheetRegionTask.price_sheet_item_id.in_(item_ids),
            PriceSheetRegionTask.status == "failed",
        )).all()
        for task in tasks:
            task.status = "queued"
            task.error_code = None
            task.error_summary = None
            task.started_at = None
            task.finished_at = None
    for item in db.scalars(select(PriceSheetItem).where(PriceSheetItem.batch_id == batch_id)).all():
        if item.status in {"failed", "partial"}:
            item.status = "queued"
            item.last_error_code = None
            item.last_error_summary = None
            item.finished_at = None
    batch.status = "queued"
    batch.pause_requested = False
    batch.stop_requested = False
    batch.last_error_code = None
    batch.last_error_summary = None
    batch.finished_at = None
    batch.updated_at = datetime.now(UTC)
    db.flush()
    return get_batch_detail(db, batch_id)


def _require_batch(db: Session, batch_id: int) -> PriceSheetBatch:
    batch = db.get(PriceSheetBatch, batch_id)
    if batch is None:
        raise ValueError("价目表批次不存在")
    return batch
