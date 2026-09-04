import { CommandExecutionError } from '@jackwener/opencli/errors'
import { cli, Strategy } from '@jackwener/opencli/registry'

import { CheckoutCommandError, runCheckoutPreview } from './lib/jd-checkout-runner.js'
import { pageFailureCode } from './lib/jd-page.js'
import { chooseRegion } from './verify.js'


const COLUMNS = [
  'platform_sku_id',
  'title',
  'product_url',
  'shop_name',
  'shop_type',
  'entry_mode',
  'price_status',
  'quantity',
  'target_only',
  'line_original_price_cents',
  'line_sale_price_cents',
  'merchant_discount_cents',
  'ordinary_coupon_cents',
  'subsidy_amount_cents',
  'shipping_fee_cents',
  'payable_price_cents',
  'discount_summary',
  'conditional_reason',
  'unavailable_code',
  'region_confirmed',
  'cart_restored',
  'captured_at',
]


function classifyPage(markers) {
  return pageFailureCode(markers.title, markers.bodyText)
}


cli({
  site: 'price-compare-jd',
  name: 'checkout-preview',
  description: 'Read one guarded JD checkout preview without submitting an order or payment',
  domain: 'jd.com',
  strategy: Strategy.UI,
  access: 'write',
  browser: true,
  args: [
    { name: 'sku', positional: true, required: true, help: 'JD SKU' },
    { name: 'province', required: true, help: 'Province display name' },
    { name: 'city', required: true, help: 'City display name' },
    { name: 'district', required: true, help: 'District display name' },
    { name: 'street', required: true, help: 'Street or town display name' },
    { name: 'area-id', required: true, help: 'JD four-level area ID' },
    { name: 'allow-cart-fallback', type: 'boolean', default: true, help: 'Allow isolated cart fallback' },
  ],
  columns: COLUMNS,
  func: async (page, kwargs) => {
    const sku = String(kwargs.sku ?? '')
    const areaId = String(kwargs['area-id'] ?? '')
    if (!/^\d{5,30}$/.test(sku) || !/^[1-9]\d*-[1-9]\d*-[1-9]\d*-(?:0|[1-9]\d*)$/.test(areaId)) {
      throw new CommandExecutionError('PAGE_CHANGED: 京东结算核价参数无效')
    }
    try {
      return await runCheckoutPreview(page, {
        sku,
        province: String(kwargs.province),
        city: String(kwargs.city),
        district: String(kwargs.district),
        street: String(kwargs.street),
        areaId,
        allowCartFallback: kwargs['allow-cart-fallback'] !== false,
      }, { chooseRegion, classifyPage })
    } catch (error) {
      if (error instanceof CheckoutCommandError) {
        throw new CommandExecutionError(`${error.code}: ${error.message}`)
      }
      throw error
    }
  },
})
