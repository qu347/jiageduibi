from collections.abc import Callable, Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.automation.contracts import CheckoutPreview, DiscoveredCandidate, GatewayFailure
from app.automation.regions import RegionTarget
from app.db.base import Base
from app.db.models.price_sheets import (
    PriceSheetBatch,
    PriceSheetCheckoutResult,
    PriceSheetCheckoutTask,
)
from app.db.session import build_engine, session_factory
from app.price_sheets.contracts import ParsedPriceSheet, ParsedPriceSheetItem
from app.price_sheets.executor import PriceSheetExecutor
from app.price_sheets.service import create_batch, get_batch_detail, recover_interrupted_batches, resume_batch, start_batch


class FakeGateway:
    adapter_version = "fake-jd/checkout-1.0"

    def __init__(self, candidate_count: int = 1) -> None:
        self.candidate_count = candidate_count
        self.discover_calls: list[tuple[str, int]] = []
        self.checkout_calls: list[tuple[str, str]] = []
        self.failure_on_call: dict[int, str] = {}
        self.always_fail: dict[str, str] = {}
        self.status_by_region: dict[str, str] = {}
        self.after_checkout: Callable[[int], None] | None = None

    def discover(self, query: str, limit: int) -> list[DiscoveredCandidate]:
        self.discover_calls.append((query, limit))
        return [self._candidate(index) for index in range(self.candidate_count)][:limit]

    def checkout_preview(
        self,
        candidate: DiscoveredCandidate,
        region: RegionTarget,
        allow_cart_fallback: bool = True,
    ) -> CheckoutPreview:
        assert allow_cart_fallback is True
        self.checkout_calls.append((candidate.platform_sku_id, region.region_code))
        call_number = len(self.checkout_calls)
        if self.after_checkout is not None:
            self.after_checkout(call_number)
        if call_number in self.failure_on_call:
            raise GatewayFailure(self.failure_on_call.pop(call_number), "模拟一次失败")
        if region.region_code in self.always_fail:
            raise GatewayFailure(self.always_fail[region.region_code], "模拟持续失败")
        return self._preview(candidate, self.status_by_region.get(region.region_code, "verified"))

    @staticmethod
    def _candidate(index: int) -> DiscoveredCandidate:
        sku = str(100_000_000_000 + index)
        return DiscoveredCandidate(
            platform_sku_id=sku,
            title="Apple iPhone 17 256GB 黑色 全新国行",
            product_url=f"https://item.jd.com/{sku}.html",
            shop_name="Apple产品京东自营旗舰店",
            platform_shop_id="self",
            shop_type="self_operated",
            initial_price_cents=500_000 + index,
        )

    @staticmethod
    def _preview(candidate: DiscoveredCandidate, status: str) -> CheckoutPreview:
        unavailable = status == "unavailable"
        conditional = status == "conditional"
        return CheckoutPreview(
            platform_sku_id=candidate.platform_sku_id,
            title=candidate.title,
            product_url=candidate.product_url,
            shop_name=candidate.shop_name,
            shop_type=candidate.shop_type,
            entry_mode="buy_now",
            price_status=status,  # type: ignore[arg-type]
            quantity=0 if unavailable else 1,
            target_only=not unavailable,
            line_original_price_cents=None if unavailable else 550_000,
            line_sale_price_cents=None if unavailable else 500_000,
            merchant_discount_cents=0,
            ordinary_coupon_cents=0,
            subsidy_amount_cents=0,
            shipping_fee_cents=0,
            payable_price_cents=None if unavailable else 500_000,
            discount_summary="PLUS会员" if conditional else "",
            conditional_reason="PLUS会员" if conditional else None,
            unavailable_code="price_unavailable" if unavailable else None,
            region_confirmed=not unavailable,
            cart_restored=True,
            captured_at=datetime(2026, 9, 4, tzinfo=UTC),
        )


