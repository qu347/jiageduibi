import { expect, test } from '@playwright/test'


test('runs and restores a nationwide multi-region collection session', async ({ page, request }) => {
  await page.goto('/')
  await expect(page.getByTestId('nationwide-scope')).toContainText('全国比价')
  await page.getByTestId('keyword').fill('苹果17')
  await page.getByTestId('search-models').click()
  await page.getByText('iPhone 17', { exact: true }).click()
  await page.getByText('256GB', { exact: true }).click()
  await page.getByText('中国大陆国行', { exact: true }).click()
  await page.getByText('全新', { exact: true }).click()
  await page.getByTestId('confirm-variant').click()
  await page.getByTestId('create-collection-session').click()
  const sessionId = Number(await page.getByTestId('collection-session-id').textContent())
  expect(sessionId).toBeGreaterThan(0)

  const batches: Record<string, unknown>[] = []
  for (const platform of ['jd', 'taobao', 'pdd']) {
    const fixtureResponse = await request.get(`/${platform}/search-results.json`)
    expect(fixtureResponse.ok()).toBeTruthy()
    const batch = await fixtureResponse.json() as Record<string, unknown>
    batches.push(batch)
    const response = await request.post(`/api/search-sessions/${sessionId}/offers`, { data: batch })
    expect(response.ok()).toBeTruthy()
  }
  await page.getByTestId('refresh-session').click()

  await expect(page.getByTestId('offer-row')).toHaveCount(4)
  await expect(page.getByTestId('lowest-region')).toHaveText('最低价地区：上海市')
  await expect(page.getByText(/已排除 [5-9]\d* 条干扰项/)).toBeVisible()
  await expect(page.getByText('预计国补').first()).toBeVisible()
  const prices = await page.getByTestId('comparable-price').allTextContents()
  expect(prices).toEqual(['¥4,999.00', '¥5,049.00', '¥5,099.00', '¥5,199.00'])
  const initialOfferIds = await page.getByTestId('offer-row').evaluateAll((rows) => (
    rows.map((row) => row.getAttribute('data-offer-id'))
  ))
  expect(initialOfferIds.every(Boolean)).toBeTruthy()

  await page.getByRole('checkbox', { name: /显示会员/ }).check()
  expect(await page.getByTestId('offer-row').evaluateAll((rows) => (
    rows.map((row) => row.getAttribute('data-offer-id'))
  ))).toEqual(initialOfferIds)

  await page.reload()
  await expect(page.getByTestId('collection-session-id')).toHaveText(String(sessionId))
  await expect(page.getByTestId('offer-row')).toHaveCount(4)
  expect(await page.getByTestId('offer-row').evaluateAll((rows) => (
    rows.map((row) => row.getAttribute('data-offer-id'))
  ))).toEqual(initialOfferIds)

  await page.getByTestId('finalize-session').click()
  await expect(page.getByTestId('finalize-session')).toBeDisabled()
  const rejected = await request.post(`/api/search-sessions/${sessionId}/offers`, { data: batches[0] })
  expect(rejected.status()).toBe(422)

  await page.getByTestId('run-fixture-comparison').click()
  await expect(page.getByTestId('offer-row')).toHaveCount(4)
  await expect(page.getByTestId('comparable-price')).toHaveText([
    '¥4,999.00',
    '¥5,049.00',
    '¥5,099.00',
    '¥5,199.00',
  ])
})
