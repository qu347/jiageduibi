import {
  actionSelector,
  cartDeleteSelector,
  cartRestored,
  cartRestoreSelectors,
  cartSelectionSelectors,
  extractCheckoutPreview,
  planCartIsolation,
  safetyBoundaryCode,
  snapshotCart,
} from './jd-checkout.js'


export class CheckoutCommandError extends Error {
  constructor(code, message) {
    super(message)
    this.name = 'CheckoutCommandError'
    this.code = code
  }
}


export function readPageMarkers(input = {}, root = document) {
  return {
    url: String(input?.url ?? root.defaultView?.location?.href ?? ''),
    title: String(root.title ?? ''),
    bodyText: String(root.body?.innerText || root.body?.textContent || '').slice(0, 20000),
  }
}


export function extractItemState(expectedSku, root = document) {
  const declaredMarker = root.querySelector('[data-opencli-item]')
  const matchingMarker = root.querySelector(`[data-sku="${String(expectedSku)}"]`)
  const marker = declaredMarker || matchingMarker
  const quantityInput = root.querySelector('#buy-num, .choose-amount input, [class*="quantity"] input')
  const sku = String(marker?.getAttribute('data-sku') || expectedSku)
  const quantity = Number(marker?.getAttribute('data-quantity') || quantityInput?.value || 1)
  const bodyText = String(root.body?.innerText || root.body?.textContent || '')
  const stock = marker?.getAttribute('data-stock') || (/无货|缺货|不可配送/.test(bodyText) ? 'out_of_stock' : 'in_stock')
  return { sku, expectedSku: String(expectedSku), quantity, stock }
}


function shopType(name) {
  if (/京东自营/.test(name)) return 'self_operated'
  if (/官方旗舰店|旗舰店/.test(name)) return 'official_flagship'
  if (/授权/.test(name)) return 'authorized'
  return 'third_party'
}


function outputRow(args, entryMode, raw, cartRestored, capturedAt) {
  return {
    platform_sku_id: String(args.sku),
    title: raw.title || `京东商品 ${args.sku}`,
    product_url: `https://item.jd.com/${args.sku}.html`,
    shop_name: raw.shopName || '未知店铺',
    shop_type: shopType(raw.shopName || ''),
    entry_mode: entryMode,
    price_status: raw.priceStatus,
    quantity: raw.quantity,
    target_only: raw.targetOnly,
    line_original_price_cents: raw.lineOriginalPriceCents,
    line_sale_price_cents: raw.lineSalePriceCents,
    merchant_discount_cents: raw.merchantDiscountCents,
    ordinary_coupon_cents: raw.ordinaryCouponCents,
    subsidy_amount_cents: raw.subsidyAmountCents,
    shipping_fee_cents: raw.shippingFeeCents,
    payable_price_cents: raw.payablePriceCents,
    discount_summary: raw.discountSummary,
    conditional_reason: raw.conditionalReason,
    unavailable_code: raw.unavailableCode,
    region_confirmed: raw.regionConfirmed,
    cart_restored: cartRestored,
    captured_at: capturedAt,
  }
}


async function markers(page) {
  const url = await page.evaluate(() => window.location.href)
  return page.evaluate(readPageMarkers, { url })
}


function ensureSafe(pageMarkers, classifyPage = () => null) {
  const code = safetyBoundaryCode(pageMarkers)
  if (code) throw new CheckoutCommandError(code, '检测到订单或付款安全边界')
  const pageFailure = classifyPage(pageMarkers)
  if (pageFailure) throw new CheckoutCommandError(pageFailure, '京东页面当前不可用于结算核价')
}


function isCheckoutPreviewUrl(url) {
  const value = String(url).toLowerCase()
  return /trade\.jd\.com/.test(value) && /shopping\/order|getorderinfo/.test(value)
}


function isExpectedItemUrl(url, sku) {
  try {
    const parsed = new URL(String(url))
    return parsed.hostname === 'item.jd.com' && parsed.pathname === `/${sku}.html`
  } catch {
    return false
  }
}


async function restoreCart(page, snapshot, sku, classifyPage) {
  await page.goto('https://cart.jd.com/cart_index')
  ensureSafe(await markers(page), classifyPage)
  const remove = await page.evaluate(cartDeleteSelector, String(sku))
  if (!remove) return false
  await page.click(remove)
  await page.wait(0.3)
  const restore = await page.evaluate(cartRestoreSelectors, { before: snapshot, addedSku: String(sku) })
  if (!restore.valid) return false
  for (const selector of restore.selectors) {
    await page.click(selector)
  }
  const current = await page.evaluate(snapshotCart)
  return cartRestored(snapshot, current, String(sku))
}


