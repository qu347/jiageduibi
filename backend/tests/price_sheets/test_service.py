from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.automation.regions import MAINLAND_REGION_TARGETS
from app.db.models.price_sheets import (
    PriceSheetBatch,
    PriceSheetCheckoutResult,
    PriceSheetCheckoutTask,
    PriceSheetItem,
    PriceSheetRegionTask,
)
from app.db.session import build_engine, session_factory
from app.price_sheets.contracts import ParsedPriceSheet, ParsedPriceSheetItem
from app.price_sheets.service import create_batch, get_batch_detail, get_results, replace_items, retry_failed, start_batch


def database(tmp_path: Path):
    url = f"sqlite:///{(tmp_path / 'service.db').as_posix()}"
    config = Config(Path(__file__).parents[2] / 'alembic.ini')
    config.set_main_option('sqlalchemy.url', url)
    command.upgrade(config, 'head')
    return session_factory(build_engine(url))


def parsed_sheet() -> ParsedPriceSheet:
    return ParsedPriceSheet(
        price_date=datetime(2026, 9, 3, tzinfo=UTC).date(),
        date_inferred=False,
        items=[ParsedPriceSheetItem(
            brand='Apple', model_name='iPhone 17', storage='256GB', color='黑色',
            today_price_cents=590_000, raw_text='17-256G 黑5900', confidence=0.96,
            review_required=False,
        )],
        unparsed_lines=[],
    )


def test_start_queues_items_without_creating_tasks_before_candidates_are_frozen(tmp_path: Path) -> None:
    factory = database(tmp_path)
    with factory() as db:
        detail = create_batch(db, 'sheet.png', parsed_sheet())
        replace_items(db, detail.batch.id, detail.batch.price_date, [{
            'selected': True, 'brand': 'Apple', 'model_name': 'iPhone 17',
            'storage': '256GB', 'color': '黑色', 'today_price_cents': 590_000,
            'raw_text': 'checked', 'confidence': 1.0, 'review_required': False,
        }])
        started = start_batch(db, detail.batch.id)
        db.commit()

        assert started.batch.status == 'queued'
        assert db.query(PriceSheetRegionTask).count() == 0
        assert db.query(PriceSheetCheckoutTask).count() == 0
        assert started.items[0].total_region_count == 31


def test_review_rejects_duplicate_exact_variants(tmp_path: Path) -> None:
    factory = database(tmp_path)
    with factory() as db:
        detail = create_batch(db, 'sheet.png', parsed_sheet())
        row = {
            'selected': True, 'brand': 'Apple', 'model_name': 'iPhone 17',
            'storage': '256GB', 'color': '黑色', 'today_price_cents': 590_000,
            'raw_text': 'checked', 'confidence': 1.0, 'review_required': False,
        }
        try:
            replace_items(db, detail.batch.id, detail.batch.price_date, [row, row])
        except ValueError as exc:
            assert '重复' in str(exc)
        else:
            raise AssertionError('duplicate exact variants must be rejected')


def _started_batch(db):
    detail = create_batch(db, 'sheet.png', parsed_sheet())
    start_batch(db, detail.batch.id)
    db.flush()
    return db.get(PriceSheetBatch, detail.batch.id), db.get(PriceSheetItem, detail.items[0].id)


def _checkout_result(task: PriceSheetCheckoutTask, status: str, price: int | None = 500_000):
    unavailable = status == 'unavailable'
    return PriceSheetCheckoutResult(
        checkout_task_id=task.id,
        title='Apple iPhone 17 256GB 黑色',
        product_url=f'https://item.jd.com/{task.platform_sku_id}.html',
        shop_name='Apple产品京东自营旗舰店',
        shop_type='self_operated',
        quantity=0 if unavailable else 1,
        target_only=not unavailable,
        line_original_price_cents=None if unavailable else 550_000,
        line_sale_price_cents=None if unavailable else 500_000,
        merchant_discount_cents=0,
        ordinary_coupon_cents=0,
        subsidy_amount_cents=0,
        shipping_fee_cents=0,
        payable_price_cents=None if unavailable else price,
        discount_summary='PLUS会员' if status == 'conditional' else '',
        conditional_reason='PLUS会员' if status == 'conditional' else None,
        unavailable_code='checkout_address_required' if unavailable else None,
        price_status=status,
        region_confirmed=not unavailable,
        cart_restored=True,
        captured_at=datetime(2026, 9, 4, tzinfo=UTC),
    )


