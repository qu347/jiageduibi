# 个人国补比价工具

本项目是一个仅在本机运行的全国版比价工具。它先确认标准 SKU，再由本机已登录浏览器顺序核验中国大陆 31 个省级代表地区的京东报价；确认补贴参与默认到手价，估算补贴只单独展示。这里的“全国”表示本次任务已显示完成的代表地区覆盖，不表示穷尽平台全部商品或所有地级市。自动流程已有固定数据离线验收，真实京东页面仍明确标记为“尚未验证”。

## Prerequisites

- Windows 10/11 与 PowerShell 7 或 Windows PowerShell 5.1
- Python 3.12（`py -3.12` 可用）
- Node.js 24 与 pnpm 11
- Microsoft Edge（用于 Playwright 和手动采集扩展）
- Chrome（真实自动采集时连接 OpenCLI 官方 Browser Bridge）

离线测试不需要电商开放平台 API Key 或平台账号。真实自动采集使用你自己控制的 Chrome 京东登录态，软件不读取或保存密码、Cookie。京东联盟 AppKey/AppSecret 是可选配置：配置后优先用官方接口批量找候选，再由浏览器核验地区价格；未配置或关键词接口权限待开通时，候选搜索继续使用浏览器。

## Bootstrap

在项目根目录运行：

```powershell
.\scripts\bootstrap.ps1
```

脚本只创建项目内的 `backend\.venv`、安装锁定依赖（含 PaddleOCR CPU 版）、升级本地 SQLite 并初始化 iPhone 17 标准目录。第一次识别图片时 PaddleOCR 可能联网下载中文模型，之后使用本机缓存。

## Development

```powershell
.\scripts\dev.ps1
```

浏览器打开 `http://127.0.0.1:5173`。脚本会显示前后端进程 ID，结束时使用 `Stop-Process -Id <PID>`。

## Offline Demo

```powershell
.\scripts\build.ps1
.\scripts\demo.ps1
```

演示地址是 `http://127.0.0.1:8765`。演示规则来源使用保留域名 `example.invalid`，只用于证明“预计国补不参与默认排序”，不代表任何真实政策。

工作台有四个相互独立的入口：

- “价目表批量比价”上传 JPG/PNG/WebP 手机价目表，在本机 OCR 后先让你逐行核对机型、容量、颜色和今日价。每个规格冻结最多 20 个精确候选，再按 31 个代表街道串行读取结算预览，最多形成 620 个组合，可能运行数小时。只有 31 个地区各有无条件 verified 应付价且最低价严格低于今日价时，才显示该规格唯一一条全国最低价。
- “开始全国自动比价”是主流程：搜索 30 个候选、筛选最多 15 个，再按 31 个代表地区各打开一次搜索页批量读取白名单商品；验证码、登录失效或访问频繁只暂停当前任务。
- “手动采集备用”生成可复制的全国会话 ID，供扩展逐地区提交报价；刷新只预览，完成后不再接收报价。
- “运行三平台离线比价”读取四条固定报价，适合在没有真实平台页面时验收排序与地区展示。

## Setup Automatic JD Collection

先安装 Agent-Reach，然后运行唯一的自动采集配置命令：

```powershell
.\scripts\setup-automation.ps1
```

Agent-Reach只负责安装和诊断 OpenCLI；软件运行时直接调用 OpenCLI。脚本注册项目自带的 `price-compare-jd` 插件，并检查官方 Browser Bridge。搜索与地区展示命令只读；价目表使用受保护的 `checkout-preview`，优先“立即购买”，必要时才短暂加购并验证恢复。首次使用需由你在 Chrome 安装官方扩展并登录京东；采集期间要保持这个 Chrome 窗口打开。程序不创建或修改账号地址、不提交订单、不付款。

真实 31 地区按钮在完成单 SKU、单地区结算预览和一次购物车回退人工冒烟前只能视为“尚未现场验证”。真实京东测试建议关闭会拖慢京东页面的代理，但要保持 Chrome、OpenCLI Browser Bridge 和京东登录态可用。验收时必须确认没有提交订单或进入付款页；回退场景还要确认购物车完全恢复。如果京东页面改版，任务会安全暂停或标记失败；当前版本保留传统爬虫为未实现的后备方向，不会自动切换。

### Optional JD Union API

京东联盟凭据只从当前进程环境变量读取，不写入代码、数据库或日志。启动项目前可在同一个 PowerShell 窗口临时设置：

```powershell
$env:JD_UNION_APP_KEY = Read-Host "JD Union AppKey"
$secret = Read-Host "JD Union AppSecret" -AsSecureString
$env:JD_UNION_APP_SECRET = [Net.NetworkCredential]::new("", $secret).Password
.\scripts\demo.ps1
```

当前接入 `jd.union.open.goods.query` 作为关键词候选源，`jd.union.open.goods.rank.query` 只用于接口连通性与响应兼容验证，不会拿热销榜冒充关键词搜索结果。关键词接口返回“无访问权限”时自动回退 OpenCLI 搜索。浏览器按地区读取搜索页可见售价与商品可见性；搜索页没有明确展示的运费、会员价、优惠或国补一律不推测。

## Load the Edge Extension

1. 先运行 `.\scripts\build.ps1`。
2. 在 Edge 打开 `edge://extensions`，启用“开发人员模式”。
3. 选择“加载解压缩的扩展”，指向项目内 `extension\dist`。
4. 清单只申请 `activeTab`、`storage`、`scripting` 和 `http://127.0.0.1/*`。

## Pair the Extension

本地服务运行时，在 PowerShell 获取一次性配对码：

```powershell
(Invoke-RestMethod -Method Post http://127.0.0.1:8765/api/extension/pairing-code).code
```

把 6 位码输入扩展弹窗。配对码只能使用一次；后端只保存扩展令牌的 SHA-256 哈希。采集前还需在弹窗填写工作台当前采集会话 ID。扩展会保存该 ID，并在每次采集前确认它仍是“全国 + 采集中”的有效会话。

## Run Tests

```powershell
.\scripts\test.ps1
```

该命令先构建，再运行 OpenCLI 插件安全测试、后端、前端、扩展和 Edge 离线端到端测试。

## Build Outputs

- Web 应用：`frontend\dist`
- Edge/Chrome MV3 扩展：`extension\dist`
- SQLite：`data\price_compare.db`

## Local Data

所有目录、采集进度、候选白名单、报价、价格快照、价目表文字结果、补贴规则和配对哈希都保存在 `data\price_compare.db`。上传原图只进入随机临时文件，识别成功或失败后都会删除，不写入数据库。扩展本地存储只保存 `backendUrl`、`extensionToken` 和 `searchSessionId`；本项目不保存平台密码、Cookie、个人收货地址、命令原始输出或页面 HTML。31 个代表地区是项目固定的省/市/区/街道名称，不是用户账号地址。

## Uninstall

先在 Edge 移除扩展并停止项目进程。如需保留历史，先复制 `data\price_compare.db`。确认备份后，可以删除整个项目目录；本项目不会在项目目录外创建业务数据。

更多边界说明见 [采集会话](docs/collection-session.md)、[架构](docs/architecture.md)、[数据源政策](docs/data-source-policy.md)、[适配器](docs/platform-adapters.md)、[补贴规则](docs/subsidy-rules.md) 和 [测试](docs/testing.md)。
