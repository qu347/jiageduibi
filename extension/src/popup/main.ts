import {
  DEFAULT_BACKEND_URL,
  chromeStorage,
  localPairingApi,
  pairExtension,
} from '../shared/api'
import { loadSearchSessionId, saveSearchSessionId } from '../shared/collection-session'


const status = document.querySelector<HTMLElement>('#backend-status')!
const codeInput = document.querySelector<HTMLInputElement>('#pairing-code')!
const pairButton = document.querySelector<HTMLButtonElement>('#pair')!
const captureButton = document.querySelector<HTMLButtonElement>('#capture')!
const searchSessionInput = document.querySelector<HTMLInputElement>('#search-session-id')!
const message = document.querySelector<HTMLElement>('#message')!

async function refreshStatus() {
  try {
    const response = await fetch(`${DEFAULT_BACKEND_URL}/api/health`)
    status.textContent = response.ok ? '本地服务已连接' : '本地服务响应异常'
  } catch {
    status.textContent = '本地服务未启动'
  }
  const token = await chromeStorage.get('extensionToken')
  const savedSessionId = await loadSearchSessionId(chromeStorage)
  searchSessionInput.value = savedSessionId === null ? '' : String(savedSessionId)
  captureButton.disabled = !token
  if (token) message.textContent = '扩展已配对，可以采集当前商品页。'
}

searchSessionInput.addEventListener('change', async () => {
  const searchSessionId = Number(searchSessionInput.value)
  if (!Number.isInteger(searchSessionId) || searchSessionId <= 0) {
    message.textContent = '会话 ID 必须是正整数。'
    return
  }
  await saveSearchSessionId(searchSessionId, chromeStorage)
  message.textContent = '会话 ID 已保存。'
})

pairButton.addEventListener('click', async () => {
  const code = codeInput.value.trim()
  if (!/^\d{6}$/.test(code)) {
    message.textContent = '请输入 6 位配对码。'
    return
  }
  pairButton.disabled = true
  try {
    await pairExtension(code, chromeStorage, localPairingApi())
    codeInput.value = ''
    message.textContent = '配对成功。'
    await refreshStatus()
  } catch (error) {
    message.textContent = error instanceof Error ? error.message : '配对失败'
  } finally {
    pairButton.disabled = false
  }
})

captureButton.addEventListener('click', async () => {
  const searchSessionId = Number(searchSessionInput.value)
  if (!Number.isInteger(searchSessionId) || searchSessionId <= 0) {
    message.textContent = '请填写工作台中的比价会话 ID。'
    return
  }
  await saveSearchSessionId(searchSessionId, chromeStorage)
  captureButton.disabled = true
  message.textContent = '正在读取当前标签页的公开商品字段…'
  try {
    const result = await chrome.runtime.sendMessage({ type: 'CAPTURE_ACTIVE_TAB', searchSessionId }) as {
      status: string
      message: string
    }
    message.textContent = result.message
  } catch (error) {
    message.textContent = error instanceof Error ? error.message : '采集失败'
  } finally {
    captureButton.disabled = false
  }
})

void refreshStatus()
