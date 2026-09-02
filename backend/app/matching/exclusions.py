ACCESSORY_TERMS = ("手机壳", "钢化膜", "充电器", "数据线", "碎屏险", "延保")
NON_NEW_TERMS = ("二手", "翻新", "展示机", "官换机")
INSTALLMENT_TERMS = ("每月", "月供", "分期价")
TRADE_IN_TERMS = ("以旧换新", "回收抵扣")
DEPOSIT_TERMS = ("定金", "预售价")


def explicit_offer_exclusion(title: str) -> str | None:
    if any(term in title for term in ACCESSORY_TERMS):
        return "accessory"
    if any(term in title for term in NON_NEW_TERMS):
        return "condition_mismatch"
    if any(term in title for term in INSTALLMENT_TERMS):
        return "installment_only"
    if any(term in title for term in TRADE_IN_TERMS):
        return "trade_in_only"
    if any(term in title for term in DEPOSIT_TERMS):
        return "deposit_only"
    return None
