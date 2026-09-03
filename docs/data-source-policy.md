# Data Source Policy

## User-Initiated Capture

真实自动采集必须由用户在工作台明确点击启动，随后只通过本机 OpenCLI Browser Bridge 顺序执行已批准的京东候选搜索和 31 个代表地区核验。手动备用模式仍要求用户在当前活动标签页点击扩展按钮。

工具不并行遍历标签页、不通用爬取站点、不绕过平台访问控制。单品任务和价目表任务共用一个浏览器执行槽。界面必须显示已完成/失败/跳过地区数；未完成地区没有数据，不得推断为全国最低或全国有货。“本次已采集范围最低价”只描述已核验结果；价目表结果只有覆盖 31/31 才能标为全国最低。

## Prohibited Data

禁止读取或保存密码输入、Cookie、浏览历史、支付信息、个人收货地址、页面 HTML、命令原始输出和账号令牌。上传价目表原图只写入随机临时文件并在 OCR 结束后删除，数据库只保存可编辑的识别文字和任务结果。固定代表地区仅保存项目定义的省/市/区/街道名称。扩展清单不得加入 `cookies`、`history` 或平台通配域名权限；持久化键仅限 `backendUrl`、`extensionToken`、`searchSessionId`。

## Login and CAPTCHA

登录与验证码完全由用户在平台页面手动完成。自动任务收到 `login_required`、`captcha` 或 `rate_limited` 后暂停并保留已采集报价，不得绕过验证或立即密集重试。

## No Automated Ordering

软件只做信息整理和本地比较，不加入购物车、不下单、不支付，也不代表平台作价格承诺。

## Fixture Versus Live Status

`fixture_status=passing` 只证明保存在仓库中的固定 HTML/JSON 能通过测试。`live_status=not_validated` 表示真实网站结构、登录态和结算价尚未完成手工验收。

离线自动网关只有在 `PRICE_COMPARE_AUTOMATION_FIXTURE=1` 时启用，生产默认仍调用 OpenCLI。传统爬虫后备方案尚未实现，也不会在 OpenCLI 失败时自动启用。
