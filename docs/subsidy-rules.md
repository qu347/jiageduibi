# Subsidy Rules

## Region Selection

普通比价不要求地区。补贴判断必须选择省市编码；缺少地区时返回“需要先选择省市”。

## Rule Fields

规则包含地区、品类、有效期、最高单价、补贴基点、封顶金额、参与平台/店铺、来源链接、核验时间和启用状态。启用规则必须有 HTTP(S) 来源。

## Precedence

同一报价优先使用城市规则，其次省级规则；同级规则再按是否核验和核验时间排序。无法消解的同级冲突返回“未知”。

## Confirmed Versus Estimated

只有平台对同一 SKU 明确给出的补贴进入 `confirmed` 并影响默认可比价。按本地规则计算的是 `estimated`，只单独展示，不能改变默认排序。

## Settlement Disclaimer

规则和页面价格都可能变化，最终资格、库存、优惠和实付金额必须以平台结算页及当地官方政策为准。
