from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def config_for(tmp_path: Path) -> Config:
    config = Config(Path(__file__).parents[2] / 'alembic.ini')
    config.set_main_option('sqlalchemy.url', f"sqlite:///{(tmp_path / 'price-sheets.db').as_posix()}")
    return config


def test_price_sheet_migration_creates_independent_persistent_queue(tmp_path: Path) -> None:
    config = config_for(tmp_path)
    command.upgrade(config, '0007_collection_region_streets')

    command.upgrade(config, 'head')

    engine = create_engine(config.get_main_option('sqlalchemy.url'))
    inspector = inspect(engine)
    expected = {
        'price_sheet_batches',
        'price_sheet_items',
        'price_sheet_region_tasks',
        'price_sheet_region_results',
    }
    assert expected <= set(inspector.get_table_names())
    batch_columns = {column['name'] for column in inspector.get_columns('price_sheet_batches')}
    assert not {'image', 'image_data', 'image_path'} & batch_columns
    assert {item['name'] for item in inspector.get_unique_constraints('price_sheet_items')} == {
        'uq_price_sheet_item_variant',
    }
    assert {item['name'] for item in inspector.get_unique_constraints('price_sheet_region_tasks')} == {
        'uq_price_sheet_task_region',
    }
    assert {item['name'] for item in inspector.get_unique_constraints('price_sheet_region_results')} == {
        'uq_price_sheet_result_region',
    }
    engine.dispose()


def test_price_sheet_migration_downgrade_preserves_existing_tables(tmp_path: Path) -> None:
    config = config_for(tmp_path)
    command.upgrade(config, 'head')

    command.downgrade(config, '0007_collection_region_streets')

    engine = create_engine(config.get_main_option('sqlalchemy.url'))
    tables = set(inspect(engine).get_table_names())
    assert 'collection_region_tasks' in tables
    assert not any(table.startswith('price_sheet_') for table in tables)
    engine.dispose()
