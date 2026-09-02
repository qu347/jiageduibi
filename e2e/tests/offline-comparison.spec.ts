import { expect, test } from '@playwright/test'


test('compares one exact iPhone 17 SKU across three fixture platforms', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('keyword').fill('苹果17')
  await page.getByTestId('search-models').click()
  await page.getByText('iPhone 17', { exact: true }).click()
  await page.getByText('256GB', { exact: true }).click()
  await page.getByText('中国大陆国行', { exact: true }).click()
  await page.getByText('全新', { exact: true }).click()
  await page.getByTestId('confirm-variant').click()
  await page.getByTestId('run-fixture-comparison').click()

  await expect(page.getByTestId('offer-row')).toHaveCount(3)
  await expect(page.getByText(/已排除 [5-9]\d* 条干扰项/)).toBeVisible()
  await expect(page.getByText('预计国补').first()).toBeVisible()
  const prices = await page.getByTestId('comparable-price').allTextContents()
  expect(prices).toEqual([...prices].sort(
    (left, right) => Number(left.replace(/\D/g, '')) - Number(right.replace(/\D/g, '')),
  ))

  await page.reload()
  await page.getByRole('link', { name: '历史价格' }).click()
  await expect(page.getByText('历史最低价')).toBeVisible()
})
