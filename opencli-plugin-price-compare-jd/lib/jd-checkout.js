import { cents } from './jd-page.js'


const FORBIDDEN_ACTION = /提交订单|确认订单|去支付|立即支付|付款/
const ACTION_LABELS = {
  buy_now: /^立即购买$/,
  add_cart: /^(加入购物车|加入采购车)$/,
  go_checkout: /^去结算$/,
}
const CONDITIONAL_LABELS = [
  [/PLUS|会员/, 'PLUS会员'],
  [/新人/, '新人优惠'],
  [/学生/, '学生优惠'],
  [/白条/, '白条优惠'],
  [/指定支付|银行卡|支付优惠/, '指定支付优惠'],
  [/分期|月供/, '分期优惠'],
  [/以旧换新|回收/, '以旧换新'],
]


function normalizedText(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim()
}


function selectorFor(element, kind) {
  if (element.id) return `#${element.id}`
  const marker = `opencli-${kind}`
  element.setAttribute('data-opencli-action', marker)
  return `[data-opencli-action="${marker}"]`
}


export function actionSelector(kind, root = document) {
  const pattern = ACTION_LABELS[kind]
  if (!pattern) return null
  const candidates = Array.from(root.querySelectorAll('button, a, input[type="button"], input[type="submit"]'))
  const matches = candidates.filter((element) => {
    const label = normalizedText(element.textContent || element.value || element.getAttribute('aria-label'))
    const href = String(element.getAttribute('href') || '')
    return !FORBIDDEN_ACTION.test(label) && !safetyBoundaryCode({ url: href, title: '', bodyText: '' }) && pattern.test(label)
  })
  return matches.length === 1 ? selectorFor(matches[0], kind) : null
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


function price(root, name) {
  return cents(normalizedText(root.querySelector(`[data-opencli-price="${name}"]`)?.textContent))
}


function unavailable(base, code) {
  return {
    ...base,
    priceStatus: 'unavailable',
    unavailableCode: code,
  }
}


export function extractCheckoutPreview(expected, root = document) {
  const bodyText = normalizedText(
    root.body?.textContent || root.documentElement?.textContent || root.textContent,
  ).slice(0, 20000)
  const addressText = normalizedText(root.querySelector('[data-opencli-checkout-address]')?.textContent)
  const lines = Array.from(root.querySelectorAll('[data-opencli-checkout-line]'))
  const targetLines = lines.filter((line) => String(line.getAttribute('data-sku') || '') === String(expected.sku))
  const line = targetLines[0] ?? null
  const quantity = Number(line?.getAttribute('data-quantity') || 0)
  const targetOnly = lines.length === 1 && targetLines.length === 1
  const regionConfirmed = addressText.includes(String(expected.district)) && addressText.includes(String(expected.street))
  const summary = normalizedText(root.querySelector('[data-opencli-discount-summary]')?.textContent).slice(0, 2000)
  const conditionalReason = CONDITIONAL_LABELS.find(([pattern]) => pattern.test(summary || bodyText))?.[1] ?? null
  const base = {
    title: normalizedText(line?.querySelector('[data-opencli-title]')?.textContent),
    shopName: normalizedText(line?.querySelector('[data-opencli-shop]')?.textContent),
    quantity,
    targetOnly,
    lineOriginalPriceCents: price(line || root, 'original'),
    lineSalePriceCents: price(line || root, 'sale'),
    merchantDiscountCents: price(root, 'merchant') ?? 0,
    ordinaryCouponCents: price(root, 'coupon') ?? 0,
    subsidyAmountCents: price(root, 'subsidy') ?? 0,
    shippingFeeCents: price(root, 'shipping') ?? 0,
    payablePriceCents: price(root, 'payable'),
    discountSummary: summary,
    conditionalReason,
    unavailableCode: null,
    priceStatus: conditionalReason ? 'conditional' : 'verified',
    regionConfirmed,
  }

  if (/请选择收货地址|新增收货地址|请填写收货地址/.test(bodyText)) {
    return unavailable(base, 'checkout_address_required')
  }
  if (!regionConfirmed) return unavailable(base, 'checkout_region_unconfirmed')
  if (!targetOnly || quantity !== 1) return unavailable(base, 'sku_unconfirmed')
  if (base.payablePriceCents === null) return unavailable(base, 'price_unavailable')
  return base
}


export function snapshotCart(root = document) {
  return {
    rows: Array.from(root.querySelectorAll('[data-opencli-cart-line]')).map((line) => ({
      sku: String(line.getAttribute('data-sku') || ''),
      quantity: Number(line.getAttribute('data-quantity') || 0),
      selected: Boolean(line.querySelector('input[type="checkbox"]')?.checked),
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
