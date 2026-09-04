from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.automation.contracts import BrowserGateway, CheckoutPreview, DiscoveredCandidate, GatewayFailure
from app.automation.regions import MAINLAND_REGION_TARGETS, RegionTarget, get_region_target
from app.db.models.price_sheets import (
    PriceSheetBatch,
    PriceSheetCheckoutResult,
    PriceSheetCheckoutTask,
    PriceSheetItem,
)
from app.price_sheets.matching import PriceSheetTarget, select_price_sheet_candidates


WAITING_CODES = {
    "captcha",
    "login_required",
    "rate_limited",
    "safety_boundary_crossed",
    "cart_isolation_failed",
}
UNAVAILABLE_CODES = {
    "checkout_address_required",
    "checkout_region_unconfirmed",
    "buy_now_unavailable",
    "sku_unconfirmed",
    "price_unavailable",
}
RETRYABLE_CODES = {"network_error"}
RUN_FAILURE_CODES = {"tool_unavailable"}
TERMINAL_TASK_STATUSES = {"completed", "skipped", "failed"}
logger = logging.getLogger(__name__)


class PriceSheetExecutor:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        gateway_factory: Callable[[], BrowserGateway],
        retry_delays: tuple[float, float] = (0.0, 0.0),
        region_delay_seconds: float = 8.0,
        batch_size: int = 3,
        batch_cooldown_seconds: float = 60.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._sessions = session_factory
        self._gateway_factory = gateway_factory
        self._retry_delays = retry_delays
        self._region_delay_seconds = region_delay_seconds
        self._batch_size = batch_size
        self._batch_cooldown_seconds = batch_cooldown_seconds
        self._sleeper = sleeper

    def execute(self, batch_id: int) -> None:
        if not self._mark_running(batch_id):
            return
        gateway = self._gateway_factory()
        try:
            for item_id in self._queued_item_ids(batch_id):
                if not self._may_continue(batch_id):
                    return
                if not self._execute_item(batch_id, item_id, gateway):
                    return
            self._finish_batch(batch_id)
        except GatewayFailure as exc:
            self._handle_batch_failure(batch_id, exc)
        except Exception:
            logger.exception("Price sheet batch %s failed", batch_id)
            self._fail_batch(batch_id, "internal_error", "价目表比价发生内部错误")
            raise

    def _mark_running(self, batch_id: int) -> bool:
        with self._sessions() as db:
            batch = _require_batch(db, batch_id)
            if batch.status in {"completed", "completed_partial", "stopped", "failed", "reviewing"}:
                return False
            if batch.status in {"paused", "waiting_user"}:
                return False
            if batch.stop_requested:
                db.commit()
                self._stop_batch(batch_id)
                return False
            if batch.pause_requested:
                batch.status = "paused"
                batch.updated_at = datetime.now(UTC)
                db.commit()
                return False
            batch.status = "running"
            batch.started_at = batch.started_at or datetime.now(UTC)
            batch.finished_at = None
            batch.updated_at = datetime.now(UTC)
            db.commit()
            return True

    def _queued_item_ids(self, batch_id: int) -> list[int]:
        with self._sessions() as db:
            return list(db.scalars(
                select(PriceSheetItem.id).where(
                    PriceSheetItem.batch_id == batch_id,
                    PriceSheetItem.selected.is_(True),
                    PriceSheetItem.status.in_({"queued", "running"}),
                ).order_by(PriceSheetItem.sequence)
            ))

    def _execute_item(self, batch_id: int, item_id: int, gateway: BrowserGateway) -> bool:
        with self._sessions() as db:
            item = _require_item(db, item_id)
            batch = _require_batch(db, batch_id)
            if item.batch_id != batch_id:
                return True
            item.status = "running"
            item.started_at = item.started_at or datetime.now(UTC)
            item.finished_at = None
            batch.current_item_id = item.id
            batch.updated_at = datetime.now(UTC)
            target = PriceSheetTarget(item.brand, item.model_name, item.storage, item.color)
            stored_json = item.candidates_json
            db.commit()

        if stored_json is not None:
            candidates = [_candidate_from_json(row) for row in json.loads(stored_json)]
        else:
            try:
                discovered = self._call_with_retry(lambda: gateway.discover(target.query, 50))
            except GatewayFailure as exc:
                if exc.code != "empty_result":
                    raise
                discovered = []
            candidates = select_price_sheet_candidates(target, discovered, limit=20)

        with self._sessions() as db:
            item = _require_item(db, item_id)
            if item.candidates_json is None:
                item.candidate_count = len(candidates)
                item.candidates_json = json.dumps(
                    [asdict(candidate) for candidate in candidates], ensure_ascii=False, separators=(",", ":")
                )
            self._ensure_checkout_tasks(db, item, candidates)
            db.commit()

        if not candidates:
            self._complete_empty_item(batch_id, item_id)
            return True

        candidates_by_sku = {candidate.platform_sku_id: candidate for candidate in candidates}
        task_ids = self._queued_task_ids(item_id)
        for position, task_id in enumerate(task_ids, start=1):
            if not self._may_continue(batch_id):
                return False
            if not self._execute_checkout_task(batch_id, item_id, task_id, candidates_by_sku, gateway):
                return False
            if position < len(task_ids):
                delay = self._batch_cooldown_seconds if position % self._batch_size == 0 else self._region_delay_seconds
                if delay > 0:
                    self._sleeper(delay)
        self._finish_item(item_id)
        return True

    @staticmethod
    def _ensure_checkout_tasks(
        db: Session,
        item: PriceSheetItem,
        candidates: list[DiscoveredCandidate],
    ) -> None:
        existing = set(db.execute(
            select(PriceSheetCheckoutTask.region_code, PriceSheetCheckoutTask.platform_sku_id)
            .where(PriceSheetCheckoutTask.price_sheet_item_id == item.id)
        ).all())
        for candidate_position, candidate in enumerate(candidates):
            for region in MAINLAND_REGION_TARGETS:
                key = (region.region_code, candidate.platform_sku_id)
                if key in existing:
                    continue
                db.add(PriceSheetCheckoutTask(
                    price_sheet_item_id=item.id,
                    region_code=region.region_code,
                    platform_sku_id=candidate.platform_sku_id,
                    sequence=candidate_position * len(MAINLAND_REGION_TARGETS) + region.sequence,
                    status="queued",
                    entry_mode=None,
                    attempt_count=0,
                    error_code=None,
                    error_summary=None,
                    started_at=None,
                    finished_at=None,
                ))

    def _queued_task_ids(self, item_id: int) -> list[int]:
        with self._sessions() as db:
            return list(db.scalars(
                select(PriceSheetCheckoutTask.id).where(
                    PriceSheetCheckoutTask.price_sheet_item_id == item_id,
                    PriceSheetCheckoutTask.status == "queued",
                ).order_by(PriceSheetCheckoutTask.sequence)
            ))

    def _execute_checkout_task(
        self,
        batch_id: int,
        item_id: int,
        task_id: int,
        candidates_by_sku: dict[str, DiscoveredCandidate],
        gateway: BrowserGateway,
    ) -> bool:
        with self._sessions() as db:
            task = db.get(PriceSheetCheckoutTask, task_id)
            if task is None or task.price_sheet_item_id != item_id or task.status != "queued":
                return True
            task.status = "running"
            task.attempt_count += 1
            task.started_at = datetime.now(UTC)
            task.finished_at = None
            task.error_code = None
            task.error_summary = None
            sku = task.platform_sku_id
            region = get_region_target(task.region_code)
            db.commit()

        candidate = candidates_by_sku.get(sku)
        if candidate is None:
            return self._handle_task_failure(
                batch_id, item_id, task_id, GatewayFailure("invalid_output", "候选快照缺少当前 SKU")
            )
        checkout_preview = getattr(gateway, "checkout_preview", None)
        if not callable(checkout_preview):
            return self._handle_task_failure(
                batch_id, item_id, task_id, GatewayFailure("tool_unavailable", "结算页核价命令不可用")
            )

        try:
            preview = self._call_with_retry(lambda: checkout_preview(candidate, region, True))
            _validate_preview(preview, sku)
        except GatewayFailure as exc:
            if exc.code in UNAVAILABLE_CODES:
                preview = _unavailable_preview(candidate, exc.code)
            else:
                return self._handle_task_failure(batch_id, item_id, task_id, exc)

        with self._sessions() as db:
            task = db.get(PriceSheetCheckoutTask, task_id)
            if task is None:
                raise ValueError("价目表结算任务不存在")
            _save_checkout_result(db, task, preview)
            task.entry_mode = preview.entry_mode
            task.status = "skipped" if preview.price_status == "unavailable" else "completed"
            task.error_code = preview.unavailable_code
            task.error_summary = None
            task.finished_at = datetime.now(UTC)
            db.commit()
        self._refresh_item_counts(item_id)
        return True

    def _handle_task_failure(
        self,
        batch_id: int,
        item_id: int,
        task_id: int,
        failure: GatewayFailure,
    ) -> bool:
        with self._sessions() as db:
            batch = _require_batch(db, batch_id)
            item = _require_item(db, item_id)
            task = db.get(PriceSheetCheckoutTask, task_id)
            if task is None:
                raise ValueError("价目表结算任务不存在")
            now = datetime.now(UTC)
            region = get_region_target(task.region_code)
            message = failure.safe_message
            if failure.code == "cart_isolation_failed":
                message = "购物车未能自动恢复，请先人工检查购物车后再继续"
            summary = f"{_address(region)}：{message}"[:300]
            task.error_code = failure.code
            task.error_summary = summary
            item.last_error_code = failure.code
            item.last_error_summary = summary
            batch.last_error_code = failure.code
            batch.last_error_summary = summary
            batch.updated_at = now
            if failure.code in WAITING_CODES:
                task.status = "queued"
                task.started_at = None
                item.status = "waiting_user"
                batch.status = "waiting_user"
                db.commit()
                self._refresh_item_counts(item_id)
                return False
            task.status = "failed"
            task.finished_at = now
            if failure.code in RUN_FAILURE_CODES:
                item.status = "failed"
                item.finished_at = now
                batch.status = "failed"
                batch.current_item_id = None
                batch.finished_at = now
                db.commit()
                self._refresh_item_counts(item_id)
                return False
            db.commit()
        self._refresh_item_counts(item_id)
        return True

    def _refresh_item_counts(self, item_id: int) -> None:
        with self._sessions() as db:
            item = _require_item(db, item_id)
            item.completed_region_count = db.scalar(
                select(func.count(func.distinct(PriceSheetCheckoutTask.region_code)))
                .join(
                    PriceSheetCheckoutResult,
                    PriceSheetCheckoutResult.checkout_task_id == PriceSheetCheckoutTask.id,
                )
                .where(
                    PriceSheetCheckoutTask.price_sheet_item_id == item_id,
                    PriceSheetCheckoutResult.price_status == "verified",
                    PriceSheetCheckoutResult.payable_price_cents.is_not(None),
                )
            ) or 0
            item.failed_region_count = db.scalar(
                select(func.count(PriceSheetCheckoutTask.id)).where(
                    PriceSheetCheckoutTask.price_sheet_item_id == item_id,
                    PriceSheetCheckoutTask.status == "failed",
                )
            ) or 0
            item.lowest_price_cents = db.scalar(
                select(func.min(PriceSheetCheckoutResult.payable_price_cents))
                .join(PriceSheetCheckoutTask, PriceSheetCheckoutTask.id == PriceSheetCheckoutResult.checkout_task_id)
                .where(
                    PriceSheetCheckoutTask.price_sheet_item_id == item_id,
                    PriceSheetCheckoutResult.price_status == "verified",
                )
            )
            db.commit()

    def _finish_item(self, item_id: int) -> None:
        self._refresh_item_counts(item_id)
        with self._sessions() as db:
            item = _require_item(db, item_id)
            if item.status == "waiting_user":
                return
            non_terminal = db.scalar(
                select(func.count(PriceSheetCheckoutTask.id)).where(
                    PriceSheetCheckoutTask.price_sheet_item_id == item_id,
                    PriceSheetCheckoutTask.status.not_in(TERMINAL_TASK_STATUSES),
                )
            ) or 0
            if non_terminal:
                item.status = "queued"
                db.commit()
                return
            item.status = "completed" if item.completed_region_count == len(MAINLAND_REGION_TARGETS) else "partial"
            item.finished_at = datetime.now(UTC)
            db.commit()

    def _complete_empty_item(self, batch_id: int, item_id: int) -> None:
        with self._sessions() as db:
            item = _require_item(db, item_id)
            item.status = "completed"
            item.completed_region_count = 0
            item.lowest_price_cents = None
            item.finished_at = datetime.now(UTC)
            batch = _require_batch(db, batch_id)
            batch.current_item_id = None
            batch.updated_at = item.finished_at
            db.commit()

    def _may_continue(self, batch_id: int) -> bool:
        with self._sessions() as db:
            batch = _require_batch(db, batch_id)
            should_stop = batch.stop_requested
            should_pause = batch.pause_requested
            running = batch.status == "running"
        if should_stop:
            self._stop_batch(batch_id)
            return False
        if should_pause:
            with self._sessions() as db:
                batch = _require_batch(db, batch_id)
                running_tasks = db.scalars(
                    select(PriceSheetCheckoutTask)
                    .join(PriceSheetItem, PriceSheetItem.id == PriceSheetCheckoutTask.price_sheet_item_id)
                    .where(
                        PriceSheetItem.batch_id == batch_id,
                        PriceSheetCheckoutTask.status == "running",
                    )
                ).all()
                for task in running_tasks:
                    task.status = "queued"
                    task.started_at = None
                batch.status = "paused"
                batch.current_item_id = None
                batch.updated_at = datetime.now(UTC)
                db.commit()
            return False
        return running

    def _stop_batch(self, batch_id: int) -> None:
        with self._sessions() as db:
            batch = _require_batch(db, batch_id)
            items = db.scalars(select(PriceSheetItem).where(PriceSheetItem.batch_id == batch_id)).all()
            item_ids = [item.id for item in items]
            now = datetime.now(UTC)
            if item_ids:
                tasks = db.scalars(select(PriceSheetCheckoutTask).where(
                    PriceSheetCheckoutTask.price_sheet_item_id.in_(item_ids),
                    PriceSheetCheckoutTask.status.in_({"queued", "running"}),
                )).all()
                for task in tasks:
                    task.status = "skipped"
                    task.finished_at = now
            for item in items:
                if item.status not in {"completed", "skipped"}:
                    item.status = "partial"
                    item.finished_at = now
            batch.status = "stopped"
            batch.current_item_id = None
            batch.finished_at = now
            batch.updated_at = now
            db.commit()

    def _finish_batch(self, batch_id: int) -> None:
        with self._sessions() as db:
            batch = _require_batch(db, batch_id)
            if batch.status != "running":
                return
            items = db.scalars(select(PriceSheetItem).where(
                PriceSheetItem.batch_id == batch_id,
                PriceSheetItem.selected.is_(True),
            )).all()
            batch.completed_item_count = sum(item.status == "completed" for item in items)
            batch.partial_item_count = sum(item.status == "partial" for item in items)
            batch.failed_item_count = sum(item.status == "failed" for item in items)
            batch.lower_price_count = sum(
                item.status == "completed"
                and item.lowest_price_cents is not None
                and item.lowest_price_cents < item.today_price_cents
                for item in items
            )
            batch.status = "completed" if batch.completed_item_count == len(items) else "completed_partial"
            batch.current_item_id = None
            batch.finished_at = datetime.now(UTC)
            batch.updated_at = batch.finished_at
            db.commit()

    def _handle_batch_failure(self, batch_id: int, failure: GatewayFailure) -> None:
        if failure.code in WAITING_CODES:
            with self._sessions() as db:
                batch = _require_batch(db, batch_id)
                batch.status = "waiting_user"
                batch.last_error_code = failure.code
                batch.last_error_summary = failure.safe_message
                batch.updated_at = datetime.now(UTC)
                if batch.current_item_id is not None:
                    item = db.get(PriceSheetItem, batch.current_item_id)
                    if item is not None:
                        item.status = "waiting_user"
                        item.last_error_code = failure.code
                        item.last_error_summary = failure.safe_message
                db.commit()
            return
        self._fail_batch(batch_id, failure.code, failure.safe_message)

    def _fail_batch(self, batch_id: int, code: str, summary: str) -> None:
        with self._sessions() as db:
            batch = _require_batch(db, batch_id)
            now = datetime.now(UTC)
            batch.status = "failed"
            batch.current_item_id = None
            batch.last_error_code = code
            batch.last_error_summary = summary[:300]
            batch.finished_at = now
            batch.updated_at = now
            db.commit()

    def _call_with_retry[T](self, operation: Callable[[], T]) -> T:
        for attempt in range(len(self._retry_delays) + 1):
            try:
                return operation()
            except GatewayFailure as exc:
                if exc.code not in RETRYABLE_CODES or attempt == len(self._retry_delays):
                    raise
                delay = self._retry_delays[attempt]
                if delay > 0:
                    self._sleeper(delay)
        raise AssertionError("重试循环必须返回或抛出异常")


