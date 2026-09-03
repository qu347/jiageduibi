from __future__ import annotations

import re
from datetime import date, datetime

from app.price_sheets.contracts import OcrLine, ParsedPriceSheet, ParsedPriceSheetItem


_SPEC_PATTERN = re.compile(
    r"^\s*(?:苹果|Apple|iPhone)?\s*"
    r"(?P<series>\d{1,2})\s*"
    r"(?P<variant>Pro\s*MAX|ProMax|Pro|Air)?\s*"
    r"[-—]?\s*"
    r"(?P<storage>\d{1,2}\s*TB|\d{3,4}\s*(?:GB|G)?)"
    r"(?P<prices>.*)$",
    re.IGNORECASE,
)
_COLOR_NAMES = {
    "黑": "黑色",
    "黑色": "黑色",
    "白": "白色",
    "白色": "白色",
    "紫": "紫色",
    "紫色": "紫色",
    "蓝": "蓝色",
    "蓝色": "蓝色",
    "绿": "绿色",
    "绿色": "绿色",
    "橙": "橙色",
    "橙色": "橙色",
    "金": "金色",
    "金色": "金色",
}
_COLOR_PRICE_PATTERN = re.compile(
    rf"({'|'.join(sorted(_COLOR_NAMES, key=len, reverse=True))})\s*[：:]?\s*(\d{{3,5}})"
)
_DATE_PATTERN = re.compile(r"(?<!\d)(1[0-2]|0?[1-9])[.月/-](3[01]|[12]?\d)(?:日)?(?!\d)")


def _sort_key(line: OcrLine) -> tuple[float, float]:
    if not line.polygon:
        return (float("inf"), float("inf"))
    return (
        min(point[1] for point in line.polygon),
        min(point[0] for point in line.polygon),
    )


def _price_date(lines: list[OcrLine], uploaded_at: datetime) -> tuple[date, bool]:
    for line in lines:
        match = _DATE_PATTERN.search(line.text)
        if not match:
            continue
        try:
            return date(uploaded_at.year, int(match.group(1)), int(match.group(2))), False
        except ValueError:
            continue
    return uploaded_at.date(), True


def _model_name(series: str, variant: str | None) -> str:
    suffix = ""
    normalized = re.sub(r"\s+", "", variant or "").lower()
    if normalized == "pro":
        suffix = " Pro"
    elif normalized == "promax":
        suffix = " Pro Max"
    elif normalized == "air":
        suffix = " Air"
    return f"iPhone {int(series)}{suffix}"


def _storage(value: str) -> str:
    normalized = re.sub(r"\s+", "", value).upper()
    if normalized.endswith("TB"):
        return normalized
    number = normalized.removesuffix("GB").removesuffix("G")
    return f"{int(number)}GB"


def parse_price_sheet(lines: list[OcrLine], uploaded_at: datetime) -> ParsedPriceSheet:
    ordered = sorted(lines, key=_sort_key)
    price_date, date_inferred = _price_date(ordered, uploaded_at)
    items: list[ParsedPriceSheetItem] = []
    unparsed: list[str] = []

    for line in ordered:
        raw_text = " ".join(line.text.split())
        if not raw_text or _DATE_PATTERN.search(raw_text) or re.fullmatch(r"苹果\s*\d+\s*系列", raw_text):
            continue
        match = _SPEC_PATTERN.match(raw_text)
        if not match:
            unparsed.append(raw_text)
            continue
        pairs = list(_COLOR_PRICE_PATTERN.finditer(match.group("prices")))
        valid_count = 0
        for pair in pairs:
            cents = int(pair.group(2)) * 100
            if not 100_000 <= cents <= 3_000_000:
                continue
            valid_count += 1
            confidence = max(0.0, min(1.0, float(line.confidence)))
            items.append(ParsedPriceSheetItem(
                brand="Apple",
                model_name=_model_name(match.group("series"), match.group("variant")),
                storage=_storage(match.group("storage")),
                color=_COLOR_NAMES[pair.group(1)],
                today_price_cents=cents,
                raw_text=raw_text,
                confidence=confidence,
                review_required=confidence < 0.80 or date_inferred,
            ))
        if valid_count == 0:
            unparsed.append(raw_text)

    return ParsedPriceSheet(
        price_date=price_date,
        date_inferred=date_inferred,
        items=items,
        unparsed_lines=unparsed,
    )
