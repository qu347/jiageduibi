from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.automation.regions import MAINLAND_REGION_TARGETS, get_region_target
from app.db.models.price_sheets import (
    PriceSheetBatch,
    PriceSheetCheckoutResult,
    PriceSheetCheckoutTask,
    PriceSheetItem,
    PriceSheetRegionTask,
)
from app.price_sheets.contracts import ParsedPriceSheet
from app.schemas.price_sheets import (
    PriceSheetBatchDetail,
    PriceSheetBatchView,
    PriceSheetCheckoutCurrentView,
    PriceSheetCheckoutProgressView,
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
        checkout_progress=_checkout_progress(db, batch, items),
    )


def _checkout_progress(
    db: Session,
    batch: PriceSheetBatch,
    items: list[PriceSheetItem],
) -> PriceSheetCheckoutProgressView:
    item_ids = [item.id for item in items]
    candidate_count = sum(item.candidate_count for item in items if item.selected)
    if not item_ids:
        return PriceSheetCheckoutProgressView(
            stage="review" if batch.status == "reviewing" else "candidate_search",
            candidate_count=0,
            task_total=0,
            task_finished=0,
            verified_count=0,
            conditional_count=0,
            address_required_count=0,
            unavailable_count=0,
            failed_count=0,
            skipped_count=0,
            cart_attention_required=False,
        )

    task_counts = dict(db.execute(
        select(PriceSheetCheckoutTask.status, func.count(PriceSheetCheckoutTask.id))
        .where(PriceSheetCheckoutTask.price_sheet_item_id.in_(item_ids))
        .group_by(PriceSheetCheckoutTask.status)
    ).all())
    price_counts = dict(db.execute(
        select(PriceSheetCheckoutResult.price_status, func.count(PriceSheetCheckoutResult.id))
        .join(PriceSheetCheckoutTask, PriceSheetCheckoutTask.id == PriceSheetCheckoutResult.checkout_task_id)
        .where(PriceSheetCheckoutTask.price_sheet_item_id.in_(item_ids))
        .group_by(PriceSheetCheckoutResult.price_status)
    ).all())
    address_required_count = db.scalar(
        select(func.count(PriceSheetCheckoutResult.id))
        .join(PriceSheetCheckoutTask, PriceSheetCheckoutTask.id == PriceSheetCheckoutResult.checkout_task_id)
        .where(
            PriceSheetCheckoutTask.price_sheet_item_id.in_(item_ids),
            PriceSheetCheckoutResult.unavailable_code == "checkout_address_required",
        )
    ) or 0
    cart_attention_required = (db.scalar(
        select(func.count(PriceSheetCheckoutTask.id)).where(
            PriceSheetCheckoutTask.price_sheet_item_id.in_(item_ids),
            PriceSheetCheckoutTask.error_code == "cart_isolation_failed",
        )
    ) or 0) > 0
    current_task = db.scalar(
        select(PriceSheetCheckoutTask)
        .join(PriceSheetItem, PriceSheetItem.id == PriceSheetCheckoutTask.price_sheet_item_id)
        .where(
            PriceSheetCheckoutTask.price_sheet_item_id.in_(item_ids),
            PriceSheetCheckoutTask.status == "running",
        )
        .order_by(PriceSheetItem.sequence, PriceSheetCheckoutTask.sequence)
    )
    current = None
    if current_task is not None:
        region = get_region_target(current_task.region_code)
        current = PriceSheetCheckoutCurrentView(
            platform_sku_id=current_task.platform_sku_id,
            region_code=current_task.region_code,
            address=_region_address(region.province, region.city, region.district, region.street),
            entry_mode=current_task.entry_mode,
        )
    task_total = sum(task_counts.values())
    finished = sum(task_counts.get(status, 0) for status in ("completed", "failed", "skipped"))
    if task_total:
        stage = "checkout_verification"
    elif batch.status == "reviewing":
        stage = "review"
    elif batch.status in {"completed", "completed_partial", "failed", "stopped"}:
        stage = "completed"
    else:
        stage = "candidate_search"
    return PriceSheetCheckoutProgressView(
        stage=stage,
        candidate_count=candidate_count,
        task_total=task_total,
        task_finished=finished,
        verified_count=price_counts.get("verified", 0),
        conditional_count=price_counts.get("conditional", 0),
        address_required_count=address_required_count,
        unavailable_count=price_counts.get("unavailable", 0),
        failed_count=task_counts.get("failed", 0),
        skipped_count=task_counts.get("skipped", 0),
        cart_attention_required=cart_attention_required,
        current=current,
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
            checkout_tasks = db.scalars(select(PriceSheetCheckoutTask).where(
                PriceSheetCheckoutTask.price_sheet_item_id.in_(item_ids),
                PriceSheetCheckoutTask.status == "waiting_user",
            )).all()
            for task in checkout_tasks:
                task.status = "queued"
                task.error_code = None
                task.error_summary = None
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
        checkout_tasks = db.scalars(select(PriceSheetCheckoutTask).where(
            PriceSheetCheckoutTask.price_sheet_item_id.in_(item_ids),
            PriceSheetCheckoutTask.status == "failed",
        )).all()
        for task in checkout_tasks:
            task.status = "queued"
            task.error_code = None
            task.error_summary = None
            task.started_at = None
            task.finished_at = None
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
            for task in db.scalars(select(PriceSheetCheckoutTask).where(
                PriceSheetCheckoutTask.price_sheet_item_id.in_(item_ids),
                PriceSheetCheckoutTask.status == "running",
            )).all():
                task.status = "queued"
                task.started_at = None
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
        rows = db.execute(
            select(PriceSheetCheckoutResult, PriceSheetCheckoutTask)
            .join(PriceSheetCheckoutTask, PriceSheetCheckoutTask.id == PriceSheetCheckoutResult.checkout_task_id)
            .where(
                PriceSheetCheckoutTask.price_sheet_item_id == item.id,
                PriceSheetCheckoutResult.price_status == "verified",
                PriceSheetCheckoutResult.payable_price_cents.is_not(None),
            )
            .order_by(
                PriceSheetCheckoutResult.payable_price_cents,
                (PriceSheetCheckoutTask.sequence - 1) % len(MAINLAND_REGION_TARGETS),
                PriceSheetCheckoutTask.sequence,
                PriceSheetCheckoutTask.platform_sku_id,
            )
        ).all()
        row = rows[0] if rows else None
        coverage_count = len({task.region_code for _result, task in rows})
        failed_count = db.scalar(select(func.count(PriceSheetCheckoutTask.id)).where(
            PriceSheetCheckoutTask.price_sheet_item_id == item.id,
            PriceSheetCheckoutTask.status == "failed",
        )) or 0
        if item.candidate_count == 0 and item.status == "completed":
            not_lower.append(_result_view(item, None, "no_comparable", 0, failed_count))
        elif coverage_count != len(MAINLAND_REGION_TARGETS):
            partial.append(_result_view(item, row, "partial", coverage_count, failed_count))
        elif row is None or row[0].payable_price_cents >= item.today_price_cents:
            not_lower.append(_result_view(item, row, "not_lower", coverage_count, failed_count))
        else:
            lower.append(_result_view(item, row, "lower", coverage_count, failed_count))
    return PriceSheetResultsView(
        lower_results=lower,
        not_lower_items=not_lower,
        partial_items=partial,
    )


def _result_view(
    item: PriceSheetItem,
    row,
    status: str,
    coverage_count: int,
    failed_count: int,
) -> PriceSheetResultView:
    base = {
        "item_id": item.id,
        "model_name": item.model_name,
        "storage": item.storage,
        "color": item.color,
        "today_price_cents": item.today_price_cents,
        "status": status,
        "coverage": f"{coverage_count}/{len(MAINLAND_REGION_TARGETS)}",
        "failed_count": failed_count,
    }
    if row is None:
        return PriceSheetResultView(**base)
    result, task = row
    region = get_region_target(task.region_code)
    return PriceSheetResultView(
        **base,
        region_code=task.region_code,
        address=_region_address(region.province, region.city, region.district, region.street),
        platform_sku_id=task.platform_sku_id,
        title=result.title,
        product_url=result.product_url,
        shop_name=result.shop_name,
        entry_mode=task.entry_mode,
        price_status=result.price_status,
        quantity=result.quantity,
        target_only=result.target_only,
        line_original_price_cents=result.line_original_price_cents,
        line_sale_price_cents=result.line_sale_price_cents,
        merchant_discount_cents=result.merchant_discount_cents,
        ordinary_coupon_cents=result.ordinary_coupon_cents,
        subsidy_amount_cents=result.subsidy_amount_cents,
        shipping_fee_cents=result.shipping_fee_cents,
        payable_price_cents=result.payable_price_cents,
        discount_summary=result.discount_summary,
        conditional_reason=result.conditional_reason,
        cart_restored=result.cart_restored,
        captured_at=result.captured_at,
    )


def _region_address(province: str, city: str, district: str, street: str) -> str:
    parts: list[str] = []
    for part in (province, city, district, street):
        if not parts or part != parts[-1]:
            parts.append(part)
    return " / ".join(parts)


def _require_batch(db: Session, batch_id: int) -> PriceSheetBatch:
    batch = db.get(PriceSheetBatch, batch_id)
    if batch is None:
        raise ValueError("价目表批次不存在")
    return batch
