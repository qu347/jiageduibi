import { expect, it } from 'vitest'

import { pairExtension } from '../src/shared/api'
import type { ExtensionStorage, PairingApi } from '../src/shared/types'


function createMemoryStorage(): ExtensionStorage {
  const values = new Map<string, string>()
  return {
    get: async (key) => values.get(key),
    set: async (key, value) => { values.set(key, value) },
    remove: async (key) => { values.delete(key) },
  }
}


function fakeApi(result: { token: string }): PairingApi {
  return { pair: async () => result }
}


it('stores only the returned local token after pairing', async () => {
  const storage = createMemoryStorage()

  await pairExtension('123456', storage, fakeApi({ token: 'local-token-value' }))

  expect(await storage.get('extensionToken')).toBe('local-token-value')
  expect(await storage.get('pairingCode')).toBeUndefined()
})
