from io import BytesIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import inspect

from app.main import create_app
from app.price_sheets.contracts import OcrLine


class FixedOcrEngine:
    def recognize(self, _image_path: Path) -> list[OcrLine]:
        return [
            OcrLine('郑州思物通讯---9.3收货行情', 0.98, ((0, 0), (1, 0), (1, 1), (0, 1))),
            OcrLine('17-256G 黑5900白5900', 0.96, ((0, 2), (1, 2), (1, 3), (0, 3))),
        ]


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new('RGB', (10, 10), color='white').save(buffer, format='PNG')
    return buffer.getvalue()


def client_for(tmp_path: Path) -> TestClient:
    url = f"sqlite:///{(tmp_path / 'api.db').as_posix()}"
    config = Config(Path(__file__).parents[2] / 'alembic.ini')
    config.set_main_option('sqlalchemy.url', url)
    command.upgrade(config, 'head')
    return TestClient(create_app(database_url=url, ocr_engine_factory=FixedOcrEngine))


def test_recognize_edit_and_start_batch_without_persisting_image(tmp_path: Path) -> None:
    client = client_for(tmp_path)
    recognized = client.post(
        '/api/price-sheet-batches/recognize',
        content=png_bytes(),
        headers={'Content-Type': 'image/png', 'X-File-Name': 'sheet.png'},
    )

    assert recognized.status_code == 201
    detail = recognized.json()
    assert detail['batch']['status'] == 'reviewing'
    assert len(detail['items']) == 2
    assert {item['color'] for item in detail['items']} == {'黑色', '白色'}
    batch_id = detail['batch']['id']
    columns = {column['name'] for column in inspect(client.app.state.engine).get_columns('price_sheet_batches')}
    assert not {'image', 'image_data', 'image_path'} & columns

    saved = client.put(f'/api/price-sheet-batches/{batch_id}/items', json={
        'price_date': '2026-09-03',
        'items': [
            {**item, 'today_price_cents': item['today_price_cents'] - 1000}
            for item in detail['items']
        ],
    })
    assert saved.status_code == 200
    started = client.post(f'/api/price-sheet-batches/{batch_id}/start')
    assert started.status_code == 200
    assert started.json()['batch']['status'] == 'queued'
    assert started.json()['batch']['selected_count'] == 2
    assert len(started.json()['tasks']) == 62
    assert started.json()['tasks'][0]['street'] == '奥运村街道'


def test_review_validation_returns_structured_422(tmp_path: Path) -> None:
    client = client_for(tmp_path)
    detail = client.post(
        '/api/price-sheet-batches/recognize', content=png_bytes(),
        headers={'Content-Type': 'image/png', 'X-File-Name': 'sheet.png'},
    ).json()
    row = detail['items'][0]

    response = client.put(f"/api/price-sheet-batches/{detail['batch']['id']}/items", json={
        'price_date': '2026-09-03',
        'items': [row, row],
    })

    assert response.status_code == 422
    assert response.json()['detail']['what_happened'] == '保存价目表校对结果失败'
