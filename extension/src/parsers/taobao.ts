import {
  pageFailure,
  parseCents,
  textOf,
  type PlatformParser,
  type RawOfferCandidate,
} from './base'


export const taobaoParser: PlatformParser = {
  platform: 'taobao',
  adapterVersion: 'fixture-v1',
  canHandle: (url) => url.hostname === 's.taobao.com',
  parse(document) {
    const failure = pageFailure(document)
    if (failure) return failure
    const cards = [...document.querySelectorAll('#mainsrp-itemlist .item')]
    if (!cards.length) return { status: 'unsupported', message: '当前淘宝页面没有可识别的商品列表' }
    const items: RawOfferCandidate[] = []
    for (const card of cards) {
      const price = parseCents(textOf(card.querySelector('.price')))
      if (price === null) return { status: 'missing_price', message: '商品缺少一次性总价，未进行猜测' }
      const link = card.querySelector<HTMLAnchorElement>('.pic-link')
      const shopName = textOf(card.querySelector('.shop')) || '淘宝店铺'
      items.push({
        platform: 'taobao',
        title: textOf(link),
        platform_product_id: card.getAttribute('data-nid') ?? '',
        platform_sku_id: card.getAttribute('data-sku') ?? '',
        platform_shop_id: shopName,
        shop_name: shopName,
        shop_type: shopName.includes('官方旗舰') ? 'official_flagship' : 'third_party',
        product_url: link?.href ?? '',
        sale_price_cents: price,
        captured_at: new Date().toISOString(),
      })
    }
    return { status: 'ok', items }
  },
}
