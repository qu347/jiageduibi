from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from app.automation.regions import MAINLAND_REGION_TARGETS
from app.db.models.price_sheets import (
    PriceSheetBatch,
    PriceSheetItem,
    PriceSheetRegionResult,
    PriceSheetRegionTask,
)
from app.price_sheets.contracts import ParsedPriceSheet
from app.schemas.price_sheets import (
    PriceSheetBatchDetail,
    PriceSheetBatchView,
    PriceSheetItemInput,
    PriceSheetItemView,
    PriceSheetRegionTaskView,
    PriceSheetResultsView,
    PriceSheetResultView,
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
        for item in db.scalars(select(PriceSheetItem).where(
            PriceSheetItem.batch_id == batch_id,
            PriceSheetItem.status == "waiting_user",
        )).all():
            item.status = "queued"
            item.last_error_code = None
            item.last_error_summary = None
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


def recover_interrupted_batches(db: Session) -> int:
    batches = db.scalars(select(PriceSheetBatch).where(PriceSheetBatch.status == "running")).all()
    now = datetime.now(UTC)
    for batch in batches:
        item_ids = db.scalars(select(PriceSheetItem.id).where(PriceSheetItem.batch_id == batch.id)).all()
        for item in db.scalars(select(PriceSheetItem).where(
            PriceSheetItem.batch_id == batch.id,
            PriceSheetItem.status == "running",
        )).all():
            item.status = "queued"
            item.started_at = None
        if item_ids:
            for task in db.scalars(select(PriceSheetRegionTask).where(
                PriceSheetRegionTask.price_sheet_item_id.in_(item_ids),
                PriceSheetRegionTask.status == "running",
            )).all():
                task.status = "queued"
                task.started_at = None
        batch.status = "queued"
        batch.current_item_id = None
        batch.updated_at = now
    db.flush()
    return len(batches)


def get_results(db: Session, batch_id: int) -> PriceSheetResultsView:
    _require_batch(db, batch_id)
    items = db.scalars(select(PriceSheetItem).where(
        PriceSheetItem.batch_id == batch_id,
        PriceSheetItem.selected.is_(True),
    ).order_by(PriceSheetItem.sequence)).all()
    lower: list[PriceSheetResultView] = []
    not_lower: list[PriceSheetResultView] = []
    partial: list[PriceSheetResultView] = []
    for item in items:
        row = db.execute(
            select(PriceSheetRegionResult, PriceSheetRegionTask)
            .join(PriceSheetRegionTask, and_(
                PriceSheetRegionTask.price_sheet_item_id == PriceSheetRegionResult.price_sheet_item_id,
                PriceSheetRegionTask.region_code == PriceSheetRegionResult.region_code,
            ))
            .where(PriceSheetRegionResult.price_sheet_item_id == item.id)
            .order_by(
                PriceSheetRegionResult.trusted_price_cents,
                PriceSheetRegionTask.sequence,
                PriceSheetRegionResult.platform_sku_id,
            )
        ).first()
        complete = item.completed_region_count == item.total_region_count == 31 and item.failed_region_count == 0
        if not complete:
            partial.append(_result_view(item, row, "partial"))
        elif row is None or row[0].trusted_price_cents >= item.today_price_cents:
            not_lower.append(_result_view(item, row, "no_comparable" if row is None else "not_lower"))
        else:
            lower.append(_result_view(item, row, "lower"))
    return PriceSheetResultsView(
        lower_results=lower,
        not_lower_items=not_lower,
        partial_items=partial,
    )


def _result_view(item: PriceSheetItem, row, status: str) -> PriceSheetResultView:
    base = {
        "item_id": item.id,
        "model_name": item.model_name,
        "storage": item.storage,
        "color": item.color,
        "today_price_cents": item.today_price_cents,
        "status": status,
        "coverage": f"{item.completed_region_count}/{item.total_region_count or 31}",
    }
    if row is None:
        return PriceSheetResultView(**base)
    result, task = row
    return PriceSheetResultView(
        **base,
        region_code=result.region_code,
        address=_task_address(task),
        platform_sku_id=result.platform_sku_id,
        title=result.title,
        product_url=result.product_url,
        shop_name=result.shop_name,
        sale_price_cents=result.sale_price_cents,
        platform_coupon_cents=result.platform_coupon_cents + result.merchant_discount_cents,
        subsidy_amount_cents=result.subsidy_amount_cents,
        shipping_fee_cents=result.shipping_fee_cents,
        trusted_price_cents=result.trusted_price_cents,
        sale_price_includes_coupon=result.sale_price_includes_coupon,
        sale_price_includes_subsidy=result.sale_price_includes_subsidy,
        captured_at=result.captured_at,
    )


def _task_address(task: PriceSheetRegionTask) -> str:
    parts: list[str] = []
    for part in (task.province, task.city, task.district, task.street):
        if not parts or part != parts[-1]:
            parts.append(part)
    return " / ".join(parts)


def _require_batch(db: Session, batch_id: int) -> PriceSheetBatch:
    batch = db.get(PriceSheetBatch, batch_id)
    if batch is None:
        raise ValueError("价目表批次不存在")
    return batch