async function runCartFallback(page, args, productUrl, clock, classifyPage) {
  await page.goto('https://cart.jd.com/cart_index')
  ensureSafe(await markers(page), classifyPage)
  const before = await page.evaluate(snapshotCart)
  if (!planCartIsolation(before, String(args.sku)).allowed) {
    await page.goto(productUrl)
    throw new CheckoutCommandError('CART_ISOLATION_FAILED', '目标 SKU 已存在于用户购物车')
  }

  await page.goto(productUrl)
  const addCart = await page.evaluate(actionSelector, 'add_cart')
  if (!addCart) {
    throw new CheckoutCommandError('BUY_NOW_UNAVAILABLE', '商品没有可安全使用的购买或加购入口')
  }

  let cartMutated = false
  let restored = false
  try {
    await page.click(addCart)
    cartMutated = true
    await page.goto('https://cart.jd.com/cart_index')
    ensureSafe(await markers(page), classifyPage)
    const isolation = await page.evaluate(cartSelectionSelectors, String(args.sku))
    if (!isolation.valid) {
      throw new CheckoutCommandError('CART_ISOLATION_FAILED', '无法唯一隔离本次新增购物车行')
    }
    for (const selector of isolation.selectors) {
      await page.click(selector)
    }
    const goCheckout = await page.evaluate(actionSelector, 'go_checkout')
    if (!goCheckout) {
      throw new CheckoutCommandError('CART_ISOLATION_FAILED', '找不到安全的去结算入口')
    }
    await page.click(goCheckout)
    await page.wait(0.5)
    const checkoutMarkers = await markers(page)
    ensureSafe(checkoutMarkers, classifyPage)
    if (!isCheckoutPreviewUrl(checkoutMarkers.url)) {
      throw new CheckoutCommandError('PAGE_CHANGED', '购物车结算没有进入结算预览')
    }
    const raw = await page.evaluate(extractCheckoutPreview, {
      sku: String(args.sku), district: String(args.district), street: String(args.street),
    })
    return [outputRow(args, 'cart_fallback', raw, true, clock())]
  } finally {
    if (cartMutated) restored = await restoreCart(page, before, args.sku, classifyPage)
    await page.goto(productUrl)
    if (cartMutated && !restored) {
      throw new CheckoutCommandError('CART_ISOLATION_FAILED', '购物车未能恢复，请人工检查')
    }
  }
}


export async function runCheckoutPreview(page, args, dependencies = {}) {
  const chooseRegion = dependencies.chooseRegion
  const clock = dependencies.clock ?? (() => new Date().toISOString())
  const classifyPage = dependencies.classifyPage ?? (() => null)
  if (typeof chooseRegion !== 'function') {
    throw new CheckoutCommandError('PAGE_CHANGED', '京东地区选择能力不可用')
  }
  const productUrl = `https://item.jd.com/${args.sku}.html`
  await page.goto(productUrl)
  const initialMarkers = await markers(page)
  ensureSafe(initialMarkers, classifyPage)
  if (!isExpectedItemUrl(initialMarkers.url, args.sku)) {
    throw new CheckoutCommandError('SKU_UNCONFIRMED', '商品页 URL 与目标 SKU 不一致')
  }
  await chooseRegion(page, args.areaId, args.province, args.city, args.district, args.street)
  const regionalMarkers = await markers(page)
  ensureSafe(regionalMarkers, classifyPage)
  if (!isExpectedItemUrl(regionalMarkers.url, args.sku)) {
    throw new CheckoutCommandError('SKU_UNCONFIRMED', '切换地区后商品页 URL 与目标 SKU 不一致')
  }

  const item = await page.evaluate(extractItemState, String(args.sku))
  if (item.sku !== String(args.sku) || item.quantity !== 1) {
    throw new CheckoutCommandError('SKU_UNCONFIRMED', '商品页无法确认目标 SKU 或数量 1')
  }
  if (item.stock !== 'in_stock') {
    return [outputRow(args, 'buy_now', {
      title: '', shopName: '', quantity: 0, targetOnly: false,
      lineOriginalPriceCents: null, lineSalePriceCents: null,
      merchantDiscountCents: 0, ordinaryCouponCents: 0, subsidyAmountCents: 0,
      shippingFeeCents: 0, payablePriceCents: null, discountSummary: '',
      conditionalReason: null, unavailableCode: 'price_unavailable',
      priceStatus: 'unavailable', regionConfirmed: false,
    }, true, clock())]
  }

  const buyNow = await page.evaluate(actionSelector, 'buy_now')
  if (!buyNow) {
    if (args.allowCartFallback) {
      return runCartFallback(page, args, productUrl, clock, classifyPage)
    }
    throw new CheckoutCommandError('BUY_NOW_UNAVAILABLE', '商品没有可安全使用的立即购买入口')
  }

  try {
    await page.click(buyNow)
    await page.wait(0.5)
    const checkoutMarkers = await markers(page)
    ensureSafe(checkoutMarkers, classifyPage)
    if (!isCheckoutPreviewUrl(checkoutMarkers.url)) {
      throw new CheckoutCommandError('PAGE_CHANGED', '立即购买后没有进入结算预览')
    }
    const raw = await page.evaluate(extractCheckoutPreview, {
      sku: String(args.sku),
      district: String(args.district),
      street: String(args.street),
    })
    return [outputRow(args, 'buy_now', raw, true, clock())]
  } finally {
    await page.goto(productUrl)
  }
}
