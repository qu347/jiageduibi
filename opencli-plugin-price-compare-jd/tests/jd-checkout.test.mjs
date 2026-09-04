import test from 'node:test'
import assert from 'node:assert/strict'
import { parseHTML } from 'linkedom'

import {
  actionSelector,
  cartRestored,
  extractCheckoutPreview,
  planCartIsolation,
  safetyBoundaryCode,
  snapshotCart,
} from '../lib/jd-checkout.js'
import { CheckoutCommandError, runCheckoutPreview } from '../lib/jd-checkout-runner.js'


function runAsBrowserEvaluation(fn, arg, document) {
  return Function('document', 'arg', `return (${fn.toString()})(arg)`)(document, arg)
}


test('selects allowed purchase actions but never order submission or payment controls', () => {
  const { document } = parseHTML(`
    <button id="buy">立即购买</button>
    <button id="submit">提交订单</button>
    <a id="pay" href="https://cashier.jd.com/pay">去支付</a>
  `)

  assert.equal(actionSelector('buy_now', document), '#buy')
  assert.equal(actionSelector('submit_order', document), null)
  assert.equal(actionSelector('go_checkout', document), null)
})


test('page evaluators are self-contained when serialized into the browser', () => {
  const { document } = parseHTML(`
    <button id="buy">立即购买</button>
    <div data-opencli-checkout-address>北京市 朝阳区 奥运村街道</div>
    <div data-opencli-checkout-line data-sku="1001" data-quantity="1">
      <span data-opencli-title>Apple iPhone 17</span><span data-opencli-shop>京东自营</span>
      <span data-opencli-price="sale">¥5,419</span>
    </div>
    <strong data-opencli-price="payable">¥5,419</strong>
  `)

  assert.equal(runAsBrowserEvaluation(actionSelector, 'buy_now', document), '#buy')
  assert.equal(
    runAsBrowserEvaluation(
      extractCheckoutPreview,
      { sku: '1001', district: '朝阳区', street: '奥运村街道' },
      document,
    ).priceStatus,
    'verified',
  )
  assert.deepEqual(runAsBrowserEvaluation(snapshotCart, undefined, document), { rows: [] })
})


test('rejects payment and order-success navigation boundaries', () => {
  assert.equal(
    safetyBoundaryCode({ url: 'https://cashier.jd.com/pay', title: '', bodyText: '' }),
    'SAFETY_BOUNDARY_CROSSED',
  )
  assert.equal(
    safetyBoundaryCode({ url: 'https://trade.jd.com/order/success', title: '订单提交成功', bodyText: '' }),
    'SAFETY_BOUNDARY_CROSSED',
  )
  assert.equal(
    safetyBoundaryCode({ url: 'https://trade.jd.com/shopping/order/getOrderInfo.action', title: '填写并核对订单信息', bodyText: '提交订单' }),
    null,
  )
})


test('extracts a verified one-item checkout without inferring discounts', () => {
  const { document } = parseHTML(`
    <main>
      <div data-opencli-checkout-address>北京市 朝阳区 奥运村街道</div>
      <div data-opencli-checkout-line data-sku="1001" data-quantity="1">
        <span data-opencli-title>Apple iPhone 17 256GB 黑色</span>
        <span data-opencli-shop>Apple产品京东自营旗舰店</span>
        <span data-opencli-price="original">¥5,919</span>
        <span data-opencli-price="sale">¥5,419</span>
      </div>
      <span data-opencli-price="merchant">¥0</span>
      <span data-opencli-price="coupon">¥100</span>
      <span data-opencli-price="subsidy">¥500</span>
      <span data-opencli-price="shipping">¥0</span>
      <strong data-opencli-price="payable">¥4,819</strong>
      <div data-opencli-discount-summary>优惠券 100 元；国家补贴已应用 500 元</div>
    </main>
  `)

  const result = extractCheckoutPreview({
    sku: '1001', district: '朝阳区', street: '奥运村街道',
  }, document)

  assert.deepEqual(result, {
    title: 'Apple iPhone 17 256GB 黑色',
    shopName: 'Apple产品京东自营旗舰店',
    quantity: 1,
    targetOnly: true,
    lineOriginalPriceCents: 591900,
    lineSalePriceCents: 541900,
    merchantDiscountCents: 0,
    ordinaryCouponCents: 10000,
    subsidyAmountCents: 50000,
    shippingFeeCents: 0,
    payablePriceCents: 481900,
    discountSummary: '优惠券 100 元；国家补贴已应用 500 元',
    conditionalReason: null,
    unavailableCode: null,
    priceStatus: 'verified',
    regionConfirmed: true,
  })
})


