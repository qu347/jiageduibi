import { describe, expect, it, vi } from 'vitest'

import { installCaptureListener } from '../src/content/capture'


function fakeRuntime() {
  const listeners: Array<(
    message: { type?: string },
    sender: unknown,
    sendResponse: (value: unknown) => void,
  ) => boolean> = []
  return {
    listeners,
    runtime: {
      onMessage: {
        addListener: vi.fn((listener: typeof listeners[number]) => listeners.push(listener)),
      },
    },
  }
}


describe('capture listener installation', () => {
  it('installs once per document target and returns capture results', () => {
    const first = fakeRuntime()
    const firstTarget = {}
    const parseResult = {
      status: 'ok' as const,
      items: [{
        platform: 'jd' as const,
        title: 'Apple iPhone 17 256GB',
        platform_product_id: 'product-1',
        platform_sku_id: 'sku-1',
        platform_shop_id: 'shop-1',
        shop_name: '京东自营',
        shop_type: 'self_operated' as const,
        product_url: 'https://item.jd.com/1.html',
        sale_price_cents: 509900,
        captured_at: '2026-09-02T00:00:00Z',
      }],
    }
    const capture = vi.fn(() => parseResult)

    installCaptureListener(first.runtime, capture, firstTarget)
    installCaptureListener(first.runtime, capture, firstTarget)

    expect(first.runtime.onMessage.addListener).toHaveBeenCalledOnce()
    const sendResponse = vi.fn()
    expect(first.listeners[0]({ type: 'CAPTURE_PAGE' }, {}, sendResponse)).toBe(false)
    expect(sendResponse).toHaveBeenCalledWith(parseResult)

    const secondTarget = {}
    installCaptureListener(first.runtime, capture, secondTarget)
    expect(first.runtime.onMessage.addListener).toHaveBeenCalledTimes(2)
  })
})
