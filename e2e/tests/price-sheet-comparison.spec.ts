import { expect, test } from '@playwright/test'


const ONE_PIXEL_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGP8//8/AwMDEwMYAAAkBgMBXaJOiAAAAABJRU5ErkJggg==',
  'base64',
)

test('uploads, reviews, compares and restores an exact-color price sheet', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/')
  await page.getByTestId('price-sheet-tab').click()
  await page.getByTestId('price-sheet-file').setInputFiles({
    name: '9.3-iphone-price-sheet.png',
    mimeType: 'image/png',
    buffer: ONE_PIXEL_PNG,
  })

  await expect(page.getByText('2 核对识别结果', { exact: true })).toBeVisible()
  await expect(page.getByText('iPhone 17 · 256GB · 黑色', { exact: true })).toBeVisible()
  await expect(page.getByText('iPhone 17 · 256GB · 白色', { exact: true })).toBeVisible()

  await page.getByTestId('start-price-sheet').click()
  await expect(page.getByText('结算页核价', { exact: true })).toBeVisible()
  await expect(page.getByText(/候选 20\/20/)).toBeVisible()
  await expect(page.getByText('程序只读取结算预览，不会提交订单或付款。', { exact: true })).toBeVisible()
  await expect(page.getByTestId('price-sheet-low-result')).toHaveCount(1, { timeout: 90_000 })
  await expect(page.getByTestId('price-sheet-low-result')).toContainText('黑色')
  await expect(page.getByTestId('price-sheet-low-result')).toContainText('31/31')
  await expect(page.getByTestId('price-sheet-low-result')).toContainText('奥运村街道')
  await expect(page.getByTestId('price-sheet-low-result')).toContainText('结算应付')
  await expect(page.getByTestId('price-sheet-low-result')).toContainText('¥5,199')

  await page.getByRole('button', { name: /未发现更低价/ }).click()
  await expect(page.getByText('iPhone 17 · 256GB · 白色', { exact: true })).toBeVisible()
  await expect(page.getByText('仅完成 30/31，不能称为全国最低', { exact: true })).toBeVisible()

  await page.reload()
  await page.getByTestId('price-sheet-tab').click()
  await expect(page.getByTestId('price-sheet-low-result')).toHaveCount(1)
  await expect(page.getByTestId('price-sheet-low-result')).toContainText('黑色')
})


test('keeps the manual cart warning when fixture restoration fails', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('price-sheet-tab').click()
  await page.getByTestId('price-sheet-file').setInputFiles({
    name: 'cart-warning.png',
    mimeType: 'image/png',
    buffer: ONE_PIXEL_PNG,
  })
  const rows = page.locator('.price-sheet-row')
  await rows.first().getByLabel('颜色').fill('紫色')
  await rows.nth(1).getByLabel('查询').uncheck()

  await page.getByTestId('start-price-sheet').click()

  await expect(page.getByText('购物车可能未完全恢复，请人工检查', { exact: true })).toBeVisible({ timeout: 30_000 })
  await page.reload()
  await page.getByTestId('price-sheet-tab').click()
  await expect(page.getByText('购物车可能未完全恢复，请人工检查', { exact: true })).toBeVisible()
})
