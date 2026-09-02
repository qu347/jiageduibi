import { describe, expect, it, vi } from 'vitest'

import {
  formatIngestionSummary,
  loadSearchSessionId,
  saveSearchSessionId,
  validateCollectionSession,
} from '../src/shared/collection-session'
import type { ExtensionStorage } from '../src/shared/types'


function memoryStorage(): ExtensionStorage {
  const values = new Map<string, string>()
  return {
    get: async (key) => values.get(key),
    set: async (key, value) => { values.set(key, value) },
    remove: async (key) => { values.delete(key) },
  }
}

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}


describe('extension collection session', () => {
  it('saves and restores a positive search session id', async () => {
    const storage = memoryStorage()

    await saveSearchSessionId(123, storage)

    expect(await storage.get('searchSessionId')).toBe('123')
    expect(await loadSearchSessionId(storage)).toBe(123)
  })

  it('validates a national collecting session', async () => {
    const fetcher = vi.fn().mockResolvedValue(response({
      id: 123,
      variant_id: 7,
      comparison_scope: 'national',
      region_code: null,
      include_conditional: false,
      status: 'collecting',
      created_at: '2026-09-02T00:00:00Z',
      finalized_at: null,
    }))

    const session = await validateCollectionSession(123, 'http://127.0.0.1:8765', fetcher)

    expect(session.id).toBe(123)
    expect(fetcher).toHaveBeenCalledWith('http://127.0.0.1:8765/api/search-sessions/123')
  })

  it.each([
    ['不存在', response({ detail: 'missing' }, 404), '采集会话不存在'],
    ['已完成', response({ comparison_scope: 'national', status: 'completed' }), '采集会话已经完成'],
    ['地区会话', response({ comparison_scope: 'regional', status: 'collecting' }), '仅支持全国采集会话'],
  ])('distinguishes %s validation failures', async (_case, backendResponse, message) => {
    await expect(validateCollectionSession(
      123,
      'http://127.0.0.1:8765',
      vi.fn().mockResolvedValue(backendResponse),
    )).rejects.toThrow(message)
  })

  it('distinguishes a local service network failure', async () => {
    await expect(validateCollectionSession(
      123,
      'http://127.0.0.1:8765',
      vi.fn().mockRejectedValue(new TypeError('Failed to fetch')),
    )).rejects.toThrow('无法连接本地服务')
  })

  it('formats accepted and excluded counts with exclusion reasons', () => {
    expect(formatIngestionSummary({
      platform: 'jd',
      accepted_count: 2,
      excluded_count: 1,
      exclusions: { low_confidence: 1 },
    }, 123)).toContain('已接收 2 条')
    expect(formatIngestionSummary({
      platform: 'jd',
      accepted_count: 2,
      excluded_count: 1,
      exclusions: { low_confidence: 1 },
    }, 123)).toContain('low_confidence：1')

    expect(formatIngestionSummary({
      platform: 'jd',
      accepted_count: 0,
      excluded_count: 3,
      exclusions: { wrong_storage: 2, accessory: 1 },
    }, 123)).toContain('全部 3 条候选报价均被排除')
  })
})
