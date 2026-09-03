from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.automation.candidates import build_search_query, select_candidates
from app.automation.contracts import (
    BrowserGateway,
    DiscoveredCandidate,
    GatewayFailure,
    RegionBatchGateway,
    VerifiedOffer,
)
from app.automation.regions import RegionTarget
from app.automation.run_service import refresh_run_counts, require_run
from app.db.models.automation import CollectionCandidate, CollectionRegionTask
from app.db.models.offers import SearchSession
from app.schemas.offers import RawOffer
from app.services.offer_ingestion import ingest_verified_browser_offer, load_match_target
from app.services.offer_retention import retain_region_top_offers


WAITING_CODES = {"captcha", "login_required", "rate_limited"}
RETRYABLE_CODES = {"network_error"}
TASK_FAILURE_CODES = {"page_changed", "unsupported_region", "invalid_output", "empty_result"}
RUN_FAILURE_CODES = {"tool_unavailable"}


logger = logging.getLogger(__name__)


class CollectionExecutor:
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

    def execute(self, run_id: int) -> None:
        if not self._mark_running(run_id):
            return
        gateway = self._gateway_factory()
        try:
            candidates, query = self._load_or_discover_candidates(run_id, gateway)
            if not candidates:
                self._fail_run(run_id, "empty_result", "没有找到可比较的候选商品")
                return

            task_ids = self._queued_task_ids(run_id)
            for position, task_id in enumerate(task_ids, start=1):
                if not self._may_continue(run_id):
                    return
                if not self._execute_region(run_id, task_id, query, candidates, gateway):
                    return
                if position < len(task_ids):
                    delay = (
                        self._batch_cooldown_seconds
                        if position % self._batch_size == 0
                        else self._region_delay_seconds
                    )
                    if delay > 0:
                        self._sleeper(delay)
            self._finish_run(run_id)
        except GatewayFailure as exc:
            self._handle_run_gateway_failure(run_id, exc)
        except Exception:
            logger.exception("Automatic collection run %s failed", run_id)
            self._fail_run(run_id, "internal_error", "自动采集发生内部错误")
            raise

    def _mark_running(self, run_id: int) -> bool:
        with self._sessions() as db:
            run = require_run(db, run_id)
            if run.status in {"completed", "completed_partial", "stopped", "failed"}:
                return False
            if run.status in {"paused", "waiting_user"}:
                return False
            if run.stop_requested:
                db.commit()
                self._stop_run(run_id)
                return False
            if run.pause_requested:
                run.status = "paused"
                run.updated_at = datetime.now(UTC)
                db.commit()
                return False
            run.status = "running"
            run.started_at = run.started_at or datetime.now(UTC)
            run.finished_at = None
            run.updated_at = datetime.now(UTC)
            db.commit()
            return True

    def _load_or_discover_candidates(
        self,
        run_id: int,
        gateway: BrowserGateway,
    ) -> tuple[list[DiscoveredCandidate], str]:
        with self._sessions() as db:
            run = require_run(db, run_id)
            search = db.get(SearchSession, run.search_session_id)
            if search is None:
                raise ValueError("搜索会话不存在")
            target = load_match_target(db, search.variant_id)
            query = build_search_query(target)
            stored = db.scalars(
                select(CollectionCandidate)
                .where(CollectionCandidate.collection_run_id == run_id)
                .order_by(CollectionCandidate.sequence)
            ).all()
            if stored:
                return [_stored_candidate(row) for row in stored], query

        discovered = self._call_with_retry(lambda: gateway.discover(query, 30))
        selection = select_candidates(discovered, target, limit=15)
        with self._sessions() as db:
            run = require_run(db, run_id)
            run.candidate_count = selection.discovered_count
            run.selected_candidate_count = len(selection.selected)
            run.stage = "verifying"
            run.updated_at = datetime.now(UTC)
            db.add_all(
                CollectionCandidate(
                    collection_run_id=run_id,
                    sequence=sequence,
                    platform_sku_id=item.platform_sku_id,
                    title=item.title,
                    product_url=item.product_url,
                    platform_shop_id=item.platform_shop_id,
                    shop_name=item.shop_name,
                    shop_type=item.shop_type,
                    initial_price_cents=item.initial_price_cents,
                    match_score=item.match_score,
                )
                for sequence, item in enumerate(selection.selected, start=1)
            )
            db.commit()
        return [
            DiscoveredCandidate(
                platform_sku_id=item.platform_sku_id,
                title=item.title,
                product_url=item.product_url,
                shop_name=item.shop_name,
                platform_shop_id=item.platform_shop_id,
                shop_type=item.shop_type,
                initial_price_cents=item.initial_price_cents,
            )
            for item in selection.selected
        ], query

    def _queued_task_ids(self, run_id: int) -> list[int]:
        with self._sessions() as db:
            return list(
                db.scalars(
                    select(CollectionRegionTask.id)
                    .where(
                        CollectionRegionTask.collection_run_id == run_id,
                        CollectionRegionTask.status == "queued",
                    )
                    .order_by(CollectionRegionTask.sequence)
                )
            )

    def _execute_region(
        self,
        run_id: int,
        task_id: int,
        query: str,
        candidates: list[DiscoveredCandidate],
        gateway: BrowserGateway,
    ) -> bool:
        with self._sessions() as db:
            task = db.get(CollectionRegionTask, task_id)
            if task is None or task.collection_run_id != run_id or task.status != "queued":
                return True
            run = require_run(db, run_id)
            task.status = "running"
            task.attempts += 1
            task.started_at = datetime.now(UTC)
            task.finished_at = None
            task.error_code = None
            task.error_summary = None
            run.status = "running"
            run.stage = "verifying"
            run.current_region_code = task.region_code
            run.updated_at = datetime.now(UTC)
            region = RegionTarget(
                region_code=task.region_code,
                province=task.province,
                city=task.city,
                district=task.district,
                sequence=task.sequence,
            )
            db.commit()

        if isinstance(gateway, RegionBatchGateway):
            try:
                verified_offers = self._call_with_retry(
                    lambda: gateway.verify_region(query, candidates, region)
                )
            except GatewayFailure as exc:
                return self._handle_task_gateway_failure(run_id, task_id, exc)

            for verified in verified_offers:
                self._record_verified_offer(run_id, task_id, verified, region, gateway.adapter_version)
                if not self._may_continue(run_id, current_task_id=task_id):
                    return False
        else:
            for candidate in candidates:
                try:
                    verified = self._call_with_retry(lambda: gateway.verify(candidate, region))
                except GatewayFailure as exc:
                    return self._handle_task_gateway_failure(run_id, task_id, exc)

                self._record_verified_offer(run_id, task_id, verified, region, gateway.adapter_version)
                if not self._may_continue(run_id, current_task_id=task_id):
                    return False

        with self._sessions() as db:
            task = db.get(CollectionRegionTask, task_id)
            run = require_run(db, run_id)
            if task is None:
                raise ValueError("地区采集任务不存在")
            retain_region_top_offers(
                db,
                run.search_session_id,
                "jd",
                region.region_code,
                limit=10,
            )
            task.status = "completed"
            task.finished_at = datetime.now(UTC)
            run.current_region_code = None
            run.updated_at = datetime.now(UTC)
            refresh_run_counts(db, run_id)
            db.commit()
        return True

    def _record_verified_offer(
        self,
        run_id: int,
        task_id: int,
        verified: VerifiedOffer,
        region: RegionTarget,
        adapter_version: str,
    ) -> None:
        accepted_count = 0
        if not _is_out_of_stock(verified.stock_status):
            with self._sessions() as db:
                summary = ingest_verified_browser_offer(
                    db,
                    self._search_session_id(db, run_id),
                    _raw_offer(verified, region),
                    adapter_version=adapter_version,
                )
                accepted_count = summary.accepted_count
        self._record_verified_candidate(task_id, accepted_count)

    def _record_verified_candidate(self, task_id: int, accepted_count: int) -> None:
        with self._sessions() as db:
            task = db.get(CollectionRegionTask, task_id)
            if task is None:
                raise ValueError("地区采集任务不存在")
            task.verified_candidate_count += 1
            task.accepted_offer_count += accepted_count
            db.commit()

    def _may_continue(self, run_id: int, current_task_id: int | None = None) -> bool:
        with self._sessions() as db:
            run = require_run(db, run_id)
            should_stop = run.stop_requested
            should_pause = run.pause_requested
            is_running = run.status == "running"
        if should_stop:
            self._stop_run(run_id)
            return False
        if should_pause:
            self._pause_run(run_id, current_task_id)
            return False
        return is_running

    def _pause_run(self, run_id: int, current_task_id: int | None) -> None:
        with self._sessions() as db:
            run = require_run(db, run_id)
            if current_task_id is not None:
                task = db.get(CollectionRegionTask, current_task_id)
                if task is not None and task.status == "running":
                    task.status = "queued"
                    task.started_at = None
            run.status = "paused"
            run.current_region_code = None
            run.updated_at = datetime.now(UTC)
            db.commit()

    def _stop_run(self, run_id: int) -> None:
        with self._sessions() as db:
            run = require_run(db, run_id)
            now = datetime.now(UTC)
            unfinished = db.scalars(
                select(CollectionRegionTask).where(
                    CollectionRegionTask.collection_run_id == run_id,
                    CollectionRegionTask.status.in_({"queued", "running", "waiting_user"}),
                )
            ).all()
            for task in unfinished:
                task.status = "skipped"
                task.finished_at = now
            run.status = "stopped"
            run.current_region_code = None
            run.finished_at = now
            run.updated_at = now
            refresh_run_counts(db, run_id)
            db.commit()

    def _handle_task_gateway_failure(
        self,
        run_id: int,
        task_id: int,
        failure: GatewayFailure,
    ) -> bool:
        with self._sessions() as db:
            run = require_run(db, run_id)
            task = db.get(CollectionRegionTask, task_id)
            if task is None:
                raise ValueError("地区采集任务不存在")
            now = datetime.now(UTC)
            task.error_code = failure.code
            task.error_summary = failure.safe_message
            run.last_error_code = failure.code
            run.last_error_summary = failure.safe_message
            run.updated_at = now
            if failure.code in WAITING_CODES:
                task.status = "waiting_user"
                run.status = "waiting_user"
                db.commit()
                return False
            task.status = "failed"
            task.finished_at = now
            run.current_region_code = None
            if failure.code in RUN_FAILURE_CODES:
                run.status = "failed"
                run.finished_at = now
                refresh_run_counts(db, run_id)
                db.commit()
                return False
            refresh_run_counts(db, run_id)
            db.commit()
            return True

    def _handle_run_gateway_failure(self, run_id: int, failure: GatewayFailure) -> None:
        if failure.code in WAITING_CODES:
            with self._sessions() as db:
                run = require_run(db, run_id)
                run.status = "waiting_user"
                run.last_error_code = failure.code
                run.last_error_summary = failure.safe_message
                run.updated_at = datetime.now(UTC)
                db.commit()
            return
        self._fail_run(run_id, failure.code, failure.safe_message)

    def _fail_run(self, run_id: int, code: str, summary: str) -> None:
        with self._sessions() as db:
            run = require_run(db, run_id)
            now = datetime.now(UTC)
            run.status = "failed"
            run.current_region_code = None
            run.last_error_code = code
            run.last_error_summary = summary[:300]
            run.finished_at = now
            run.updated_at = now
            db.commit()

    def _finish_run(self, run_id: int) -> None:
        with self._sessions() as db:
            run = require_run(db, run_id)
            if run.status != "running":
                return
            refresh_run_counts(db, run_id)
            run.status = "completed_partial" if run.failed_region_count else "completed"
            run.stage = "completed"
            run.current_region_code = None
            run.finished_at = datetime.now(UTC)
            run.updated_at = run.finished_at
            db.commit()

    def _search_session_id(self, db: Session, run_id: int) -> int:
        return require_run(db, run_id).search_session_id

    def _call_with_retry[T](self, operation: Callable[[], T]) -> T:
        for attempt in range(len(self._retry_delays) + 1):
            try:
                return operation()
            except GatewayFailure as exc:
                if exc.code not in RETRYABLE_CODES or attempt == len(self._retry_delays):
                    raise
                delay = self._retry_delays[attempt]
                if delay > 0:
                    time.sleep(delay)
        raise AssertionError("重试循环必须返回或抛出异常")


