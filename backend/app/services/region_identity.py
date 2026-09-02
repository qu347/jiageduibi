def normalize_region_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def build_region_key(region_code: str | None, region_name: str | None) -> str:
    normalized_name = normalize_region_name(region_name) if region_name else ""
    if region_code and normalized_name == "全国":
        raise ValueError("地区代码不能与全国适用同时出现")
    if region_code:
        return f"code:{region_code}"
    if normalized_name == "全国":
        return "national"
    if normalized_name:
        return f"name:{normalized_name}"
    return "unknown"
