# Testing

## Backend

在 `backend` 目录运行 `.\.venv\Scripts\python.exe -m pytest -v`。测试覆盖多地区迁移与安全降级、目录、匹配、价格、逐报价补贴、四字段去重、预览/完成共享排序、历史、状态与扩展鉴权。

## Frontend

运行 `pnpm --dir frontend test` 与 `pnpm --dir frontend build`。构建步骤包含 Vue 类型检查。

## Extension

运行 `pnpm --dir extension test` 与 `pnpm --dir extension build`。测试覆盖 URL 路由、三个固定解析器、缺价失败、会话保存与校验、幂等内容脚本、权限/敏感字段边界和配对存储。

## Offline E2E

`pnpm --dir e2e test` 使用本机 Edge，自动启动生产 FastAPI 服务；从“苹果17”确认精确 SKU，创建全国采集会话，导入四条多地区报价，验证条件价不重排、刷新恢复、完成后拒绝提交，并独立运行固定夹具演示。

## Manual Live Acceptance

真实平台验收尚未完成。后续验收必须记录日期、平台 URL、登录/验证码状态、解析结果、结算页价格差异和适配器版本，且不得把手工成功推断为长期稳定。
