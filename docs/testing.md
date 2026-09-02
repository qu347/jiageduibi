# Testing

## Backend

在 `backend` 目录运行 `.\.venv\Scripts\python.exe -m pytest -v`。测试覆盖多地区迁移与安全降级、31 地区目录、自动任务恢复、顺序执行、验证码暂停、网络重试、Top10 保留、目录、匹配、价格、补贴、历史、状态与扩展鉴权。

## Frontend

运行 `pnpm --dir frontend test` 与 `pnpm --dir frontend build`。构建步骤包含 Vue 类型检查。

## Extension

运行 `pnpm --dir extension test` 与 `pnpm --dir extension build`。测试覆盖 URL 路由、三个固定解析器、缺价失败、会话保存与校验、幂等内容脚本、权限/敏感字段边界和配对存储。

## OpenCLI Plugin

运行 `node --test opencli-plugin-price-compare-jd\tests\*.test.mjs`（PowerShell 总闸会解析为显式文件列表）。测试覆盖京东搜索列表解析、价格格式和登录状态判断，不访问真实网站。

## Offline E2E

`pnpm --dir e2e test` 使用本机 Edge，自动启动 FastAPI，并仅为该测试进程设置 `PRICE_COMPARE_AUTOMATION_FIXTURE=1` 和独立的系统临时 SQLite。测试从“苹果17”确认精确 SKU，启动 31 地区京东任务，验证暂停、恢复、31/31 完成、每地区 Top5 和刷新恢复；原有手动会话与四条多地区夹具流程继续独立回归。

## Manual Live Acceptance

真实平台验收尚未完成。先运行 `.\scripts\setup-automation.ps1`，再对北京朝阳、上海浦东、广东广州天河做三地区冒烟。验收必须记录日期、平台 URL、登录/验证码状态、页面显示地区、解析结果、结算页价格差异和适配器版本，且不得把手工成功推断为长期稳定。
