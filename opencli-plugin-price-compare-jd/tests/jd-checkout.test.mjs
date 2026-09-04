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
