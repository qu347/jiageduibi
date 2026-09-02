# 个人国补比价工具

本项目是一个仅在本机运行的全国版比价工具。它先确认标准 SKU，再统一比较京东、淘宝和拼多多报价；确认补贴参与默认到手价，估算补贴只单独展示。当前版本用固定夹具完成可重复的离线验收，真实网站适配状态明确标记为“尚未验证”。

## Prerequisites

- Windows 10/11 与 PowerShell 7 或 Windows PowerShell 5.1
- Python 3.12（`py -3.12` 可用）
- Node.js 24 与 pnpm 11
- Microsoft Edge（用于 Playwright 和加载扩展）

不需要平台账号、Cookie、API Key 或全局工具升级。

## Bootstrap

在项目根目录运行：

```powershell
.\scripts\bootstrap.ps1
```

脚本只创建项目内的 `backend\.venv`、安装锁定依赖、升级本地 SQLite 并初始化 iPhone 17 标准目录。

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

把 6 位码输入扩展弹窗。配对码只能使用一次；后端只保存扩展令牌的 SHA-256 哈希。采集前还需在弹窗填写工作台当前比价会话 ID。

## Run Tests

```powershell
.\scripts\test.ps1
```

该命令先构建，再运行后端、前端、扩展和 Edge 离线端到端测试。

## Build Outputs

- Web 应用：`frontend\dist`
- Edge/Chrome MV3 扩展：`extension\dist`
- SQLite：`data\price_compare.db`

## Local Data

所有目录、报价、价格快照、补贴规则和配对哈希都保存在 `data\price_compare.db`。扩展本地存储只保存 `backendUrl` 和 `extensionToken`；本项目不保存平台密码或 Cookie。

## Uninstall

先在 Edge 移除扩展并停止项目进程。如需保留历史，先复制 `data\price_compare.db`。确认备份后，可以删除整个项目目录；本项目不会在项目目录外创建业务数据。

更多边界说明见 [架构](docs/architecture.md)、[数据源政策](docs/data-source-policy.md)、[适配器](docs/platform-adapters.md)、[补贴规则](docs/subsidy-rules.md) 和 [测试](docs/testing.md)。
