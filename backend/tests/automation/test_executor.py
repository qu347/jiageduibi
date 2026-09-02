from collections.abc import Callable, Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.automation.contracts import DiscoveredCandidate, GatewayFailure, VerifiedOffer
from app.automation.executor import CollectionExecutor
from app.automation.regions import RegionTarget
from app.automation.run_service import (
    create_run,
    get_run,
    get_task,
    request_pause,
    request_stop,
    resume_run,
)
from app.db.base import Base
from app.db.models import (
    Brand,
    CollectionRegionTask,
    Offer,
    ProductModel,
    ProductSeries,
    ProductVariant,
    SearchSession,
)
from app.db.session import build_engine, session_factory


class FakeGateway:
    adapter_version = "fake-jd/1.0"

    def __init__(self) -> None:
        self.discover_calls: list[tuple[str, int]] = []
        self.verify_calls: list[tuple[str, str]] = []
        self.always_fail_regions: dict[str, str] = {}
        self.fail_once_regions: dict[str, str] = {}
        self.on_verify: Callable[[], None] | None = None
        self._active_calls = 0
        self.max_concurrent_calls = 0

    def discover(self, query: str, limit: int) -> list[DiscoveredCandidate]:
        self.discover_calls.append((query, limit))
        return [
            DiscoveredCandidate(
                platform_sku_id="sku-next",
                title="Apple iPhone 17 256GB 全新国行",
                product_url="https://item.jd.com/sku-next.html",
                shop_name="京东自营",
                platform_shop_id="jd-self",
                shop_type="self_operated",
                initial_price_cents=519900,
            ),
            DiscoveredCandidate(
                platform_sku_id="sku-cheapest",
                title="Apple iPhone 17 256GB 全新国行",
                product_url="https://item.jd.com/sku-cheapest.html",
                shop_name="京东自营",
                platform_shop_id="jd-self",
                shop_type="self_operated",
                initial_price_cents=499900,
            ),
        ]

    def verify(
        self,
        candidate: DiscoveredCandidate,
        region: RegionTarget,
    ) -> VerifiedOffer:
        self._active_calls += 1
        self.max_concurrent_calls = max(self.max_concurrent_calls, self._active_calls)
        try:
            self.verify_calls.append((candidate.platform_sku_id, region.region_code))
            if self.on_verify is not None:
                callback, self.on_verify = self.on_verify, None
                callback()
            if region.region_code in self.always_fail_regions:
                code = self.always_fail_regions[region.region_code]
                raise GatewayFailure(code, f"模拟 {code}")
            if region.region_code in self.fail_once_regions:
                code = self.fail_once_regions.pop(region.region_code)
                raise GatewayFailure(code, f"模拟 {code}")
            return VerifiedOffer(
                platform_sku_id=candidate.platform_sku_id,
                title=candidate.title,
                product_url=candidate.product_url,
                shop_name=candidate.shop_name,
                platform_shop_id=candidate.platform_shop_id,
                shop_type=candidate.shop_type,
                listed_price_cents=candidate.initial_price_cents,
                sale_price_cents=candidate.initial_price_cents,
                merchant_discount_cents=0,
                platform_coupon_cents=0,
                member_discount_cents=0,
                payment_discount_cents=0,
                subsidy_amount_cents=0,
                subsidy_status="unknown",
                shipping_fee_cents=0,
                installation_fee_cents=0,
                conditional_price_cents=None,
                stock_status="in_stock",
                captured_at=datetime.now(UTC),
            )
        finally:
            self._active_calls -= 1

    def attempts_for(self, region_code: str) -> int:
        return sum(call_region == region_code for _sku, call_region in self.verify_calls)


