import { expect, it } from 'vitest'

import { ApiError } from '../src/api/client'
import { normalizeApiError } from '../src/stores/comparison'


it('preserves a plain-text server error without reading the response twice', async () => {
  const error = await ApiError.fromResponse(new Response('Internal Server Error', { status: 500 }))

  expect(error.detail).toBe('Internal Server Error')
  expect(normalizeApiError(error).possible_cause).toBe('Internal Server Error')
})
