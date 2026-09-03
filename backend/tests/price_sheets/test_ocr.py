from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.price_sheets.contracts import OcrLine
from app.main import _default_ocr_engine_factory
from app.price_sheets.ocr import FixtureOcrEngine, ImageValidationError, PaddleOcrEngine, recognize_image


class RecordingEngine:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.received_path: Path | None = None

    def recognize(self, image_path: Path) -> list[OcrLine]:
        self.received_path = image_path
        assert image_path.exists()
        if self.failure:
            raise self.failure
        return [OcrLine('17-256G 黑5900', 0.98, ((0, 0), (1, 0), (1, 1), (0, 1)))]


def image_bytes(format_name: str = 'PNG', size: tuple[int, int] = (10, 10)) -> bytes:
    buffer = BytesIO()
    Image.new('1', size, color=1).save(buffer, format=format_name)
    return buffer.getvalue()


def test_valid_image_is_passed_through_a_random_temporary_file_then_deleted() -> None:
    engine = RecordingEngine()

    rows = recognize_image(image_bytes(), 'image/png', engine)

    assert rows[0].text == '17-256G 黑5900'
    assert engine.received_path is not None
    assert not engine.received_path.exists()


@pytest.mark.parametrize(
    ('data', 'content_type', 'code'),
    [
        (image_bytes(), 'text/plain', 'unsupported_type'),
        (b'not-an-image', 'image/png', 'invalid_image'),
        (image_bytes('JPEG'), 'image/png', 'type_mismatch'),
        (b'x' * (10 * 1024 * 1024 + 1), 'image/png', 'file_too_large'),
        (image_bytes(size=(5000, 4001)), 'image/png', 'too_many_pixels'),
    ],
    ids=['mime', 'magic', 'mismatch', 'bytes', 'pixels'],
)
def test_rejects_unsafe_image_inputs(data: bytes, content_type: str, code: str) -> None:
    with pytest.raises(ImageValidationError) as failure:
        recognize_image(data, content_type, RecordingEngine())

    assert failure.value.code == code


def test_temporary_file_is_deleted_when_engine_fails() -> None:
    engine = RecordingEngine(RuntimeError('model failed'))

    with pytest.raises(RuntimeError, match='model failed'):
        recognize_image(image_bytes(), 'image/png', engine)

    assert engine.received_path is not None
    assert not engine.received_path.exists()


def test_fixture_ocr_returns_two_color_specific_rows() -> None:
    rows = FixtureOcrEngine().recognize(Path('ignored.png'))

    assert [row.text for row in rows] == [
        '9.3收货行情',
        '17-256G 黑5900',
        '17-256G 白5000',
    ]


def test_default_ocr_uses_fixture_only_for_exact_test_environment_value(monkeypatch) -> None:
    monkeypatch.setenv('PRICE_COMPARE_OCR_FIXTURE', 'true')
    assert isinstance(_default_ocr_engine_factory(), PaddleOcrEngine)

    monkeypatch.setenv('PRICE_COMPARE_OCR_FIXTURE', '1')
    assert isinstance(_default_ocr_engine_factory(), FixtureOcrEngine)
