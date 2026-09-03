const NON_TOTAL_PRICE = /月供|分期|定金|预售|起步|起价/
const NON_NEW_PRODUCT = /二手|准新机|资源机|翻新机|官换机|展示机/


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


export function waitForSearchResults(page, timeout = 10) {
  return page.wait({
    selector: '#J_goodsList .gl-item, .plugin_goodsCardWrapper[data-sku]',
    timeout,
  })
}


export function regionOpenerSelector(root = document) {
  const candidates = [
    '#area-2026',
    '#area-selector',
    '.ui-area-text',
    '.delivery-address',
    '[class*="address"]',
  ]
  const view = root.defaultView
  const layoutAvailable = Number.isFinite(view?.innerWidth)
  const visible = (element) => {
    const style = typeof view?.getComputedStyle === 'function'
      ? view.getComputedStyle(element)
      : null
    const rect = typeof element.getBoundingClientRect === 'function'
      ? element.getBoundingClientRect()
      : null
    return style?.display !== 'none'
      && style?.visibility !== 'hidden'
      && (!layoutAvailable || !rect || rect.width > 0 || rect.height > 0)
  }

  for (const selector of candidates) {
    const matches = Array.from(root.querySelectorAll(selector))
    const element = matches.find(visible)
    if (!element) continue
    if (element.id) return `#${element.id}`
    if (matches.length === 1) return selector

    const path = []
    let current = element
    while (current && current !== root.body) {
      const siblings = Array.from(current.parentElement?.children || []).filter(
        (sibling) => sibling.tagName === current.tagName,
      )
      path.unshift(`${current.tagName.toLowerCase()}:nth-of-type(${siblings.indexOf(current) + 1})`)
      current = current.parentElement
    }
    return `body > ${path.join(' > ')}`
  }
  return null
}


export function extractSearchRows(limit, root = document) {
  const maximum = Math.min(50, Math.max(1, Number(limit) || 30))
  const legacyCards = Array.from(root.querySelectorAll('#J_goodsList .gl-item'))
  const currentCards = Array.from(root.querySelectorAll('.plugin_goodsCardWrapper[data-sku]'))
  const cards = legacyCards.length ? legacyCards : currentCards

  return cards.slice(0, maximum).map((node) => {
    const sku = node.getAttribute('data-sku') || ''
    const legacyLink = node.querySelector('.p-name a')
    const currentTitle = node.querySelector('[class*="_goods_title_container_"] [title]')
    const shop = node.querySelector(
      '.p-shop a, [class*="_name_"] [class*="_limit_"]',
    )
    return {
      sku,
      title: legacyLink?.textContent || currentTitle?.getAttribute('title') || currentTitle?.textContent || '',
      price: node.querySelector('.p-price i, [class*="_price_"]')?.textContent || '',
      url: legacyLink?.getAttribute('href') || (sku ? `https://item.jd.com/${sku}.html` : ''),
      shop_name: shop?.textContent || '未知店铺',
      platform_shop_id: shop?.getAttribute('data-shopid') || null,
    }
  })
}


export function regionLabelCandidates(value) {
  const label = String(value ?? '').replace(/\s+/g, '').trim()
  const short = label.replace(
    /(?:特别行政区|(?:壮族|回族|维吾尔)?自治区|自治州|地区|省|市|区|县|旗)$/,
    '',
  )
  return short && short !== label ? [label, short] : [label]
}


export function regionListLoading(root = document) {
  return Boolean(root.querySelector('[class*="jd_area_wrap_"] [class*="loading"]'))
}


