# Platform Adapters

## Adapter Contract

解析器实现 `canHandle(URL)` 与 `parse(Document, URL)`，只返回白名单商品字段。成功结果含平台、标题、平台商品/SKU、店铺、URL、整数分价、适用地区和采集时间。同一平台 SKU 可按不同 `region_key` 独立保存。

## JD Fixture

京东夹具限定 `#J_goodsList .gl-item`、`.p-name`、`.p-price`、`.p-shop` 和 `.p-link`。缺少 `.p-price` 返回 `missing_price`。

## JD OpenCLI Plugin

项目自带 `price-compare-jd`，不覆盖 OpenCLI 上游内置 `jd` 命令。`search`、`verify` 和 `verify-region` 是读取命令：搜索候选或通过已校验的京东四级地区编码更新本地配送地区后回读页面。价目表模式严格匹配机型、容量和颜色，排除配件、二手/翻新、定金、分期、以旧换新和预约商品，并冻结最多 20 个候选。

`checkout-preview` 明确标记为受控 write。它对每个候选与代表街道优先使用“立即购买”，只读取结算预览中的目标 SKU、数量 1、地区、优惠明细和应付金额；没有安全入口时才允许可验证恢复的购物车回退。命令永不选择提交订单或付款控件，进入收银台、付款或订单成功页会立即触发安全熔断。插件不创建或修改账号收货地址。Agent-Reach只用于安装/诊断，FastAPI 运行时直接调用 OpenCLI 的严格 JSON 输出。

命令失败被映射为安全状态：网络错误有限重试；`login_required`、`captcha`、`rate_limited`、`safety_boundary_crossed` 和 `cart_isolation_failed` 暂停任务；缺少真实地址、无法确认 SKU/地区或价格时跳过当前组合；`tool_unavailable` 停止整次任务。环境诊断只有在扩展与连接检查都明确成功时才报告 Browser Bridge 可用。原始 stderr 和页面 HTML 不进入数据库或前端。

## Optional JD Union Candidate Source

配置 `JD_UNION_APP_KEY` 与 `JD_UNION_APP_SECRET` 后，候选发现优先调用京东联盟 `jd.union.open.goods.query`；签名按京东 MD5 规则在内存生成，凭据不进入业务数据。接口只提供候选，31 个代表地区的搜索页可见售价与商品可见性仍交给 OpenCLI 浏览器核验。

`jd.union.open.goods.rank.query` 的当前嵌套响应已纳入兼容测试，但热销榜不具备关键词语义，因此不参与用户查询结果。关键词接口业务状态为 403 时只降级本次候选发现到 OpenCLI；其他凭据、网关或响应错误保持显式失败，防止把错误配置静默伪装成成功。

## Taobao/Tmall Fixture

淘宝夹具限定 `#mainsrp-itemlist .item` 及其链接、价格和店铺节点。当前离线版本未单独声明天猫真实页面已验证。

## PDD Fixture

拼多多夹具限定 `[data-testid="goods-card"]`、价格与店铺节点，并识别授权演示店。

## Structured Failures

失败状态包括 `login_required`、`captcha`、`rate_limited`、`unsupported_region`、`page_changed`、`missing_price` 或 `invalid_output`。解析器不得用月供、以旧换新宣传价或缺失字段推测一次性总价。

## Live Validation Not Completed

真实京东、淘宝/天猫和拼多多选择器、页面地区识别及结算口径仍需用户登录后的逐平台手工验收。平台状态 API 因此保持 `live_status=not_validated`。启用真实 31 地区采集前，至少人工核验北京、上海、广东三个代表地区，并确认页面显示地区、售价、库存和时间戳均正确。
