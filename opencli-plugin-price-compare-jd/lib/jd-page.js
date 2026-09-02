const NON_TOTAL_PRICE = /月供|分期|定金|预售|起步|起价/


export function cents(value) {
  if (typeof value !== 'string') return null
  const normalized = value.replace(/\s+/g, ' ').trim()
  if (!normalized || NON_TOTAL_PRICE.test(normalized)) return null
  const match = normalized.match(/(?:￥|¥)?\s*(\d[\d,]*)(?:\.(\d{1,2}))?/)
  if (!match) return null
  const yuan = Number(match[1].replaceAll(',', ''))
  const decimal = (match[2] ?? '').padEnd(2, '0')
  const fen = decimal ? Number(decimal) : 0
  if (!Number.isSafeInteger(yuan) || !Number.isSafeInteger(fen)) return null
  const result = yuan * 100 + fen
  return result > 0 ? result : null
}


function shopType(name) {
  if (/京东自营/.test(name)) return 'self_operated'
  if (/官方旗舰店|旗舰店/.test(name)) return 'official_flagship'
  if (/授权/.test(name)) return 'authorized'
  return 'third_party'
}


export function normalizeSearchRows(rows, limit) {
  if (!Array.isArray(rows)) return []
  const maximum = Math.min(50, Math.max(1, Number(limit) || 30))
  const seen = new Set()
  const output = []

  for (const row of rows) {
    const sku = String(row?.sku ?? '').trim()
    const title = String(row?.title ?? '').replace(/\s+/g, ' ').trim()
    const price = cents(String(row?.price ?? ''))
    const rawUrl = String(row?.url ?? '').trim()
    if (!sku || !title || !price || !rawUrl || NON_TOTAL_PRICE.test(title) || seen.has(sku)) continue
    const productUrl = rawUrl.startsWith('//') ? `https:${rawUrl}` : rawUrl
    if (!/^https:\/\/item\.jd\.com\/\d+\.html(?:[?#].*)?$/.test(productUrl)) continue

    const shopName = String(row?.shop_name ?? '').replace(/\s+/g, ' ').trim() || '未知店铺'
    seen.add(sku)
    output.push({
      platform_sku_id: sku,
      title,
      product_url: productUrl,
      shop_name: shopName,
      platform_shop_id: row?.platform_shop_id ? String(row.platform_shop_id) : null,
      shop_type: shopType(shopName),
      initial_price_cents: price,
    })
    if (output.length >= maximum) break
  }
  return output
}


export function pageFailureCode(title, bodyText) {
  const pageTitle = String(title ?? '')
  const sample = String(bodyText ?? '').slice(0, 20000)
  if (/登录/.test(pageTitle) || /扫码登录|账户登录|请先登录|登录京东账号/.test(sample)) {
    return 'AUTH_REQUIRED'
  }
  if (/验证码|安全验证|滑块|拖动滑块|访问验证/.test(sample)) return 'CAPTCHA'
  if (/页面内容暂不可用|页面不存在|访问异常|系统繁忙|商品已下架/.test(sample)) return 'PAGE_CHANGED'
  return null
}


export function normalizeVerifiedOffer(raw, capturedAt = new Date().toISOString()) {
  const sku = String(raw?.sku ?? '').trim()
  const salePrice = cents(String(raw?.salePrice ?? ''))
  const title = String(raw?.title ?? '').replace(/\s+/g, ' ').trim()
  if (!sku || !title || !salePrice) return null

  const shopName = String(raw?.shopName ?? '').replace(/\s+/g, ' ').trim() || '未知店铺'
  const stockText = String(raw?.stockText ?? '')
  const shippingText = String(raw?.shippingText ?? '')
  const stockStatus = /无货|缺货|暂不支持配送|不可配送/.test(stockText)
    ? 'out_of_stock'
    : 'in_stock'
  const shippingFee = /免运费|包邮/.test(shippingText) ? 0 : (cents(shippingText) ?? 0)

  return {
    platform_sku_id: sku,
    title,
    product_url: `https://item.jd.com/${sku}.html`,
    shop_name: shopName,
    platform_shop_id: raw?.shopId ? String(raw.shopId) : null,
    shop_type: shopType(shopName),
    listed_price_cents: cents(String(raw?.listedPrice ?? '')),
    sale_price_cents: salePrice,
    merchant_discount_cents: 0,
    platform_coupon_cents: 0,
    member_discount_cents: 0,
    payment_discount_cents: 0,
    subsidy_amount_cents: 0,
    subsidy_status: 'unknown',
    shipping_fee_cents: shippingFee,
    installation_fee_cents: 0,
    conditional_price_cents: cents(String(raw?.memberPrice ?? '')),
    stock_status: stockStatus,
    captured_at: capturedAt,
  }
}
