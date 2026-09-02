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

  expect(manifest.permissions).toEqual(['activeTab', 'storage', 'scripting'])
  expect(manifest.host_permissions).toEqual(['http://127.0.0.1/*'])
})


it('limits extension storage to non-sensitive configuration keys', () => {
  const source = [
    '../src/shared/api.ts',
    '../src/shared/collection-session.ts',
    '../src/background/index.ts',
    '../src/popup/main.ts',
  ].map((path) => readFileSync(resolve(import.meta.dirname, path), 'utf8')).join('\n')

  for (const forbidden of ['cookie', 'password', 'address', 'phone', 'pageHtml', 'documentHtml']) {
    expect(source).not.toMatch(new RegExp(`['\"]${forbidden}['\"]`, 'i'))
  }
  expect(source).toContain("'backendUrl'")
  expect(source).toContain("'extensionToken'")
  expect(source).toContain("'searchSessionId'")
})
