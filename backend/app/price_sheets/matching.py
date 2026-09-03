from __future__ import annotations

import re
from dataclasses import dataclass

from app.automation.contracts import DiscoveredCandidate


_MODEL_PATTERN = re.compile(
    r"(?:iPhone|苹果)\s*(?P<series>\d{1,2})(?:\s*(?P<variant>Pro\s*Max|ProMax|Pro|Air))?",
    re.IGNORECASE,
)
_STORAGE_PATTERN = re.compile(r"(?<!\d)(\d{1,4})\s*(TB|GB|G)(?![A-Za-z])", re.IGNORECASE)
_EXCLUDED = re.compile(
    r"手机壳|保护壳|钢化膜|镜头膜|充电器|数据线|配件|"
    r"海外版|国际版|港版|香港版|美版|日版|韩版|"
    r"二手|准新|翻新|展示机|官换机|资源机|"
    r"定金|分期|以旧换新|预约|新人"
)
_COLOR_LABELS = {
    "黑色": ("黑色", "黑款"),
    "白色": ("白色", "白款"),
    "紫色": ("紫色", "紫款"),
    "蓝色": ("蓝色", "蓝款"),
    "绿色": ("绿色", "绿款"),
    "橙色": ("橙色", "橙款"),
    "金色": ("金色", "金款"),
}


@dataclass(frozen=True, slots=True)
class PriceSheetTarget:
    brand: str
    model_name: str
    storage: str
    color: str

    @property
    def query(self) -> str:
        return " ".join((self.brand, self.model_name, self.storage, self.color))[:200]


def _model_key(text: str) -> tuple[int, str] | None:
    matches = list(_MODEL_PATTERN.finditer(text))
    if not matches:
        return None
    match = matches[-1]
    variant = re.sub(r"\s+", "", match.group("variant") or "").lower()
    if variant == "promax":
        variant = "pro max"
    return int(match.group("series")), variant


def _storage_key(text: str) -> str | None:
    match = _STORAGE_PATTERN.search(text)
    if not match:
        return None
    unit = match.group(2).upper()
    return f"{int(match.group(1))}{'TB' if unit == 'TB' else 'GB'}"


def _has_exact_color(title: str, color: str) -> bool:
    compact = re.sub(r"\s+", "", title)
    return any(label in compact for label in _COLOR_LABELS.get(color, (color,)))


def select_price_sheet_candidates(
    target: PriceSheetTarget,
    candidates: list[DiscoveredCandidate],
    limit: int = 15,
) -> list[DiscoveredCandidate]:
    target_model = _model_key(target.model_name)
    target_storage = _storage_key(target.storage)
    accepted = [
        candidate
        for candidate in candidates
        if not _EXCLUDED.search(candidate.title)
        and _model_key(candidate.title) == target_model
        and _storage_key(candidate.title) == target_storage
        and _has_exact_color(candidate.title, target.color)
    ]
    return sorted(accepted, key=lambda item: (item.initial_price_cents, item.platform_sku_id))[:limit]
