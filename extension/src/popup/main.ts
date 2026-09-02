import {
  DEFAULT_BACKEND_URL,
  chromeStorage,
  localPairingApi,
  pairExtension,
} from '../shared/api'


const status = document.querySelector<HTMLElement>('#backend-status')!
const codeInput = document.querySelector<HTMLInputElement>('#pairing-code')!
const pairButton = document.querySelector<HTMLButtonElement>('#pair')!
const captureButton = document.querySelector<HTMLButtonElement>('#capture')!
const message = document.querySelector<HTMLElement>('#message')!

async function refreshStatus() {
  try {
    const response = await fetch(`${DEFAULT_BACKEND_URL}/api/health`)
    status.textContent = response.ok ? '本地服务已连接' : '本地服务响应异常'
  } catch {
    status.textContent = '本地服务未启动'
  }
  const token = await chromeStorage.get('extensionToken')
  captureButton.disabled = !token
  if (token) message.textContent = '扩展已配对，可以采集当前商品页。'
}

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

captureButton.addEventListener('click', () => {
  message.textContent = '页面采集将在下一步启用。'
})

void refreshStatus()
