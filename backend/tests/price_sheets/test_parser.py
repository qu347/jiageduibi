from datetime import date, datetime

from app.price_sheets.contracts import OcrLine
from app.price_sheets.parser import parse_price_sheet


def line(text: str, y: float, confidence: float = 0.96) -> OcrLine:
    return OcrLine(
        text=text,
        confidence=confidence,
        polygon=((0.0, y), (600.0, y), (600.0, y + 20), (0.0, y + 20)),
    )


def test_parses_each_color_as_an_independent_exact_variant() -> None:
    parsed = parse_price_sheet([
        line('郑州思物通讯---9.3收货行情', 0),
        line('苹果17系列', 30),
        line('17-256G 黑5900白5900紫5900绿5900', 60),
        line('17Pro256 白7990橙7890蓝7940', 90),
        line('17ProMAX1TB 白11850橙11850蓝11850', 120),
        line('17Air 256 黑5680白5700金5680蓝5680', 150),
    ], datetime(2026, 9, 4, 8, 0))

    assert parsed.price_date == date(2026, 9, 3)
    assert len(parsed.items) == 14
    assert any(
        item.model_name == 'iPhone 17 Pro Max'
        and item.storage == '1TB'
        and item.color == '橙色'
        and item.today_price_cents == 1_185_000
        for item in parsed.items
    )
    assert {
        (item.model_name, item.storage, item.color)
        for item in parsed.items
        if item.model_name == 'iPhone 17 Air'
    } == {
        ('iPhone 17 Air', '256GB', '黑色'),
        ('iPhone 17 Air', '256GB', '白色'),
        ('iPhone 17 Air', '256GB', '金色'),
        ('iPhone 17 Air', '256GB', '蓝色'),
    }


def test_sorts_ocr_lines_by_coordinates_before_parsing() -> None:
    parsed = parse_price_sheet([
        line('17-512G 黑7730', 100),
        line('17-256G 白5900', 50),
    ], datetime(2026, 9, 4, 8, 0))

    assert [(item.storage, item.color) for item in parsed.items] == [
        ('256GB', '白色'),
        ('512GB', '黑色'),
    ]


def test_falls_back_to_upload_date_and_marks_low_confidence_for_review() -> None:
    parsed = parse_price_sheet([
        line('苹果17系列', 0),
        line('17Pro512 白9920', 30, confidence=0.72),
    ], datetime(2026, 9, 4, 8, 0))

    assert parsed.price_date == date(2026, 9, 4)
    assert parsed.date_inferred is True
    assert parsed.items[0].confidence == 0.72
    assert parsed.items[0].review_required is True


def test_keeps_unparsed_or_invalid_rows_without_inventing_items() -> None:
    parsed = parse_price_sheet([
        line('17-256G 5900', 0),
        line('17Pro256 橙999', 30),
        line('无法识别的文字', 60),
    ], datetime(2026, 9, 4, 8, 0))

    assert parsed.items == []
    assert parsed.unparsed_lines == [
        '17-256G 5900',
        '17Pro256 橙999',
        '无法识别的文字',
    ]


def test_duplicate_exact_color_is_collapsed_to_one_review_row() -> None:
    parsed = parse_price_sheet([
        line('17-256G 紫5900紫5900蓝6000蓝5800', 0),
    ], datetime(2026, 9, 4, 8, 0))

    assert [
        (item.color, item.today_price_cents, item.review_required)
        for item in parsed.items
    ] == [
        ('紫色', 590_000, True),
        ('蓝色', 580_000, True),
    ]
