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
  await expect(page.getByText('4 查看结果', { exact: true })).toBeVisible({ timeout: 90_000 })
  await expect(page.getByTestId('price-sheet-low-result')).toHaveCount(1)
  await expect(page.getByTestId('price-sheet-low-result')).toContainText('黑色')
  await expect(page.getByTestId('price-sheet-low-result')).toContainText('31/31')
  await expect(page.getByTestId('price-sheet-low-result')).toContainText('奥运村街道')

  await page.getByRole('button', { name: /未发现更低价/ }).click()
  await expect(page.getByText('iPhone 17 · 256GB · 白色', { exact: true })).toBeVisible()
  await expect(page.getByText('未发现低于今日价的商品', { exact: true })).toBeVisible()

  await page.reload()
  await page.getByTestId('price-sheet-tab').click()
  await expect(page.getByTestId('price-sheet-low-result')).toHaveCount(1)
  await expect(page.getByTestId('price-sheet-low-result')).toContainText('黑色')
})
