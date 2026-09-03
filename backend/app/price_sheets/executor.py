from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.automation.contracts import (
    BrowserGateway,
    DiscoveredCandidate,
    GatewayFailure,
    RegionBatchGateway,
    VerifiedOffer,
)
from app.automation.regions import RegionTarget
from app.db.models.price_sheets import (
    PriceSheetBatch,
    PriceSheetItem,
    PriceSheetRegionResult,
    PriceSheetRegionTask,
)
from app.price_sheets.matching import PriceSheetTarget, select_price_sheet_candidates
from app.price_sheets.pricing import calculate_price_sheet_offer


WAITING_CODES = {"captcha", "login_required", "rate_limited"}
RETRYABLE_CODES = {"network_error"}
RUN_FAILURE_CODES = {"tool_unavailable"}
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
            item = db.get(PriceSheetItem, item_id)
            batch = _require_batch(db, batch_id)
            if item is None or item.batch_id != batch_id:
                return True
            item.status = "running"
            item.started_at = item.started_at or datetime.now(UTC)
            item.finished_at = None
            batch.current_item_id = item.id
            batch.updated_at = datetime.now(UTC)
            target = PriceSheetTarget(item.brand, item.model_name, item.storage, item.color)
            stored_json = item.candidates_json
            db.commit()

        if stored_json:
            candidates = [_candidate_from_json(row) for row in json.loads(stored_json)]
        else:
            try:
                discovered = self._call_with_retry(lambda: gateway.discover(target.query, 30))
            except GatewayFailure as exc:
                if exc.code != "empty_result":
                    raise
                discovered = []
            candidates = select_price_sheet_candidates(target, discovered, limit=15)
            with self._sessions() as db:
                item = _require_item(db, item_id)
                item.candidate_count = len(candidates)
                item.candidates_json = json.dumps(
                    [asdict(candidate) for candidate in candidates], ensure_ascii=False, separators=(",", ":")
                )
                db.commit()

        if not candidates:
            self._complete_empty_item(batch_id, item_id)
            return True

        task_ids = self._queued_task_ids(item_id)
        for position, task_id in enumerate(task_ids, start=1):
            if not self._may_continue(batch_id):
                return False
            if not self._execute_region(batch_id, item_id, task_id, target, candidates, gateway):
                return False
            if position < len(task_ids):
                delay = self._batch_cooldown_seconds if position % self._batch_size == 0 else self._region_delay_seconds
                if delay > 0:
                    self._sleeper(delay)
        self._finish_item(item_id)
        return True

    def _queued_task_ids(self, item_id: int) -> list[int]:
        with self._sessions() as db:
            return list(db.scalars(
                select(PriceSheetRegionTask.id).where(
                    PriceSheetRegionTask.price_sheet_item_id == item_id,
                    PriceSheetRegionTask.status == "queued",
                ).order_by(PriceSheetRegionTask.sequence)
            ))

    def _execute_region(
        self,
        batch_id: int,
        item_id: int,
        task_id: int,
        target: PriceSheetTarget,
        candidates: list[DiscoveredCandidate],
        gateway: BrowserGateway,
    ) -> bool:
        with self._sessions() as db:
            task = db.get(PriceSheetRegionTask, task_id)
            if task is None or task.price_sheet_item_id != item_id or task.status != "queued":
                return True
            task.status = "running"
            task.attempts += 1
            task.started_at = datetime.now(UTC)
            task.finished_at = None
            task.error_code = None
            task.error_summary = None
            region = RegionTarget(
                task.region_code, task.province, task.city, task.district, task.street, task.sequence,
            )
            db.commit()

        try:
            if isinstance(gateway, RegionBatchGateway):
                verified = self._call_with_retry(
                    lambda: gateway.verify_region(target.query, candidates, region)
                )
            else:
                verified = [
                    self._call_with_retry(lambda candidate=candidate: gateway.verify(candidate, region))
                    for candidate in candidates
                ]
        except GatewayFailure as exc:
            if exc.code == "empty_result":
                verified = []
            else:
                return self._handle_task_failure(batch_id, item_id, task_id, exc)

        accepted: list[tuple[int, str, VerifiedOffer, object]] = []
        for offer in verified:
            if _out_of_stock(offer.stock_status) or not _offer_matches(target, offer):
                continue
            try:
                calculated = calculate_price_sheet_offer(offer)
            except ValueError:
                continue
            accepted.append((calculated.trusted_price_cents, offer.platform_sku_id, offer, calculated))
        accepted.sort(key=lambda row: (row[0], row[1]))

        with self._sessions() as db:
            task = db.get(PriceSheetRegionTask, task_id)
            if task is None:
                raise ValueError("价目表地区任务不存在")
            if accepted:
                _save_region_result(db, item_id, region, accepted[0][2], accepted[0][3])
                task.lowest_result_cents = accepted[0][0]
            task.verified_candidate_count = len(verified)
            task.status = "completed"
            task.finished_at = datetime.now(UTC)
            db.commit()
        self._refresh_item_counts(item_id)
        return True

    def _handle_task_failure(
        self, batch_id: int, item_id: int, task_id: int, failure: GatewayFailure,
    ) -> bool:
        with self._sessions() as db:
            batch = _require_batch(db, batch_id)
            item = _require_item(db, item_id)
            task = db.get(PriceSheetRegionTask, task_id)
            if task is None:
                raise ValueError("价目表地区任务不存在")
            now = datetime.now(UTC)
            address = _address(task.province, task.city, task.district, task.street)
            summary = f"{address}：{failure.safe_message}"[:300]
            task.error_code = failure.code
            task.error_summary = summary
            item.last_error_code = failure.code
            item.last_error_summary = summary
            batch.last_error_code = failure.code
            batch.last_error_summary = summary
            batch.updated_at = now
            if failure.code in WAITING_CODES:
                task.status = "waiting_user"
                item.status = "waiting_user"
                batch.status = "waiting_user"
                db.commit()
                self._refresh_item_counts(item_id)
                return False
            task.status = "failed"
            task.finished_at = now
            if failure.code in RUN_FAILURE_CODES:
                item.status = "failed"
                batch.status = "failed"
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
            counts = dict(db.execute(
                select(PriceSheetRegionTask.status, func.count(PriceSheetRegionTask.id))
                .where(PriceSheetRegionTask.price_sheet_item_id == item_id)
                .group_by(PriceSheetRegionTask.status)
            ).all())
            item.completed_region_count = counts.get("completed", 0)
            item.failed_region_count = counts.get("failed", 0)
            item.lowest_price_cents = db.scalar(select(func.min(PriceSheetRegionResult.trusted_price_cents)).where(
                PriceSheetRegionResult.price_sheet_item_id == item_id
            ))
            db.commit()

    def _finish_item(self, item_id: int) -> None:
        self._refresh_item_counts(item_id)
        with self._sessions() as db:
            item = _require_item(db, item_id)
            if item.status == "waiting_user":
                return
            item.status = "completed" if item.completed_region_count == item.total_region_count else "partial"
            item.finished_at = datetime.now(UTC)
            db.commit()

    def _complete_empty_item(self, batch_id: int, item_id: int) -> None:
        with self._sessions() as db:
            tasks = db.scalars(select(PriceSheetRegionTask).where(
                PriceSheetRegionTask.price_sheet_item_id == item_id,
                PriceSheetRegionTask.status == "queued",
            )).all()
            now = datetime.now(UTC)
            for task in tasks:
                task.status = "completed"
                task.finished_at = now
            item = _require_item(db, item_id)
            item.status = "completed"
            item.completed_region_count = item.total_region_count
            item.finished_at = now
            batch = _require_batch(db, batch_id)
            batch.current_item_id = None
            batch.updated_at = now
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
                running_tasks = db.scalars(select(PriceSheetRegionTask).join(
                    PriceSheetItem, PriceSheetItem.id == PriceSheetRegionTask.price_sheet_item_id,
                ).where(
                    PriceSheetItem.batch_id == batch_id,
                    PriceSheetRegionTask.status == "running",
                )).all()
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
                tasks = db.scalars(select(PriceSheetRegionTask).where(
                    PriceSheetRegionTask.price_sheet_item_id.in_(item_ids),
                    PriceSheetRegionTask.status.in_({"queued", "running", "waiting_user"}),
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
                PriceSheetItem.batch_id == batch_id, PriceSheetItem.selected.is_(True),
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


def _offer_matches(target: PriceSheetTarget, offer: VerifiedOffer) -> bool:
    candidate = DiscoveredCandidate(
        offer.platform_sku_id, offer.title, offer.product_url, offer.shop_name,
        offer.platform_shop_id, offer.shop_type, offer.sale_price_cents,
    )
    return bool(select_price_sheet_candidates(target, [candidate], limit=1))


def _save_region_result(db: Session, item_id: int, region: RegionTarget, offer: VerifiedOffer, calculated) -> None:
    result = db.scalar(select(PriceSheetRegionResult).where(
        PriceSheetRegionResult.price_sheet_item_id == item_id,
        PriceSheetRegionResult.region_code == region.region_code,
    ))
    if result is None:
        result = PriceSheetRegionResult(price_sheet_item_id=item_id, region_code=region.region_code)
        db.add(result)
    result.platform_sku_id = offer.platform_sku_id
    result.title = offer.title
    result.product_url = offer.product_url
    result.shop_name = offer.shop_name
    result.shop_type = offer.shop_type
    result.listed_price_cents = offer.listed_price_cents
    result.sale_price_cents = offer.sale_price_cents
    result.merchant_discount_cents = offer.merchant_discount_cents
    result.platform_coupon_cents = offer.platform_coupon_cents
    result.subsidy_amount_cents = offer.subsidy_amount_cents
    result.shipping_fee_cents = offer.shipping_fee_cents
    result.trusted_price_cents = calculated.trusted_price_cents
    result.sale_price_includes_coupon = offer.sale_price_includes_coupon
    result.sale_price_includes_subsidy = offer.sale_price_includes_subsidy
    result.stock_status = offer.stock_status
    result.captured_at = offer.captured_at


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


def _out_of_stock(value: str) -> bool:
    return value.strip().casefold() in {"out_of_stock", "sold_out", "缺货", "无货"}


def _address(province: str, city: str, district: str, street: str) -> str:
    parts: list[str] = []
    for part in (province, city, district, street):
        if not parts or part != parts[-1]:
            parts.append(part)
    return " / ".join(parts)