test('marks qualification-based checkout prices as conditional', () => {
  const { document } = parseHTML(`
    <div data-opencli-checkout-address>广东省 广州市 天河区 石牌街道</div>
    <div data-opencli-checkout-line data-sku="1001" data-quantity="1">
      <span data-opencli-title>Apple iPhone 17</span><span data-opencli-shop>京东自营</span>
      <span data-opencli-price="sale">¥5,419</span>
    </div>
    <strong data-opencli-price="payable">¥5,199</strong>
    <div data-opencli-discount-summary>PLUS会员专享 ¥220</div>
  `)

  const result = extractCheckoutPreview({ sku: '1001', district: '天河区', street: '石牌街道' }, document)

  assert.equal(result.priceStatus, 'conditional')
  assert.equal(result.conditionalReason, 'PLUS会员')
  assert.equal(result.ordinaryCouponCents, 0)
  assert.equal(result.subsidyAmountCents, 0)
})


test('returns explicit unavailable reasons for untrusted checkout pages', () => {
  const cases = [
    {
      html: '<div>请选择收货地址</div>',
      expected: 'checkout_address_required',
    },
    {
      html: '<div data-opencli-checkout-address>北京市 朝阳区</div><div data-opencli-checkout-line data-sku="1001" data-quantity="1"></div><b data-opencli-price="payable">¥5000</b>',
      expected: 'checkout_region_unconfirmed',
    },
    {
      html: '<div data-opencli-checkout-address>北京市 朝阳区 奥运村街道</div><div data-opencli-checkout-line data-sku="9999" data-quantity="1"></div><b data-opencli-price="payable">¥5000</b>',
      expected: 'sku_unconfirmed',
    },
    {
      html: '<div data-opencli-checkout-address>北京市 朝阳区 奥运村街道</div><div data-opencli-checkout-line data-sku="1001" data-quantity="2"></div><b data-opencli-price="payable">¥5000</b>',
      expected: 'sku_unconfirmed',
    },
    {
      html: '<div data-opencli-checkout-address>北京市 朝阳区 奥运村街道</div><div data-opencli-checkout-line data-sku="1001" data-quantity="1"></div>',
      expected: 'price_unavailable',
    },
  ]

  for (const { html, expected } of cases) {
    const { document } = parseHTML(html)
    const result = extractCheckoutPreview({ sku: '1001', district: '朝阳区', street: '奥运村街道' }, document)
    assert.equal(result.priceStatus, 'unavailable')
    assert.equal(result.unavailableCode, expected)
  }
})


test('refuses fallback when the target SKU already belongs to the user cart', () => {
  const snapshot = { rows: [{ sku: '1001', quantity: 2, selected: true }] }

  assert.deepEqual(planCartIsolation(snapshot, '1001'), {
    allowed: false,
    code: 'cart_isolation_failed',
  })
})


test('captures cart state and verifies exact restoration after removing the added SKU', () => {
  const beforeDocument = parseHTML(`
    <div data-opencli-cart-line data-sku="2002" data-quantity="2"><input type="checkbox" checked></div>
    <div data-opencli-cart-line data-sku="3003" data-quantity="1"><input type="checkbox"></div>
  `).document
  const restoredDocument = parseHTML(`
    <div data-opencli-cart-line data-sku="2002" data-quantity="2"><input type="checkbox" checked></div>
    <div data-opencli-cart-line data-sku="3003" data-quantity="1"><input type="checkbox"></div>
  `).document
  const changedDocument = parseHTML(`
    <div data-opencli-cart-line data-sku="2002" data-quantity="2"><input type="checkbox"></div>
    <div data-opencli-cart-line data-sku="1001" data-quantity="1"><input type="checkbox" checked></div>
  `).document
  const snapshot = snapshotCart(beforeDocument)

  assert.deepEqual(planCartIsolation(snapshot, '1001'), { allowed: true, code: null })
  assert.equal(cartRestored(snapshot, snapshotCart(restoredDocument), '1001'), true)
  assert.equal(cartRestored(snapshot, snapshotCart(changedDocument), '1001'), false)
})


