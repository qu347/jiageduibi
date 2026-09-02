# Testing

## Backend

在 `backend` 目录运行 `.\.venv\Scripts\python.exe -m pytest -v`。测试覆盖迁移、目录、匹配、价格、补贴、去重、完整三平台流程、历史、状态与扩展鉴权。

## Frontend

运行 `pnpm --dir frontend test` 与 `pnpm --dir frontend build`。构建步骤包含 Vue 类型检查。

## Extension

运行 `pnpm --dir extension test` 与 `pnpm --dir extension build`。测试覆盖 URL 路由、三个固定解析器、缺价失败、Cookie/密码边界和配对存储。

## Offline E2E

`pnpm --dir e2e test` 使用本机 Edge，自动启动生产 FastAPI 服务；从“苹果17”确认精确 SKU，得到三条排序报价，随后刷新并检查历史最低价。

## Manual Live Acceptance

真实平台验收尚未完成。后续验收必须记录日期、平台 URL、登录/验证码状态、解析结果、结算页价格差异和适配器版本，且不得把手工成功推断为长期稳定。
