function normalizedText(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim()
}


export function actionSelector(kind, root = document) {
  const patterns = {
    buy_now: /^立即购买$/,
    add_cart: /^(加入购物车|加入采购车)$/,
    go_checkout: /^去结算$/,
  }
  const pattern = patterns[kind]
  if (!pattern) return null
  const candidates = Array.from(root.querySelectorAll('button, a, input[type="button"], input[type="submit"]'))
  const matches = candidates.filter((element) => {
    const label = String(element.textContent || element.value || element.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim()
    const href = String(element.getAttribute('href') || '')
    let unsafeHref = false
    try {
      const parsed = new URL(href)
      unsafeHref = /(?:^|\.)(?:cashier|pay)\.jd\.com$/.test(parsed.hostname)
    } catch {
      unsafeHref = false
    }
    return !/提交订单|确认订单|去支付|立即支付|付款/.test(label) && !unsafeHref && pattern.test(label)
  })
  if (matches.length !== 1) return null
  const element = matches[0]
  if (element.id) return `#${element.id}`
  const marker = `opencli-${kind}`
  element.setAttribute('data-opencli-action', marker)
  return `[data-opencli-action="${marker}"]`
}


export function safetyBoundaryCode(markers) {
  const url = String(markers?.url ?? '').toLowerCase()
  const title = normalizedText(markers?.title)
  const bodyText = normalizedText(markers?.bodyText).slice(0, 20000)
  if (
    /(?:^|\.)cashier\.jd\.com/.test(safeHost(url))
    || /(?:^|\.)pay\.jd\.com/.test(safeHost(url))
    || /(?:order|trade)[^?#]*(?:success|finish|complete)/.test(url)
    || /订单提交成功|支付成功|付款成功/.test(`${title} ${bodyText}`)
  ) return 'SAFETY_BOUNDARY_CROSSED'
  return null
}


function safeHost(value) {
  try {
    return new URL(value).hostname
  } catch {
    return ''
  }
}


export function extractCheckoutPreview(expected, root = document) {
  const normalize = (value) => String(value ?? '').replace(/\s+/g, ' ').trim()
  const parseMoney = (value) => {
    const normalized = normalize(value)
    if (!normalized || /月供|分期|定金|预售|起步|起价/.test(normalized)) return null
    const match = normalized.match(/(?:￥|¥)?\s*(\d[\d,]*)(?:\.(\d{1,2}))?/)
    if (!match) return null
    const yuan = Number(match[1].replaceAll(',', ''))
    const fen = Number((match[2] ?? '').padEnd(2, '0') || 0)
    if (!Number.isSafeInteger(yuan) || !Number.isSafeInteger(fen)) return null
    const result = yuan * 100 + fen
    return result > 0 ? result : null
  }
  const priceSelectors = {
    original: ['[data-opencli-price="original"]', '.price-original', '.p-price del'],
    sale: ['[data-opencli-price="sale"]', '.p-price', '.jd-price'],
    merchant: ['[data-opencli-price="merchant"]', '.merchant-discount .price', '[data-type="merchant"] .price'],
    coupon: ['[data-opencli-price="coupon"]', '.coupon-discount .price', '[data-type="coupon"] .price'],
    subsidy: ['[data-opencli-price="subsidy"]', '.subsidy-discount .price', '[data-type="subsidy"] .price'],
    shipping: ['[data-opencli-price="shipping"]', '.freight-price', '[data-type="freight"] .price'],
    payable: ['[data-opencli-price="payable"]', '#sumPayPriceId', '.pay-price', '.payment-price .price'],
  }
  const readPrice = (view, name) => {
    if (!view) return null
    const selector = priceSelectors[name].find((value) => view.querySelector(value))
    return parseMoney(selector ? view.querySelector(selector)?.textContent : '')
  }
  const bodyText = normalize(
    root.body?.textContent || root.documentElement?.textContent || root.textContent,
  ).slice(0, 20000)
  const addressText = normalize(root.querySelector(
    '[data-opencli-checkout-address], .consignee-item.item-selected .addr-detail, .consignee-item.item-selected',
  )?.textContent)
  const lines = Array.from(root.querySelectorAll(
    '[data-opencli-checkout-line], #order_ware_list .goods-item[data-sku], .order-item[data-sku]',
  ))
  const targetLines = lines.filter((line) => String(line.getAttribute('data-sku') || '') === String(expected.sku))
  const line = targetLines[0] ?? null
  const quantityText = normalize(line?.querySelector('.p-num, .quantity')?.textContent)
  const quantity = Number(line?.getAttribute('data-quantity') || quantityText.match(/\d+/)?.[0] || 0)
  const targetOnly = lines.length === 1 && targetLines.length === 1
  const regionConfirmed = addressText.includes(String(expected.district)) && addressText.includes(String(expected.street))
  const summary = normalize(root.querySelector(
    '[data-opencli-discount-summary], .discount-summary',
  )?.textContent).slice(0, 2000)
  const conditionalLabels = [
    [/PLUS|会员/, 'PLUS会员'],
    [/新人/, '新人优惠'],
    [/学生/, '学生优惠'],
    [/白条/, '白条优惠'],
    [/指定支付|银行卡|支付优惠/, '指定支付优惠'],
    [/分期|月供/, '分期优惠'],
    [/以旧换新|回收/, '以旧换新'],
  ]
  const conditionalReason = conditionalLabels.find(([pattern]) => pattern.test(summary || bodyText))?.[1] ?? null
  const base = {
    title: normalize(line?.querySelector('[data-opencli-title], .p-name, .goods-name')?.textContent),
    shopName: normalize(line?.querySelector('[data-opencli-shop], .shop-name')?.textContent),
    quantity,
    targetOnly,
    lineOriginalPriceCents: readPrice(line || root, 'original'),
    lineSalePriceCents: readPrice(line || root, 'sale'),
    merchantDiscountCents: readPrice(root, 'merchant') ?? 0,
    ordinaryCouponCents: readPrice(root, 'coupon') ?? 0,
    subsidyAmountCents: readPrice(root, 'subsidy') ?? 0,
    shippingFeeCents: readPrice(root, 'shipping') ?? 0,
    payablePriceCents: readPrice(root, 'payable'),
    discountSummary: summary,
    conditionalReason,
    unavailableCode: null,
    priceStatus: conditionalReason ? 'conditional' : 'verified',
    regionConfirmed,
  }

  if (/请选择收货地址|新增收货地址|请填写收货地址/.test(bodyText)) {
    return { ...base, priceStatus: 'unavailable', unavailableCode: 'checkout_address_required' }
  }
  if (!regionConfirmed) return { ...base, priceStatus: 'unavailable', unavailableCode: 'checkout_region_unconfirmed' }
  if (!targetOnly || quantity !== 1) return { ...base, priceStatus: 'unavailable', unavailableCode: 'sku_unconfirmed' }
  if (base.payablePriceCents === null) return { ...base, priceStatus: 'unavailable', unavailableCode: 'price_unavailable' }
  return base
}


export function snapshotCart(input, evaluatedRoot) {
  const root = evaluatedRoot || (input?.querySelectorAll ? input : document)
  return {
    rows: Array.from(root.querySelectorAll(
      '[data-opencli-cart-line], .item-item[data-sku], [class*="cart-item"][data-sku]',
    )).map((line) => ({
      sku: String(line.getAttribute('data-sku') || ''),
      quantity: Number(
        line.getAttribute('data-quantity')
        || line.querySelector('input.itxt, [class*="quantity"] input')?.value
        || 0,
      ),
      selected: (() => {
        const checkbox = line.querySelector('input[type="checkbox"]')
        return typeof checkbox?.checked === 'boolean' ? checkbox.checked : Boolean(checkbox?.hasAttribute('checked'))
      })(),
    })).filter((row) => row.sku).sort((left, right) => left.sku.localeCompare(right.sku)),
  }
}


export function planCartIsolation(snapshot, sku) {
  const exists = snapshot?.rows?.some((row) => row.sku === String(sku))
  return exists
    ? { allowed: false, code: 'cart_isolation_failed' }
    : { allowed: true, code: null }
}


export function cartRestored(before, current, addedSku) {
  if (current?.rows?.some((row) => row.sku === String(addedSku))) return false
  return JSON.stringify(before?.rows ?? []) === JSON.stringify(current?.rows ?? [])
}


export function cartSelectionSelectors(sku, root = document) {
  const lines = Array.from(root.querySelectorAll(
    '[data-opencli-cart-line], .item-item[data-sku], [class*="cart-item"][data-sku]',
  ))
  const targets = lines.filter((line) => String(line.getAttribute('data-sku') || '') === String(sku))
  if (targets.length !== 1 || Number(targets[0].getAttribute('data-quantity') || targets[0].querySelector('input.itxt, [class*="quantity"] input')?.value || 0) !== 1) {
    return { valid: false, selectors: [] }
  }
  const selectors = []
  for (const line of lines) {
    const checkbox = line.querySelector('input[type="checkbox"]')
    if (!checkbox) return { valid: false, selectors: [] }
    const shouldSelect = line === targets[0]
    const selected = typeof checkbox.checked === 'boolean' ? checkbox.checked : checkbox.hasAttribute('checked')
    if (selected === shouldSelect) continue
    if (checkbox.id) selectors.push(`#${checkbox.id}`)
    else {
      const marker = `isolate-${line.getAttribute('data-sku')}`
      checkbox.setAttribute('data-opencli-cart-toggle', marker)
      selectors.push(`[data-opencli-cart-toggle="${marker}"]`)
    }
  }
  return { valid: true, selectors }
}


export function cartDeleteSelector(sku, root = document) {
  const lines = Array.from(root.querySelectorAll(
    '[data-opencli-cart-line], .item-item[data-sku], [class*="cart-item"][data-sku]',
  )).filter((line) => String(line.getAttribute('data-sku') || '') === String(sku))
  if (lines.length !== 1) return null
  const actions = Array.from(lines[0].querySelectorAll(
    '[data-opencli-remove], .cart-remove, .p-ops a, button, a',
  )).filter((element) => /删除|移除/.test(String(element.textContent || element.getAttribute('aria-label') || '')))
  if (actions.length !== 1) return null
  const element = actions[0]
  if (element.id) return `#${element.id}`
  element.setAttribute('data-opencli-cart-remove', String(sku))
  return `[data-opencli-cart-remove="${sku}"]`
}


export function cartRestoreSelectors(input, root = document) {
  const before = input?.before?.rows ?? []
  const addedSku = String(input?.addedSku ?? '')
  const lines = Array.from(root.querySelectorAll(
    '[data-opencli-cart-line], .item-item[data-sku], [class*="cart-item"][data-sku]',
  ))
  if (lines.some((line) => String(line.getAttribute('data-sku') || '') === addedSku)) {
    return { valid: false, selectors: [] }
  }
  if (lines.length !== before.length) return { valid: false, selectors: [] }
  const selectors = []
  for (const original of before) {
    const matches = lines.filter((line) => String(line.getAttribute('data-sku') || '') === original.sku)
    if (matches.length !== 1) return { valid: false, selectors: [] }
    const line = matches[0]
    const quantity = Number(line.getAttribute('data-quantity') || line.querySelector('input.itxt, [class*="quantity"] input')?.value || 0)
    const checkbox = line.querySelector('input[type="checkbox"]')
    if (quantity !== original.quantity || !checkbox) return { valid: false, selectors: [] }
    const selected = typeof checkbox.checked === 'boolean' ? checkbox.checked : checkbox.hasAttribute('checked')
    if (selected === original.selected) continue
    if (checkbox.id) selectors.push(`#${checkbox.id}`)
    else {
      const marker = `restore-${original.sku}`
      checkbox.setAttribute('data-opencli-cart-toggle', marker)
      selectors.push(`[data-opencli-cart-toggle="${marker}"]`)
    }
  }
  return { valid: true, selectors }
}
