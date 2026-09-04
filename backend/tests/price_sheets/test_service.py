from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.db.models.price_sheets import PriceSheetCheckoutTask, PriceSheetRegionTask
from app.db.session import build_engine, session_factory
from app.price_sheets.contracts import ParsedPriceSheet, ParsedPriceSheetItem
from app.price_sheets.service import create_batch, replace_items, start_batch


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
