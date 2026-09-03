from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.automation.contracts import DiscoveredCandidate, GatewayFailure, VerifiedOffer
from app.automation.regions import RegionTarget
from app.db.base import Base
from app.db.models.price_sheets import PriceSheetRegionResult, PriceSheetRegionTask
from app.db.session import build_engine, session_factory
from app.price_sheets.contracts import ParsedPriceSheet, ParsedPriceSheetItem
from app.price_sheets.executor import PriceSheetExecutor
from app.price_sheets.service import create_batch, get_batch_detail, get_results, resume_batch, start_batch


class FakeGateway:
    adapter_version = 'fake-jd/1.0'

    def __init__(self) -> None:
        self.discover_calls: list[str] = []
        self.region_calls: list[str] = []
        self.fail_once: dict[str, str] = {}
        self.always_fail: dict[str, str] = {}

    def discover(self, query: str, limit: int) -> list[DiscoveredCandidate]:
        self.discover_calls.append(query)
        return [
            self._candidate('2', 510_000),
            self._candidate('1', 500_000),
        ][:limit]

    def verify_region(
        self,
        _query: str,
        candidates: list[DiscoveredCandidate],
        region: RegionTarget,
    ) -> list[VerifiedOffer]:
        self.region_calls.append(region.region_code)
        if region.region_code in self.always_fail:
            raise GatewayFailure(self.always_fail[region.region_code], '模拟失败')
        if region.region_code in self.fail_once:
            raise GatewayFailure(self.fail_once.pop(region.region_code), '模拟一次失败')
        return [self._offer(candidate, region.sequence) for candidate in candidates]

    @staticmethod
    def _candidate(sku: str, price: int) -> DiscoveredCandidate:
        return DiscoveredCandidate(
            platform_sku_id=sku,
            title='Apple iPhone 17 256GB 黑色 全新国行',
            product_url=f'https://item.jd.com/{sku}.html',
            shop_name='京东自营',
            platform_shop_id='self',
            shop_type='self_operated',
            initial_price_cents=price,
        )

    @staticmethod
    def _offer(candidate: DiscoveredCandidate, sequence: int) -> VerifiedOffer:
        price = candidate.initial_price_cents + sequence * 100
        return VerifiedOffer(
            platform_sku_id=candidate.platform_sku_id,
            title=candidate.title,
            product_url=candidate.product_url,
            shop_name=candidate.shop_name,
            platform_shop_id=candidate.platform_shop_id,
            shop_type=candidate.shop_type,
            listed_price_cents=price,
            sale_price_cents=price,
            merchant_discount_cents=0,
            platform_coupon_cents=0,
            member_discount_cents=0,
            payment_discount_cents=0,
            subsidy_amount_cents=0,
            subsidy_status='unknown',
            shipping_fee_cents=0,
            installation_fee_cents=0,
            conditional_price_cents=None,
            stock_status='in_stock',
            captured_at=datetime.now(UTC),
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
            brand='Apple', model_name='iPhone 17', storage='256GB', color='黑色',
            today_price_cents=590_000, raw_text='17-256G 黑5900', confidence=0.98,
            review_required=False,
        )],
        unparsed_lines=[],
    )
    detail = create_batch(db, 'sheet.png', parsed)
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


def test_executor_discovers_once_and_saves_one_lowest_result_per_region(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway()

    execute(factory, gateway, batch_id)
    db.expire_all()

    detail = get_batch_detail(db, batch_id)
    assert gateway.discover_calls == ['Apple iPhone 17 256GB 黑色']
    assert len(gateway.region_calls) == 31
    assert detail.batch.status == 'completed'
    assert detail.items[0].completed_region_count == 31
    assert db.scalar(select(func.count(PriceSheetRegionResult.id))) == 31
    assert db.scalar(select(func.min(PriceSheetRegionResult.trusted_price_cents))) == 500_100
    results = get_results(db, batch_id)
    assert len(results.lower_results) == 1
    assert results.lower_results[0].coverage == '31/31'
    assert results.lower_results[0].address == '北京市 / 朝阳区 / 奥运村街道'


def test_waiting_task_resumes_without_repeating_completed_regions_or_search(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway()
    gateway.fail_once['310100'] = 'captcha'

    execute(factory, gateway, batch_id)
    db.expire_all()
    first_count = len(gateway.region_calls)
    assert get_batch_detail(db, batch_id).batch.status == 'waiting_user'

    resume_batch(db, batch_id)
    db.commit()
    execute(factory, gateway, batch_id)
    db.expire_all()

    assert gateway.discover_calls == ['Apple iPhone 17 256GB 黑色']
    assert gateway.region_calls.count('110100') == 1
    assert len(gateway.region_calls) == first_count + (31 - 8)
    assert get_batch_detail(db, batch_id).batch.status == 'completed'


def test_partial_coverage_is_never_reported_as_nationwide_lowest(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway()
    gateway.always_fail['540100'] = 'page_changed'

    execute(factory, gateway, batch_id)
    db.expire_all()

    results = get_results(db, batch_id)
    assert results.lower_results == []
    assert results.not_lower_items == []
    assert len(results.partial_items) == 1
    assert results.partial_items[0].coverage == '30/31'
    task = db.scalar(select(PriceSheetRegionTask).where(PriceSheetRegionTask.region_code == '540100'))
    assert task is not None and task.status == 'failed'


def test_network_failure_retries_twice_then_continues(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    factory, db = database
    gateway = FakeGateway()
    gateway.always_fail['540100'] = 'network_error'

    execute(factory, gateway, batch_id)
    db.expire_all()

    assert gateway.region_calls.count('540100') == 3
    assert '610100' in gateway.region_calls
    assert get_batch_detail(db, batch_id).batch.status == 'completed_partial'


def test_complete_price_that_is_not_lower_is_reported_separately(
    database: tuple[sessionmaker[Session], Session], batch_id: int,
) -> None:
    factory, db = database
    item = get_batch_detail(db, batch_id).items[0]
    from app.db.models.price_sheets import PriceSheetItem
    db.get(PriceSheetItem, item.id).today_price_cents = 400_000
    db.commit()

    execute(factory, FakeGateway(), batch_id)
    db.expire_all()

    results = get_results(db, batch_id)
    assert results.lower_results == []
    assert len(results.not_lower_items) == 1
    assert results.not_lower_items[0].status == 'not_lower'