def _validate_preview(preview: CheckoutPreview, expected_sku: str) -> None:
    if preview.platform_sku_id != expected_sku:
        raise GatewayFailure("invalid_output", "结算结果 SKU 与任务不一致")
    if preview.price_status in {"verified", "conditional"}:
        if (
            preview.quantity != 1
            or not preview.target_only
            or not preview.region_confirmed
            or preview.payable_price_cents is None
            or preview.payable_price_cents <= 0
        ):
            raise GatewayFailure("invalid_output", "结算结果未能确认 SKU、地区、数量和应付金额")
    if preview.price_status == "verified" and preview.conditional_reason:
        raise GatewayFailure("invalid_output", "无条件价格包含资格限制")
    if preview.entry_mode == "cart_fallback" and not preview.cart_restored:
        raise GatewayFailure("cart_isolation_failed", "购物车未恢复")


def _save_checkout_result(db: Session, task: PriceSheetCheckoutTask, preview: CheckoutPreview) -> None:
    result = db.scalar(select(PriceSheetCheckoutResult).where(
        PriceSheetCheckoutResult.checkout_task_id == task.id
    ))
    if result is None:
        result = PriceSheetCheckoutResult(checkout_task_id=task.id)
        db.add(result)
    result.title = preview.title
    result.product_url = preview.product_url
    result.shop_name = preview.shop_name
    result.shop_type = preview.shop_type
    result.quantity = preview.quantity
    result.target_only = preview.target_only
    result.line_original_price_cents = preview.line_original_price_cents
    result.line_sale_price_cents = preview.line_sale_price_cents
    result.merchant_discount_cents = preview.merchant_discount_cents
    result.ordinary_coupon_cents = preview.ordinary_coupon_cents
    result.subsidy_amount_cents = preview.subsidy_amount_cents
    result.shipping_fee_cents = preview.shipping_fee_cents
    result.payable_price_cents = preview.payable_price_cents
    result.discount_summary = preview.discount_summary
    result.conditional_reason = preview.conditional_reason
    result.unavailable_code = preview.unavailable_code
    result.price_status = preview.price_status
    result.region_confirmed = preview.region_confirmed
    result.cart_restored = preview.cart_restored
    result.captured_at = preview.captured_at


