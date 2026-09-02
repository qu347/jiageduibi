import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { expect, it, vi } from 'vitest'

import { captureCurrentDocument } from '../src/parsers'


it('never reads password inputs or cookies', () => {
  document.body.innerHTML = '<input type="password" value="secret"><div data-title="iPhone 17 256GB"></div>'
  const cookieSpy = vi.spyOn(document, 'cookie', 'get')

  captureCurrentDocument(document, new URL('https://search.jd.com/Search?keyword=iphone17'))

  expect(cookieSpy).not.toHaveBeenCalled()
})


it('keeps privileged and persistent host permissions out of the manifest', () => {
  const manifest = JSON.parse(
    readFileSync(resolve(import.meta.dirname, '../public/manifest.json'), 'utf8'),
  ) as { permissions: string[]; host_permissions: string[] }

  expect(manifest.permissions).not.toContain('cookies')
  expect(manifest.permissions).not.toContain('history')
  expect(manifest.host_permissions).toEqual(['http://127.0.0.1/*'])
})
