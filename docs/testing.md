# Testing

## Backend

在 `backend` 目录运行 `.\.venv\Scripts\python.exe -m pytest -v`。测试覆盖多地区迁移与安全降级、31 个代表街道、自动任务恢复、跨模式浏览器串行、验证码暂停、网络重试、价目表 OCR/解析/精确颜色匹配/可信价格、Top10 保留、目录、补贴、历史、状态与扩展鉴权。

## Frontend

运行 `pnpm --dir frontend test` 与 `pnpm --dir frontend build`。构建步骤包含 Vue 类型检查。

## Extension

运行 `pnpm --dir extension test` 与 `pnpm --dir extension build`。测试覆盖 URL 路由、三个固定解析器、缺价失败、会话保存与校验、幂等内容脚本、权限/敏感字段边界和配对存储。

## OpenCLI Plugin

运行 `node --test opencli-plugin-price-compare-jd\tests\*.test.mjs`（PowerShell 总闸会解析为显式文件列表）。测试覆盖京东搜索列表解析、批量候选白名单、结算预览字段、订单/付款熔断、购物车隔离与恢复、登录状态、访问频繁和不可用商品页判断，不访问真实网站。

## Offline E2E

`pnpm --dir e2e test` 使用本机 Edge，自动启动 FastAPI，并仅为该测试进程设置 `PRICE_COMPARE_AUTOMATION_FIXTURE=1`、`PRICE_COMPARE_OCR_FIXTURE=1` 和独立的系统临时 SQLite。测试从“苹果17”确认精确 SKU，启动 31 地区京东任务并验证暂停/恢复；另一路上传合法图片，冻结每个规格 20 个候选并完成最多 620 个结算组合，只显示一条 31/31 verified 低价，确认更低的 conditional 价格不会胜出、缺真实地址会形成部分覆盖、购物车恢复失败会留下持久警告。全部夹具只返回内存数据，不加载真实京东 URL。

## Manual Live Acceptance

真实平台验收尚未完成。先运行 `.\scripts\setup-automation.ps1`，保持 Chrome、Browser Bridge 与京东登录态，在代理关闭的网络环境下只对一个 SKU × 一个地区做“立即购买”冒烟，目视确认数量、SKU、区县、街道和应付金额一致且没有提交订单或进入支付页。再选一个确实需要购物车回退的商品，结束后人工确认购物车完全恢复。两项通过后才运行完整 31 地区批次；最多 620 个组合可能持续数小时。不得把一次手工成功推断为长期稳定。
