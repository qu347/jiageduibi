import { expect, test } from '@playwright/test'


test('runs, pauses, resumes and restores a 31-region automatic JD collection', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/')
  await page.getByTestId('keyword').fill('苹果17')
  await page.getByTestId('search-models').click()
  await page.getByText('iPhone 17', { exact: true }).click()
  await page.getByText('256GB', { exact: true }).click()
  await page.getByText('中国大陆国行', { exact: true }).click()
  await page.getByText('全新', { exact: true }).click()
  await page.getByTestId('confirm-variant').click()

  await expect(page.getByText('自动采集环境可用')).toBeVisible()
  await page.getByTestId('start-automatic-collection').click()
  await expect(page.getByTestId('automatic-progress')).toContainText('/31')
  await page.getByTestId('pause-automatic-collection').click()
  await expect(page.getByText('已暂停', { exact: true })).toBeVisible({ timeout: 15_000 })

  await page.getByTestId('resume-automatic-collection').click()
  await expect(page.getByTestId('automatic-progress')).toContainText('已核验 31/31', { timeout: 90_000 })
  await expect(page.getByText('本次已采集范围最低价')).toBeVisible()
  await expect(page.getByTestId('offer-row')).toHaveCount(155)

  await page.reload()
  await expect(page.getByTestId('automatic-progress')).toContainText('已核验 31/31')
  await expect(page.getByTestId('offer-row')).toHaveCount(155)
})
