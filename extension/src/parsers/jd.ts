import {
  pageFailure,
  parseCents,
  textOf,
  type PlatformParser,
  type RawOfferCandidate,
} from './base'


export const jdParser: PlatformParser = {
  platform: 'jd',
  adapterVersion: 'fixture-v1',
  canHandle: (url) => url.hostname === 'search.jd.com',
  parse(document) {
    const failure = pageFailure(document)
    if (failure) return failure
    const cards = [...document.querySelectorAll('#J_goodsList .gl-item')]
    if (!cards.length) return { status: 'unsupported', message: '当前京东页面没有可识别的商品列表' }
    const items: RawOfferCandidate[] = []
    for (const card of cards) {
      const price = parseCents(textOf(card.querySelector('.p-price')))
      if (price === null) return { status: 'missing_price', message: '商品缺少一次性总价，未进行猜测' }
      const shopName = textOf(card.querySelector('.p-shop')) || '京东店铺'
      items.push({
        platform: 'jd',
        title: textOf(card.querySelector('.p-name em')),
        platform_product_id: card.getAttribute('data-product-id') ?? '',
        platform_sku_id: card.getAttribute('data-sku') ?? '',
        platform_shop_id: shopName,
        shop_name: shopName,
        shop_type: shopName.includes('自营') ? 'self_operated' : 'third_party',
        product_url: card.querySelector<HTMLAnchorElement>('.p-link')?.href ?? '',
        sale_price_cents: price,
        captured_at: new Date().toISOString(),
      })
    }
    return { status: 'ok', items }
  },
}