def _stored_candidate(row: CollectionCandidate) -> DiscoveredCandidate:
    return DiscoveredCandidate(
        platform_sku_id=row.platform_sku_id,
        title=row.title,
        product_url=row.product_url,
        shop_name=row.shop_name,
        platform_shop_id=row.platform_shop_id,
        shop_type=row.shop_type,  # type: ignore[arg-type]
        initial_price_cents=row.initial_price_cents,
    )


def _raw_offer(verified: VerifiedOffer, region: RegionTarget) -> RawOffer:
    return RawOffer(
        title=verified.title,
        platform="jd",
        listed_price_cents=verified.listed_price_cents,
        sale_price_cents=verified.sale_price_cents,
        platform_product_id=verified.platform_sku_id,
        platform_sku_id=verified.platform_sku_id,
        platform_shop_id=verified.platform_shop_id,
        shop_name=verified.shop_name,
        shop_type=verified.shop_type,
        product_url=verified.product_url,
        region_code=region.region_code,
        region_name=region.province,
        merchant_discount_cents=verified.merchant_discount_cents,
        platform_coupon_cents=verified.platform_coupon_cents,
        member_discount_cents=verified.member_discount_cents,
        payment_discount_cents=verified.payment_discount_cents,
        subsidy_amount_cents=verified.subsidy_amount_cents,
        subsidy_status=verified.subsidy_status,
        shipping_fee_cents=verified.shipping_fee_cents,
        installation_fee_cents=verified.installation_fee_cents,
        conditional_price_cents=verified.conditional_price_cents,
        stock_status=verified.stock_status,
        captured_at=verified.captured_at,
    )


def _is_out_of_stock(stock_status: str) -> bool:
    return stock_status.strip().casefold() in {"out_of_stock", "sold_out", "缺货", "无货"}
