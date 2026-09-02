# Platform Adapters

## Adapter Contract

解析器实现 `canHandle(URL)` 与 `parse(Document, URL)`，只返回白名单商品字段。成功结果含平台、标题、平台商品/SKU、店铺、URL、整数分价和采集时间。

## JD Fixture

京东夹具限定 `#J_goodsList .gl-item`、`.p-name`、`.p-price`、`.p-shop` 和 `.p-link`。缺少 `.p-price` 返回 `missing_price`。

## Taobao/Tmall Fixture

淘宝夹具限定 `#mainsrp-itemlist .item` 及其链接、价格和店铺节点。当前离线版本未单独声明天猫真实页面已验证。

## PDD Fixture

拼多多夹具限定 `[data-testid="goods-card"]`、价格与店铺节点，并识别授权演示店。

## Structured Failures

失败状态为 `login_required`、`captcha`、`unsupported` 或 `missing_price`。解析器不得用月供、以旧换新宣传价或缺失字段推测一次性总价。

## Live Validation Not Completed

真实京东、淘宝/天猫和拼多多选择器仍需用户登录后的逐平台手工验收。平台状态 API 因此保持 `live_status=not_validated`。