export function extractVerifiedOffer(itemSku, root = document) {
  const text = (...selectors) => {
    for (const selector of selectors) {
      const value = root.querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim()
      if (value) return value
    }
    return ''
  }
  const shop = root.querySelector('.top-name, .name a, .J-hove-wrap a')
  const subsidy = Array.from(root.querySelectorAll('.floor-item')).find(
    (node) => /国家补贴|政府补贴|国补/.test(node.textContent || ''),
  )

  return {
    sku: String(itemSku),
    title: text('.sku-title-name', '.sku-name', '.itemInfo-wrap h1'),
    shopName: shop?.getAttribute('title') || shop?.textContent?.replace(/\s+/g, ' ').trim() || '未知店铺',
    shopId: shop?.getAttribute('data-shopid') || shop?.getAttribute('data-id') || null,
    salePrice: text('.product-price--value', '.summary-price .p-price', '.p-price .price'),
    listedPrice: text('.product-price--gray-line-through', '.summary-price .del', '.origin-price'),
    stockText: text('.logistics-delivery-time', '#store-prompt', '#J-stock', '.store-prompt'),
    shippingText: text('.logistics-service', '#summary-service', '.delivery'),
    memberPrice: text('.plus-price', '[class*="member-price"]'),
    subsidyText: subsidy?.textContent?.replace(/\s+/g, ' ').trim() || '',
  }
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
    if (
      !sku
      || !title
      || !price
      || !rawUrl
      || NON_TOTAL_PRICE.test(title)
      || NON_NEW_PRODUCT.test(title)
      || seen.has(sku)
    ) continue
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


export function searchCandidatesToVerifiedOffers(candidates, allowedSkus, capturedAt) {
  if (!Array.isArray(candidates) || !Array.isArray(allowedSkus)) return []
  const allowed = new Set(allowedSkus.map((sku) => String(sku)))
  return candidates
    .filter((candidate) => allowed.has(candidate.platform_sku_id))
    .map((candidate) => ({
      platform_sku_id: candidate.platform_sku_id,
      title: candidate.title,
      product_url: candidate.product_url,
      shop_name: candidate.shop_name,
      platform_shop_id: candidate.platform_shop_id,
      shop_type: candidate.shop_type,
      listed_price_cents: null,
      sale_price_cents: candidate.initial_price_cents,
      merchant_discount_cents: 0,
      platform_coupon_cents: 0,
      member_discount_cents: 0,
      payment_discount_cents: 0,
      subsidy_amount_cents: 0,
      subsidy_status: 'unknown',
      shipping_fee_cents: 0,
      installation_fee_cents: 0,
      conditional_price_cents: null,
      stock_status: 'in_stock',
      captured_at: capturedAt,
    }))
}


export function pageFailureCode(title, bodyText) {
  const pageTitle = String(title ?? '')
  const sample = String(bodyText ?? '').slice(0, 20000)
  if (/登录/.test(pageTitle) || /扫码登录|账户登录|请先登录|登录京东账号/.test(sample)) {
    return 'AUTH_REQUIRED'
  }
  if (/验证码|安全验证|滑块|拖动滑块|访问验证/.test(sample)) return 'CAPTCHA'
  if (/访问频繁导致无法搜索|由于访问频繁|操作过于频繁/.test(sample)) return 'RATE_LIMITED'
  if (/网络异常导致无法搜索|网络异常|网络错误|加载失败/.test(sample)) return 'NETWORK_ERROR'
  if (/暂时无法展示该商品的信息|页面内容暂不可用|页面不存在|访问异常|系统繁忙|商品已下架/.test(sample)) {
    return 'PAGE_CHANGED'
  }
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
  const subsidyText = String(raw?.subsidyText ?? '')
  const subsidyAmount = /国家补贴|政府补贴|国补/.test(subsidyText) ? cents(subsidyText) : null
  const stockStatus = /无货|缺货|暂不支持配送|不可配送/.test(stockText)
    ? 'out_of_stock'
    : 'in_stock'
  const shippingFee = /免(?:基础)?运费|包邮/.test(shippingText) ? 0 : (cents(shippingText) ?? 0)

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
    subsidy_amount_cents: subsidyAmount ?? 0,
    subsidy_status: subsidyAmount ? 'confirmed' : 'unknown',
    shipping_fee_cents: shippingFee,
    installation_fee_cents: 0,
    conditional_price_cents: cents(String(raw?.memberPrice ?? '')),
    stock_status: stockStatus,
    captured_at: capturedAt,
  }
}