class FakeCheckoutPage {
  constructor(destination = 'checkout') {
    this.destination = destination
    this.url = ''
    this.document = null
    this.clicks = []
    this.checkoutClickCount = 0
  }

  async goto(url) {
    this.url = url
    if (url.includes('item.jd.com')) {
      this.document = parseHTML(`
        <html><head><title>Apple iPhone 17</title></head><body>
          <div data-opencli-item data-sku="1001" data-quantity="1" data-stock="in_stock"></div>
          <button id="buy">立即购买</button>
        </body></html>
      `).document
    }
  }

  async click(selector) {
    if (this.url.includes('trade.jd.com')) this.checkoutClickCount += 1
    this.clicks.push(selector)
    if (selector === '#buy') {
      this.url = this.destination === 'cashier'
        ? 'https://cashier.jd.com/pay'
        : 'https://trade.jd.com/shopping/order/getOrderInfo.action'
      this.document = parseHTML(`
        <html><head><title>填写并核对订单信息</title></head><body>
          <div data-opencli-checkout-address>北京市 朝阳区 奥运村街道</div>
          <div data-opencli-checkout-line data-sku="1001" data-quantity="1">
            <span data-opencli-title>Apple iPhone 17 256GB 黑色</span>
            <span data-opencli-shop>京东自营</span>
            <span data-opencli-price="sale">¥5,419</span>
          </div>
          <strong data-opencli-price="payable">¥5,419</strong>
          <button>提交订单</button>
        </body></html>
      `).document
    }
  }

  async evaluate(fn, arg) {
    if (fn.name === '' && String(fn).includes('window.location.href')) return this.url
    if (fn.name === 'readPageMarkers') {
      return fn({ url: this.url }, this.document)
    }
    return fn(arg, this.document)
  }

  async wait() {}
}


test('buy-now workflow performs no click after reaching checkout', async () => {
  const page = new FakeCheckoutPage()

  const [result] = await runCheckoutPreview(page, {
    sku: '1001', province: '北京市', city: '北京市', district: '朝阳区', street: '奥运村街道',
    areaId: '1-72-55652-0', allowCartFallback: true,
  }, {
    chooseRegion: async () => {},
    clock: () => '2026-09-04T00:00:00.000Z',
  })

  assert.deepEqual(page.clicks, ['#buy'])
  assert.equal(page.checkoutClickCount, 0)
  assert.equal(result.entry_mode, 'buy_now')
  assert.equal(result.price_status, 'verified')
  assert.equal(result.quantity, 1)
  assert.equal(result.target_only, true)
  assert.equal(result.payable_price_cents, 541900)
})


test('buy-now workflow stops immediately at a payment boundary', async () => {
  const page = new FakeCheckoutPage('cashier')

  await assert.rejects(
    runCheckoutPreview(page, {
      sku: '1001', province: '北京市', city: '北京市', district: '朝阳区', street: '奥运村街道',
      areaId: '1-72-55652-0', allowCartFallback: false,
    }, { chooseRegion: async () => {} }),
    (error) => error instanceof CheckoutCommandError && error.code === 'SAFETY_BOUNDARY_CROSSED',
  )

  assert.equal(page.checkoutClickCount, 0)
})


test('workflow preserves login and captcha page failure codes', async () => {
  const page = new FakeCheckoutPage()

  await assert.rejects(
    runCheckoutPreview(page, {
      sku: '1001', province: '北京市', city: '北京市', district: '朝阳区', street: '奥运村街道',
      areaId: '1-72-55652-0', allowCartFallback: false,
    }, {
      chooseRegion: async () => {},
      classifyPage: () => 'AUTH_REQUIRED',
    }),
    (error) => error instanceof CheckoutCommandError && error.code === 'AUTH_REQUIRED',
  )
})