def _unavailable_preview(candidate: DiscoveredCandidate, code: str) -> CheckoutPreview:
    return CheckoutPreview(
        platform_sku_id=candidate.platform_sku_id,
        title=candidate.title,
        product_url=candidate.product_url,
        shop_name=candidate.shop_name,
        shop_type=candidate.shop_type,
        entry_mode="buy_now",
        price_status="unavailable",
        quantity=0,
        target_only=False,
        line_original_price_cents=None,
        line_sale_price_cents=None,
        merchant_discount_cents=0,
        ordinary_coupon_cents=0,
        subsidy_amount_cents=0,
        shipping_fee_cents=0,
        payable_price_cents=None,
        discount_summary="",
        conditional_reason=None,
        unavailable_code=code,
        region_confirmed=False,
        cart_restored=True,
        captured_at=datetime.now(UTC),
    )


def _candidate_from_json(row: dict[str, object]) -> DiscoveredCandidate:
    return DiscoveredCandidate(**row)  # type: ignore[arg-type]


def _require_batch(db: Session, batch_id: int) -> PriceSheetBatch:
    batch = db.get(PriceSheetBatch, batch_id)
    if batch is None:
        raise ValueError("价目表批次不存在")
    return batch


def _require_item(db: Session, item_id: int) -> PriceSheetItem:
    item = db.get(PriceSheetItem, item_id)
    if item is None:
        raise ValueError("价目表条目不存在")
    return item


def _address(region: RegionTarget) -> str:
    parts: list[str] = []
    for part in (region.province, region.city, region.district, region.street):
        if not parts or part != parts[-1]:
            parts.append(part)
    return " / ".join(parts)
