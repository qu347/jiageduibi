# Data Source Policy

## User-Initiated Capture

真实页面采集必须由用户在当前活动标签页点击扩展按钮触发。工具不执行后台轮询、批量爬取或跨标签页遍历。

## Prohibited Data

禁止读取或保存密码输入、Cookie、浏览历史、支付信息、收货地址和账号令牌。扩展清单不得加入 `cookies`、`history` 或平台通配域名权限。

## Login and CAPTCHA

登录与验证码完全由用户在平台页面手动完成。解析器只返回 `login_required` 或 `captcha`，不得绕过验证。

## No Automated Ordering

软件只做信息整理和本地比较，不加入购物车、不下单、不支付，也不代表平台作价格承诺。

## Fixture Versus Live Status

`fixture_status=passing` 只证明保存在仓库中的固定 HTML/JSON 能通过测试。`live_status=not_validated` 表示真实网站结构、登录态和结算价尚未完成手工验收。