@pytest.fixture
def database(tmp_path) -> Generator[tuple[sessionmaker[Session], Session], None, None]:
    engine = build_engine(f"sqlite:///{(tmp_path / 'price-sheet-executor.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = session_factory(engine)
    db = factory()
    try:
        yield factory, db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture
def batch_id(database: tuple[sessionmaker[Session], Session]) -> int:
    _factory, db = database
    parsed = ParsedPriceSheet(
        price_date=datetime(2026, 9, 3, tzinfo=UTC).date(),
        date_inferred=False,
        items=[ParsedPriceSheetItem(
            brand="Apple", model_name="iPhone 17", storage="256GB", color="黑色",
            today_price_cents=590_000, raw_text="17-256G 黑5900", confidence=0.98,
            review_required=False,
        )],
        unparsed_lines=[],
    )
    detail = create_batch(db, "sheet.png", parsed)
    start_batch(db, detail.batch.id)
    db.commit()
    return detail.batch.id


def execute(factory: sessionmaker[Session], gateway: FakeGateway, batch_id: int) -> None:
    PriceSheetExecutor(
        factory,
        lambda: gateway,
        retry_delays=(0.0, 0.0),
        region_delay_seconds=0.0,
        batch_cooldown_seconds=0.0,
    ).execute(batch_id)


def test_executor_freezes_twenty_candidates_and_builds_620_unique_tasks(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway(candidate_count=25)
    gateway.failure_on_call[1] = "login_required"

    execute(factory, gateway, batch_id)
    db.expire_all()

    item = get_batch_detail(db, batch_id).items[0]
    tasks = db.scalars(select(PriceSheetCheckoutTask).order_by(PriceSheetCheckoutTask.sequence)).all()
    assert item.candidate_count == 20
    assert len(tasks) == 620
    assert len({(task.price_sheet_item_id, task.region_code, task.platform_sku_id) for task in tasks}) == 620
    assert [task.sequence for task in tasks] == list(range(1, 621))
    assert gateway.discover_calls == [("Apple iPhone 17 256GB 黑色", 50)]

    execute(factory, gateway, batch_id)
    assert gateway.discover_calls == [("Apple iPhone 17 256GB 黑色", 50)]
    assert db.scalar(select(func.count()).select_from(PriceSheetCheckoutTask)) == 620


def test_waiting_task_resumes_without_repeating_completed_combinations_or_search(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway()
    gateway.failure_on_call[8] = "captcha"

    execute(factory, gateway, batch_id)
    db.expire_all()
    assert get_batch_detail(db, batch_id).batch.status == "waiting_user"
    assert db.scalar(select(func.count()).select_from(PriceSheetCheckoutResult)) == 7

    resume_batch(db, batch_id)
    db.commit()
    execute(factory, gateway, batch_id)
    db.expire_all()

    assert gateway.discover_calls == [("Apple iPhone 17 256GB 黑色", 50)]
    assert len(gateway.checkout_calls) == 32
    assert gateway.checkout_calls.count(gateway.checkout_calls[0]) == 1
    assert db.scalar(select(func.count()).select_from(PriceSheetCheckoutResult)) == 31
    assert get_batch_detail(db, batch_id).batch.status == "completed"


def test_executor_persists_verified_conditional_and_unavailable_results(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway()
    gateway.status_by_region.update({"310100": "conditional", "120100": "unavailable"})

    execute(factory, gateway, batch_id)
    db.expire_all()

    counts = dict(db.execute(
        select(PriceSheetCheckoutResult.price_status, func.count(PriceSheetCheckoutResult.id))
        .group_by(PriceSheetCheckoutResult.price_status)
    ).all())
    assert counts == {"conditional": 1, "unavailable": 1, "verified": 29}
    assert get_batch_detail(db, batch_id).items[0].completed_region_count == 29
    skipped = db.scalar(select(PriceSheetCheckoutTask).where(PriceSheetCheckoutTask.region_code == "120100"))
    assert skipped is not None and skipped.status == "skipped"


def test_checkout_business_failure_becomes_unavailable_and_continues(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway()
    gateway.failure_on_call[1] = "checkout_address_required"

    execute(factory, gateway, batch_id)
    first = db.scalar(select(PriceSheetCheckoutTask).order_by(PriceSheetCheckoutTask.sequence))
    assert first is not None and first.status == "skipped"
    result = db.scalar(select(PriceSheetCheckoutResult).where(PriceSheetCheckoutResult.checkout_task_id == first.id))
    assert result is not None and result.unavailable_code == "checkout_address_required"
    assert len(gateway.checkout_calls) == 31


def test_network_failure_retries_twice_then_marks_failed_and_continues(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway()
    gateway.always_fail["540100"] = "network_error"

    execute(factory, gateway, batch_id)

    assert [region for _sku, region in gateway.checkout_calls].count("540100") == 3
    assert any(region == "610100" for _sku, region in gateway.checkout_calls)
    task = db.scalar(select(PriceSheetCheckoutTask).where(PriceSheetCheckoutTask.region_code == "540100"))
    assert task is not None and task.status == "failed"
    assert get_batch_detail(db, batch_id).batch.status == "completed_partial"


@pytest.mark.parametrize("code", ["login_required", "captcha", "rate_limited", "safety_boundary_crossed"])
def test_user_attention_failures_pause_with_current_task_requeued(
    database: tuple[sessionmaker[Session], Session], batch_id: int, code: str,
) -> None:
    factory, db = database
    gateway = FakeGateway()
    gateway.failure_on_call[1] = code

    execute(factory, gateway, batch_id)

    batch = db.get(PriceSheetBatch, batch_id)
    task = db.scalar(select(PriceSheetCheckoutTask).order_by(PriceSheetCheckoutTask.sequence))
    assert batch is not None and batch.status == "waiting_user"
    assert task is not None and task.status == "queued"


def test_cart_isolation_failure_sets_fixed_manual_cart_warning(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway()
    gateway.failure_on_call[1] = "cart_isolation_failed"

    execute(factory, gateway, batch_id)

    batch = db.get(PriceSheetBatch, batch_id)
    assert batch is not None and batch.status == "waiting_user"
    assert batch.last_error_code == "cart_isolation_failed"
    assert "人工检查购物车" in (batch.last_error_summary or "")


def test_tool_unavailable_fails_the_batch(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway()
    gateway.failure_on_call[1] = "tool_unavailable"

    execute(factory, gateway, batch_id)

    assert db.get(PriceSheetBatch, batch_id).status == "failed"  # type: ignore[union-attr]


def test_stop_is_applied_after_the_current_checkout_result_is_committed(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway()

    def request_stop_after_first(call_number: int) -> None:
        if call_number == 1:
            with factory() as other:
                other.get(PriceSheetBatch, batch_id).stop_requested = True  # type: ignore[union-attr]
                other.commit()

    gateway.after_checkout = request_stop_after_first
    execute(factory, gateway, batch_id)

    assert len(gateway.checkout_calls) == 1
    with factory() as other:
        assert other.get(PriceSheetBatch, batch_id).status == "stopped"  # type: ignore[union-attr]
        assert other.scalar(select(func.count()).select_from(PriceSheetCheckoutResult)) == 1


def test_recovery_requeues_only_running_checkout_tasks(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    _factory, db = database
    item_id = get_batch_detail(db, batch_id).items[0].id
    completed = PriceSheetCheckoutTask(
        price_sheet_item_id=item_id, region_code="110100", platform_sku_id="1001", sequence=1,
        status="completed", entry_mode="buy_now", attempt_count=1,
    )
    running = PriceSheetCheckoutTask(
        price_sheet_item_id=item_id, region_code="310100", platform_sku_id="1001", sequence=2,
        status="running", entry_mode=None, attempt_count=1, started_at=datetime.now(UTC),
    )
    db.add_all([completed, running])
    batch = db.get(PriceSheetBatch, batch_id)
    batch.status = "running"  # type: ignore[union-attr]
    db.commit()

    assert recover_interrupted_batches(db) == 1
    db.commit()

    assert completed.status == "completed"
    assert running.status == "queued"
    assert running.started_at is None
