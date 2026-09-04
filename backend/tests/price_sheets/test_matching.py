from app.automation.contracts import DiscoveredCandidate
from app.price_sheets.matching import PriceSheetTarget, select_price_sheet_candidates


def candidate(sku: str, title: str, price: int = 500_000) -> DiscoveredCandidate:
    return DiscoveredCandidate(
        platform_sku_id=sku,
        title=title,
        product_url=f'https://item.jd.com/{sku}.html',
        shop_name='京东自营',
        platform_shop_id='self',
        shop_type='self_operated',
        initial_price_cents=price,
    )


def test_query_and_selection_require_exact_model_capacity_and_color() -> None:
    target = PriceSheetTarget('Apple', 'iPhone 17 Pro', '256GB', '橙色')
    assert target.query == 'Apple iPhone 17 Pro 256GB 橙色'
    rows = [
        candidate('1', 'Apple iPhone 17 Pro 256GB 橙色 全新国行', 520_000),
        candidate('2', 'Apple iPhone 17 Pro Max 256GB 橙色 全新国行', 490_000),
        candidate('3', 'Apple iPhone 17 Air 256GB 橙色 全新国行', 480_000),
        candidate('4', 'Apple iPhone 17 Pro 512GB 橙色 全新国行', 470_000),
        candidate('5', 'Apple iPhone 17 Pro 256GB 蓝色 全新国行', 460_000),
        candidate('6', 'Apple iPhone 17 Pro 256GB 全新国行', 450_000),
    ]

    selected = select_price_sheet_candidates(target, rows)

    assert [row.platform_sku_id for row in selected] == ['1']


def test_selection_excludes_wrong_version_condition_accessories_and_conditional_sales() -> None:
    target = PriceSheetTarget('Apple', 'iPhone 17', '256GB', '黑色')
    excluded = ['手机壳', '海外版', '港版', '二手', '准新机', '翻新机', '定金', '分期', '以旧换新', '预约专享']
    rows = [candidate(str(index), f'Apple iPhone 17 256GB 黑色 {word}') for index, word in enumerate(excluded)]
    rows.append(candidate('99', 'Apple iPhone 17 256GB 黑色 全新国行'))

    assert [row.platform_sku_id for row in select_price_sheet_candidates(target, rows)] == ['99']


def test_selection_is_stably_sorted_and_defaults_to_twenty() -> None:
    target = PriceSheetTarget('Apple', 'iPhone 17', '256GB', '白色')
    rows = [candidate(str(index).zfill(2), 'Apple iPhone 17 256GB 白色 全新国行', 500_000 - index) for index in range(25)]

    selected = select_price_sheet_candidates(target, rows)

    assert len(selected) == 20
    assert [row.platform_sku_id for row in selected[:2]] == ['24', '23']