def test_checkout_progress_is_aggregated_without_returning_620_tasks(tmp_path: Path) -> None:
    factory = database(tmp_path)
    with factory() as db:
        batch, item = _started_batch(db)
        item.candidate_count = 20
        batch.status = 'running'
        tasks: list[PriceSheetCheckoutTask] = []
        for index in range(620):
            if index < 94:
                status = 'completed'
            elif index < 119:
                status = 'skipped'
            elif index < 127:
                status = 'failed'
            elif index == 127:
                status = 'running'
            else:
                status = 'queued'
            task = PriceSheetCheckoutTask(
                price_sheet_item_id=item.id,
                region_code=MAINLAND_REGION_TARGETS[index % 31].region_code,
                platform_sku_id=str(100_000_000_000 + index // 31),
                sequence=index + 1,
                status=status,
                entry_mode='buy_now' if index <= 127 else None,
                attempt_count=1 if index <= 127 else 0,
                error_code='page_changed' if status == 'failed' else None,
            )
            tasks.append(task)
        db.add_all(tasks)
        db.flush()
        for index in range(83):
            db.add(_checkout_result(tasks[index], 'verified'))
        for index in range(83, 94):
            db.add(_checkout_result(tasks[index], 'conditional'))
        for index in range(94, 112):
            result = _checkout_result(tasks[index], 'unavailable', None)
            result.unavailable_code = 'checkout_address_required' if index < 101 else 'price_unavailable'
            db.add(result)
        db.commit()

        detail = get_batch_detail(db, batch.id)

        assert detail.tasks == []
        assert detail.checkout_progress.model_dump() == {
            'stage': 'checkout_verification',
            'candidate_count': 20,
            'task_total': 620,
            'task_finished': 127,
            'verified_count': 83,
            'conditional_count': 11,
            'address_required_count': 7,
            'unavailable_count': 18,
            'failed_count': 8,
            'skipped_count': 25,
            'cart_attention_required': False,
            'current': {
                'platform_sku_id': tasks[127].platform_sku_id,
                'region_code': tasks[127].region_code,
                'address': '山西省 / 太原市 / 小店区 / 坞城街道',
                'entry_mode': 'buy_now',
            },
        }


def test_results_require_31_verified_regions_and_ignore_lower_conditional_price(tmp_path: Path) -> None:
    factory = database(tmp_path)
    with factory() as db:
        batch, item = _started_batch(db)
        item.candidate_count = 2
        item.status = 'completed'
        verified_tasks: list[PriceSheetCheckoutTask] = []
        for region in MAINLAND_REGION_TARGETS:
            task = PriceSheetCheckoutTask(
                price_sheet_item_id=item.id,
                region_code=region.region_code,
                platform_sku_id='100000000001',
                sequence=region.sequence,
                status='completed',
                entry_mode='buy_now',
                attempt_count=1,
            )
            db.add(task)
            verified_tasks.append(task)
        conditional = PriceSheetCheckoutTask(
            price_sheet_item_id=item.id,
            region_code=MAINLAND_REGION_TARGETS[0].region_code,
            platform_sku_id='100000000002',
            sequence=32,
            status='completed',
            entry_mode='buy_now',
            attempt_count=1,
        )
        failed = PriceSheetCheckoutTask(
            price_sheet_item_id=item.id,
            region_code=MAINLAND_REGION_TARGETS[1].region_code,
            platform_sku_id='100000000002',
            sequence=33,
            status='failed',
            entry_mode=None,
            attempt_count=1,
            error_code='page_changed',
        )
        db.add_all([conditional, failed])
        db.flush()
        for task, region in zip(verified_tasks, MAINLAND_REGION_TARGETS, strict=True):
            db.add(_checkout_result(task, 'verified', 500_000 + region.sequence))
        db.add(_checkout_result(conditional, 'conditional', 100_000))
        db.commit()

        complete = get_results(db, batch.id)
        assert len(complete.lower_results) == 1
        assert complete.lower_results[0].coverage == '31/31'
        assert complete.lower_results[0].payable_price_cents == 500_001
        assert complete.lower_results[0].price_status == 'verified'
        assert complete.lower_results[0].failed_count == 1

        first_result = db.scalar(select(PriceSheetCheckoutResult).where(
            PriceSheetCheckoutResult.checkout_task_id == verified_tasks[0].id
        ))
        db.delete(first_result)
        db.commit()

        incomplete = get_results(db, batch.id)
        assert incomplete.lower_results == []
        assert len(incomplete.partial_items) == 1
        assert incomplete.partial_items[0].coverage == '30/31'


def test_retry_failed_checkout_tasks_leaves_skipped_results_untouched(tmp_path: Path) -> None:
    factory = database(tmp_path)
    with factory() as db:
        batch, item = _started_batch(db)
        batch.status = 'completed_partial'
        item.status = 'partial'
        failed = PriceSheetCheckoutTask(
            price_sheet_item_id=item.id, region_code='110100', platform_sku_id='1001', sequence=1,
            status='failed', entry_mode=None, attempt_count=1, error_code='network_error',
        )
        skipped = PriceSheetCheckoutTask(
            price_sheet_item_id=item.id, region_code='310100', platform_sku_id='1001', sequence=2,
            status='skipped', entry_mode='buy_now', attempt_count=1, error_code='price_unavailable',
        )
        db.add_all([failed, skipped])
        db.flush()
        db.add(_checkout_result(skipped, 'unavailable', None))
        db.commit()

        retry_failed(db, batch.id)
        db.commit()

        assert failed.status == 'queued'
        assert skipped.status == 'skipped'
        assert db.scalar(select(PriceSheetCheckoutResult).where(
            PriceSheetCheckoutResult.checkout_task_id == skipped.id
        )) is not None


def test_cart_attention_is_derived_from_persisted_checkout_task_error(tmp_path: Path) -> None:
    factory = database(tmp_path)
    with factory() as db:
        batch, item = _started_batch(db)
        batch.status = 'waiting_user'
        db.add(PriceSheetCheckoutTask(
            price_sheet_item_id=item.id, region_code='110100', platform_sku_id='1001', sequence=1,
            status='queued', entry_mode='cart_fallback', attempt_count=1,
            error_code='cart_isolation_failed', error_summary='请人工检查购物车',
        ))
        db.commit()

    with factory() as reopened:
        assert get_batch_detail(reopened, batch.id).checkout_progress.cart_attention_required is True
