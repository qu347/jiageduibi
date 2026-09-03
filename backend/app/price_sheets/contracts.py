from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class OcrLine:
    text: str
    confidence: float
    polygon: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class ParsedPriceSheetItem:
    brand: str
    model_name: str
    storage: str
    color: str
    today_price_cents: int
    raw_text: str
    confidence: float
    review_required: bool


@dataclass(frozen=True, slots=True)
class ParsedPriceSheet:
    price_date: date
    date_inferred: bool
    items: list[ParsedPriceSheetItem]
    unparsed_lines: list[str]