@pytest.fixture
def database(tmp_path) -> Generator[tuple[sessionmaker[Session], Session], None, None]:
    engine = build_engine(f"sqlite:///{(tmp_path / 'executor.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = session_factory(engine)
    db = factory()
    try:
        yield factory, db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture
def run_id(database: tuple[sessionmaker[Session], Session]) -> int:
    _factory, db = database
    brand = Brand(name="Apple", deleted_at=None)
    db.add(brand)
    db.flush()
    series = ProductSeries(brand_id=brand.id, name="iPhone 17 系列", active=True, deleted_at=None)
    db.add(series)
    db.flush()
    model = ProductModel(
        series_id=series.id,
        model_name="iPhone 17",
        model_code="APPLE_IPHONE_17",
        category="手机",
        active=True,
        deleted_at=None,
    )
    db.add(model)
    db.flush()
    variant = ProductVariant(
        model_id=model.id,
        sku_code="APPLE_IPHONE_17_256_CN_NEW_ANY",
        storage="256GB",
        memory=None,
        color="不限",
        region_version="中国大陆国行",
        condition="全新",
        active=True,
        deleted_at=None,
    )
    db.add(variant)
    db.flush()
    search = SearchSession(
        variant_id=variant.id,
        region_code=None,
        comparison_scope="national",
        include_conditional=False,
        status="collecting",
        created_at=datetime.now(UTC),
        finalized_at=None,
    )
    db.add(search)
    db.commit()
    result = create_run(db, search.id)
    db.commit()
    return result.id


def execute_with(
    database: tuple[sessionmaker[Session], Session],
    gateway: FakeGateway,
    run_id: int,
) -> None:
    factory, _db = database
    CollectionExecutor(factory, lambda: gateway, retry_delays=(0.0, 0.0)).execute(run_id)


def refresh(db: Session) -> None:
    db.expire_all()


def test_executor_discovers_once_and_verifies_regions_sequentially(
    database: tuple[sessionmaker[Session], Session],
    run_id: int,
) -> None:
    gateway = FakeGateway()

    execute_with(database, gateway, run_id)
    _factory, db = database
    refresh(db)

    assert gateway.discover_calls == [("Apple iPhone 17 256GB", 30)]
    assert gateway.max_concurrent_calls == 1
    assert gateway.verify_calls[:2] == [
        ("sku-cheapest", "110100"),
        ("sku-next", "110100"),
    ]
    assert gateway.verify_calls[-1][1] == "650100"
    assert get_run(db, run_id).status == "completed"
    assert get_run(db, run_id).completed_region_count == 31
    assert db.scalar(select(func.count(Offer.id))) == 62


def test_captcha_pauses_current_task_without_losing_completed_regions(
    database: tuple[sessionmaker[Session], Session],
    run_id: int,
) -> None:
    gateway = FakeGateway()
    gateway.fail_once_regions["310100"] = "captcha"

    execute_with(database, gateway, run_id)
    _factory, db = database
    refresh(db)

    assert get_run(db, run_id).status == "waiting_user"
    assert get_task(db, run_id, "110100").status == "completed"
    assert get_task(db, run_id, "310100").status == "waiting_user"

    resume_run(db, run_id)
    db.commit()
    execute_with(database, gateway, run_id)
    refresh(db)

    assert gateway.discover_calls == [("Apple iPhone 17 256GB", 30)]
    assert get_run(db, run_id).status == "completed"


def test_network_error_retries_twice_then_continues_to_next_region(
    database: tuple[sessionmaker[Session], Session],
    run_id: int,
) -> None:
    gateway = FakeGateway()
    gateway.always_fail_regions["540100"] = "network_error"

    execute_with(database, gateway, run_id)
    _factory, db = database
    refresh(db)

    assert gateway.attempts_for("540100") == 3
    assert get_task(db, run_id, "540100").status == "failed"
    assert get_task(db, run_id, "610100").status == "completed"
    assert get_run(db, run_id).status == "completed_partial"


def test_pause_after_gateway_checkpoint_requeues_current_region(
    database: tuple[sessionmaker[Session], Session],
    run_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway()

    def pause() -> None:
        with factory() as control_db:
            request_pause(control_db, run_id)
            control_db.commit()

    gateway.on_verify = pause
    execute_with(database, gateway, run_id)
    refresh(db)

    assert get_run(db, run_id).status == "paused"
    assert get_task(db, run_id, "110100").status == "queued"
    assert gateway.verify_calls == [("sku-cheapest", "110100")]


def test_stop_keeps_committed_offer_and_skips_unfinished_regions(
    database: tuple[sessionmaker[Session], Session],
    run_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway()

    def stop() -> None:
        with factory() as control_db:
            request_stop(control_db, run_id)
            control_db.commit()

    gateway.on_verify = stop
    execute_with(database, gateway, run_id)
    refresh(db)

    assert get_run(db, run_id).status == "stopped"
    assert db.scalar(select(func.count(Offer.id))) == 1
    skipped = db.scalar(
        select(func.count(CollectionRegionTask.id)).where(
            CollectionRegionTask.collection_run_id == run_id,
            CollectionRegionTask.status == "skipped",
        )
    )
    assert skipped == 31
