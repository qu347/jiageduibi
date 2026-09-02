# Platform Adapters

## Adapter Contract

解析器实现 `canHandle(URL)` 与 `parse(Document, URL)`，只返回白名单商品字段。成功结果含平台、标题、平台商品/SKU、店铺、URL、整数分价、适用地区和采集时间。同一平台 SKU 可按不同 `region_key` 独立保存。

## JD Fixture

京东夹具限定 `#J_goodsList .gl-item`、`.p-name`、`.p-price`、`.p-shop` 和 `.p-link`。缺少 `.p-price` 返回 `missing_price`。

## Read-only JD OpenCLI Plugin

项目自带 `price-compare-jd`，不覆盖 OpenCLI 上游内置 `jd` 命令。`search` 只读取搜索列表候选；`verify` 只选择项目固定的代表省/市/区并读取售价与库存。插件不访问购物车、订单、支付或账号地址写入接口。Agent-Reach只用于安装/诊断，FastAPI 运行时直接调用 OpenCLI 的 JSON 输出。

命令失败被映射为安全状态：网络错误有限重试；`login_required`、`captcha` 等待用户；`page_changed`、`unsupported_region` 只影响当前地区；`tool_unavailable` 停止整次任务。原始 stderr 和页面 HTML 不进入数据库或前端。

## Taobao/Tmall Fixture

淘宝夹具限定 `#mainsrp-itemlist .item` 及其链接、价格和店铺节点。当前离线版本未单独声明天猫真实页面已验证。

## PDD Fixture

拼多多夹具限定 `[data-testid="goods-card"]`、价格与店铺节点，并识别授权演示店。

## Structured Failures

失败状态包括 `login_required`、`captcha`、`unsupported_region`、`page_changed`、`missing_price` 或 `invalid_output`。解析器不得用月供、以旧换新宣传价或缺失字段推测一次性总价。

## Live Validation Not Completed

真实京东、淘宝/天猫和拼多多选择器、页面地区识别及结算口径仍需用户登录后的逐平台手工验收。平台状态 API 因此保持 `live_status=not_validated`。启用真实 31 地区采集前，至少人工核验北京、上海、广东三个代表地区，并确认页面显示地区、售价、库存和时间戳均正确。
