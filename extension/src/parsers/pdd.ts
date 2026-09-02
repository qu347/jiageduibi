import {
  pageFailure,
  parseCents,
  textOf,
  type PlatformParser,
  type RawOfferCandidate,
} from './base'


export const pddParser: PlatformParser = {
  platform: 'pdd',
  adapterVersion: 'fixture-v1',
  canHandle: (url) => url.hostname === 'mobile.yangkeduo.com',
  parse(document) {
    const failure = pageFailure(document)
    if (failure) return failure
    const cards = [...document.querySelectorAll('[data-testid="goods-card"]')]
    if (!cards.length) return { status: 'unsupported', message: '当前拼多多页面没有可识别的商品列表' }
    const items: RawOfferCandidate[] = []
    for (const card of cards) {
      const price = parseCents(textOf(card.querySelector('[data-testid="price"]')))
      if (price === null) return { status: 'missing_price', message: '商品缺少一次性总价，未进行猜测' }
      const link = card.querySelector<HTMLAnchorElement>('a')
      const shopName = textOf(card.querySelector('[data-testid="shop"]')) || '拼多多店铺'
      items.push({
        platform: 'pdd',
        title: textOf(card.querySelector('h2')),
        platform_product_id: card.getAttribute('data-goods-id') ?? '',
        platform_sku_id: card.getAttribute('data-sku-id') ?? '',
        platform_shop_id: shopName,
        shop_name: shopName,
        shop_type: shopName.includes('授权') ? 'authorized' : 'third_party',
        product_url: link?.href ?? '',
        sale_price_cents: price,
        captured_at: new Date().toISOString(),
      })
    }
    return { status: 'ok', items }
  },
}
