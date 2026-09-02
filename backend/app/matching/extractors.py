import re


MODEL_PATTERNS = (
    ("APPLE_IPHONE_17_PRO_MAX", re.compile(r"iphone\s*17\s*pro\s*max", re.I)),
    ("APPLE_IPHONE_17_PRO", re.compile(r"iphone\s*17\s*pro(?!\s*max)", re.I)),
    ("APPLE_IPHONE_17", re.compile(r"iphone\s*17(?!\s*pro)", re.I)),
)

STORAGE_PATTERN = re.compile(r"(?<![A-Za-z0-9])(\d+)\s*(?:GB|G)(?![A-Za-z0-9])", re.I)


def extract_model_code(title: str) -> str | None:
    for model_code, pattern in MODEL_PATTERNS:
        if pattern.search(title):
            return model_code
    return None


def extract_storage(title: str) -> str | None:
    match = STORAGE_PATTERN.search(title)
    return f"{match.group(1)}GB" if match else None


def title_has_brand(title: str, brand: str) -> bool:
    normalized = title.casefold()
    if brand.casefold() == "apple":
        return "apple" in normalized or "iphone" in normalized or "苹果" in title
    return brand.casefold() in normalized


def title_has_mainland_region(title: str) -> bool:
    return "国行" in title or "中国大陆" in title


def title_has_other_region(title: str) -> bool:
    return any(term in title for term in ("港版", "美版", "日版", "韩版", "海外版"))


def title_has_new_condition(title: str) -> bool:
    return "全新" in title