class FakeCartFallbackPage extends FakeCheckoutPage {
  constructor({ restoreFails = false } = {}) {
    super()
    this.restoreFails = restoreFails
    this.cartRows = [{ sku: '2002', quantity: 2, selected: true }]
  }

  renderProduct() {
    return parseHTML(`
      <html><head><title>Apple iPhone 17</title></head><body>
        <div data-opencli-item data-sku="1001" data-quantity="1" data-stock="in_stock"></div>
        <button id="add">加入购物车</button>
      </body></html>
    `).document
  }

  renderCart() {
    const rows = this.cartRows.map((row) => `
      <div data-opencli-cart-line data-sku="${row.sku}" data-quantity="${row.quantity}">
        <input id="check-${row.sku}" type="checkbox" ${row.selected ? 'checked' : ''}>
        <button id="delete-${row.sku}" data-opencli-remove>删除</button>
      </div>
    `).join('')
    return parseHTML(`<html><body>${rows}<button id="checkout">去结算</button></body></html>`).document
  }

  async goto(url) {
    this.url = url
    if (url.includes('item.jd.com')) this.document = this.renderProduct()
    if (url.includes('cart.jd.com')) this.document = this.renderCart()
  }

  async click(selector) {
    if (this.url.includes('trade.jd.com')) this.checkoutClickCount += 1
    this.clicks.push(selector)
    if (selector === '#add') {
      this.cartRows.push({ sku: '1001', quantity: 1, selected: true })
      return
    }
    if (selector.startsWith('#check-')) {
      const sku = selector.slice('#check-'.length)
      this.cartRows.find((row) => row.sku === sku).selected = !this.cartRows.find((row) => row.sku === sku).selected
      this.document = this.renderCart()
      return
    }
    if (selector === '#checkout') {
      this.url = 'https://trade.jd.com/shopping/order/getOrderInfo.action'
      this.document = parseHTML(`
        <html><body>
          <div data-opencli-checkout-address>北京市 朝阳区 奥运村街道</div>
          <div data-opencli-checkout-line data-sku="1001" data-quantity="1">
            <span data-opencli-title>Apple iPhone 17 256GB 黑色</span>
            <span data-opencli-shop>京东自营</span>
            <span data-opencli-price="sale">¥5,419</span>
          </div>
          <strong data-opencli-price="payable">¥5,419</strong>
          <button>提交订单</button>
        </body></html>
      `).document
      return
    }
    if (selector === '#delete-1001') {
      if (!this.restoreFails) this.cartRows = this.cartRows.filter((row) => row.sku !== '1001')
      this.document = this.renderCart()
    }
  }
}


test('cart fallback isolates one new row and restores the original cart in finally', async () => {
  const page = new FakeCartFallbackPage()

  const [result] = await runCheckoutPreview(page, {
    sku: '1001', province: '北京市', city: '北京市', district: '朝阳区', street: '奥运村街道',
    areaId: '1-72-55652-0', allowCartFallback: true,
  }, { chooseRegion: async () => {}, clock: () => '2026-09-04T00:00:00.000Z' })

  assert.equal(result.entry_mode, 'cart_fallback')
  assert.equal(result.cart_restored, true)
  assert.deepEqual(page.cartRows, [{ sku: '2002', quantity: 2, selected: true }])
  assert.equal(page.checkoutClickCount, 0)
  assert.deepEqual(page.clicks, ['#add', '#check-2002', '#checkout', '#delete-1001', '#check-2002'])
})


test('cart restoration failure overrides a parsed checkout result', async () => {
  const page = new FakeCartFallbackPage({ restoreFails: true })

  await assert.rejects(
    runCheckoutPreview(page, {
      sku: '1001', province: '北京市', city: '北京市', district: '朝阳区', street: '奥运村街道',
      areaId: '1-72-55652-0', allowCartFallback: true,
    }, { chooseRegion: async () => {} }),
    (error) => error instanceof CheckoutCommandError && error.code === 'CART_ISOLATION_FAILED',
  )

  assert.equal(page.checkoutClickCount, 0)
})
