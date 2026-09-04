# 京东结算页核价实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` for every implementation task and `superpowers:verification-before-completion` before claiming completion. Execute inline unless the user explicitly requests subagents.

**Goal:** 对每个价目表规格保留京东前 20 个精确候选，串行核验候选与 31 个代表地区的结算页应付金额，只展示无需额外资格且结算页明确确认的最低价，全程禁止提交订单和付款。

**Architecture:** 保留现有 OCR、精确规格匹配和四级地区常量，新增独立的结算核验任务/结果表。价目表执行器先一次性冻结最多 20 个候选，再按候选 × 地区生成可恢复队列；OpenCLI 新增一个标记为写操作的单 SKU、单地区 `checkout-preview` 命令，优先走“立即购买”，只在能够证明购物车可隔离并恢复时有限回退。结算页阶段只有 DOM 读取权；插件与 Python 网关各自执行订单/付款双重熔断。API 返回聚合进度而不是一次传输全部 620 个任务，结果按 31 个地区的无条件已核验覆盖率判定是否可称为全国最低。

**Tech Stack:** Python 3.12、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、pytest、OpenCLI 1.8+、Node.js test runner、linkedom、Vue 3、Pinia、TypeScript、Vitest、Playwright

**Spec:** `docs/superpowers/specs/2026-09-04-jd-checkout-price-verification-design.md`

## Global Constraints

- 仅支持京东；不增加淘宝、拼多多或传统爬虫实现。
- 每个价目表规格最多保留 20 个精确匹配候选，最多创建 `20 × 31 = 620` 个结算组合。
- 继续使用 `app.automation.regions.MAINLAND_REGION_TARGETS` 中已有的 31 个四级地区及 `jd_area_id`；不在京东账号内创建、修改或删除地址。
- 不生成虚假姓名、手机号、社区、楼栋或门牌号；结算页需要完整真实地址时返回 `checkout_address_required`。
- 数量固定为 1；结算页必须再次确认目标 SKU、目标区县和街道以及明确应付金额。
- 会员、PLUS、新人、学生、支付方式、白条、分期、以旧换新、回收和其他资格价只能标记为条件价，不进入默认最低价。
- 不根据价格差额推测普通券、国补或其他优惠类型。
- 任何代码路径都不能点击“提交订单”“确认订单”“去支付”“立即支付”“付款”，不能调用订单、支付或账号地址写接口。
- 进入收银台、支付页、订单成功页，或输出中出现订单号/支付字段时，立即触发 `safety_boundary_crossed` 并暂停批次。
- 购物车回退前后必须可验证；无法唯一隔离、删除本次新增行或恢复原勾选状态时停止并保留人工检查警告。
- 单浏览器、单任务串行执行；每个组合完成后立即提交数据库，恢复时不重搜、不重跑已完成组合。
- 数据库和日志不得保存 Cookie、密码、手机号、完整收货地址、支付信息、完整页面 HTML 或 OpenCLI 原始输出。
- 自动测试只使用假网关和静态 DOM，不访问京东、不加购物车、不进入真实结算页；真实平台测试由用户关闭代理后手工执行。
- 不修改用户已有的 `backend/app/matching/matcher.py`、`backend/tests/automation/test_candidates.py`、`backend/tests/matching/test_matcher.py`、`docs/demos/` 和 `e2e/tests/national-price-flow-demo.test.mjs` 未提交改动。

---

### Task 1: 将价目表精确候选上限改为 20

**Files:**
- Modify: `backend/app/price_sheets/matching.py`
- Modify: `backend/tests/price_sheets/test_matching.py`

**Interfaces:**
- Consumes: `PriceSheetTarget` 与发现候选列表。
- Produces: `select_price_sheet_candidates(..., limit=20)`，按搜索页价格和 SKU 稳定排序，最多返回 20 个精确规格候选。

- [ ] **Step 1: 写默认保留 20 个候选的失败测试**

把现有限制测试改成 25 个有效候选且不传 `limit`：

```python
def test_selection_is_stably_sorted_and_defaults_to_twenty() -> None:
    target = PriceSheetTarget('Apple', 'iPhone 17', '256GB', '白色')
    rows = [
        candidate(str(index).zfill(2), 'Apple iPhone 17 256GB 白色 全新国行', 500_000 - index)
        for index in range(25)
    ]

    selected = select_price_sheet_candidates(target, rows)

    assert len(selected) == 20
    assert [row.platform_sku_id for row in selected[:2]] == ['24', '23']
```

- [ ] **Step 2: 运行测试确认旧默认值失败**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_matching.py -v`

Expected: FAIL，实际只返回 15 条。

- [ ] **Step 3: 做最小修改**

```python
def select_price_sheet_candidates(
    target: PriceSheetTarget,
    candidates: list[DiscoveredCandidate],
    limit: int = 20,
) -> list[DiscoveredCandidate]:
```

保留现有型号、容量、颜色、成色和条件销售排除逻辑，不改通用 matcher。

- [ ] **Step 4: 运行测试并提交**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_matching.py -v`

Expected: PASS。

Commit: `feat: keep twenty exact JD candidates`

---

### Task 2: 新增可恢复的结算任务和结果表

**Files:**
- Modify: `backend/app/db/models/price_sheets.py`
- Modify: `backend/app/db/models/__init__.py`
- Create: `backend/alembic/versions/0009_jd_checkout_previews.py`
- Create: `backend/tests/db/test_checkout_preview_migration.py`

**Interfaces:**
- Produces: `PriceSheetCheckoutTask` 与 `PriceSheetCheckoutResult` ORM 模型。
- Preserves: 现有 `price_sheet_region_tasks` 和 `price_sheet_region_results` 表，不删除历史数据。

- [ ] **Step 1: 写迁移失败测试**

```python
def test_checkout_preview_migration_adds_unique_resumable_tasks(tmp_path: Path) -> None:
    config = config_for(tmp_path)
    command.upgrade(config, '0008_price_sheet_batches')
    command.upgrade(config, 'head')
    inspector = inspect(create_engine(config.get_main_option('sqlalchemy.url')))

    assert {'price_sheet_checkout_tasks', 'price_sheet_checkout_results'} <= set(inspector.get_table_names())
    assert {item['name'] for item in inspector.get_unique_constraints('price_sheet_checkout_tasks')} == {
        'uq_price_sheet_checkout_item_region_sku',
    }
    assert {item['name'] for item in inspector.get_unique_constraints('price_sheet_checkout_results')} == {
        'uq_price_sheet_checkout_result_task',
    }
```

同时断言降级到 `0008_price_sheet_batches` 只删除新两表，原四张价目表表仍存在。

- [ ] **Step 2: 运行迁移测试确认失败**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/db/test_checkout_preview_migration.py -v`

Expected: FAIL，因为 0009 和两张表尚不存在。

- [ ] **Step 3: 实现 0009 与 ORM**

`PriceSheetCheckoutTask` 精确字段：

```python
class PriceSheetCheckoutTask(Base):
    __tablename__ = 'price_sheet_checkout_tasks'
    __table_args__ = (UniqueConstraint(
        'price_sheet_item_id', 'region_code', 'platform_sku_id',
        name='uq_price_sheet_checkout_item_region_sku',
    ),)

    id: Mapped[int] = mapped_column(primary_key=True)
    price_sheet_item_id: Mapped[int] = mapped_column(ForeignKey('price_sheet_items.id'), index=True)
    region_code: Mapped[str] = mapped_column(String(12), index=True)
    platform_sku_id: Mapped[str] = mapped_column(String(160))
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    entry_mode: Mapped[str | None] = mapped_column(String(32))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

`PriceSheetCheckoutResult` 使用独立 `id`，`checkout_task_id` 唯一；保存 `title/product_url/shop_name/shop_type`、`quantity`、`target_only`、`line_original_price_cents`、`line_sale_price_cents`、`merchant_discount_cents`、`ordinary_coupon_cents`、`subsidy_amount_cents`、`shipping_fee_cents`、`payable_price_cents`、`discount_summary`、`conditional_reason`、`unavailable_code`、`price_status`、`region_confirmed`、`cart_restored` 和 `captured_at`。所有金额均为整数分，可缺金额字段为 nullable。

- [ ] **Step 4: 导出模型并验证升级/降级**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/db/test_checkout_preview_migration.py backend/tests/db/test_migrations.py -v
```

Expected: PASS。

Commit: `feat: persist JD checkout preview tasks`

---

### Task 3: 定义结算预览契约并封闭 OpenCLI 输出

**Files:**
- Modify: `backend/app/automation/contracts.py`
- Modify: `backend/app/automation/opencli.py`
- Modify: `backend/tests/automation/test_opencli_gateway.py`
- Create: `backend/tests/automation/fixtures/opencli-checkout-preview.json`

**Interfaces:**
- Produces: `CheckoutPreview`、运行时可检查的 `CheckoutPreviewGateway` 和 `OpenCliGateway.checkout_preview(candidate, region, allow_cart_fallback=True)`。
- OpenCLI command: `opencli.cmd price-compare-jd checkout-preview <sku> --province ... --city ... --district ... --street ... --area-id ... --allow-cart-fallback true --site-session persistent -f json`。

- [ ] **Step 1: 写严格输出契约失败测试**

用固定命令运行器返回一条合法结果，断言参数含完整四级地区、候选 SKU 和 `--allow-cart-fallback true`，并解析为：

```python
CheckoutPreview(
    platform_sku_id='100209267857',
    title='Apple iPhone 17 256GB 黑色',
    product_url='https://item.jd.com/100209267857.html',
    shop_name='Apple产品京东自营旗舰店',
    shop_type='self_operated',
    entry_mode='buy_now',
    price_status='verified',
    quantity=1,
    target_only=True,
    line_original_price_cents=591_900,
    line_sale_price_cents=541_900,
    merchant_discount_cents=0,
    ordinary_coupon_cents=0,
    subsidy_amount_cents=50_000,
    shipping_fee_cents=0,
    payable_price_cents=541_900,
    discount_summary='国家补贴已应用 500 元',
    conditional_reason=None,
    unavailable_code=None,
    region_confirmed=True,
    cart_restored=True,
    captured_at=datetime(2026, 9, 4, tzinfo=UTC),
)
```

- [ ] **Step 2: 写订单/支付字段拒绝测试**

参数化加入 `order_id`、`payment_id`、`payment_status`、`pay_url` 和任意未知字段，全部必须抛出：

```python
with pytest.raises(GatewayFailure, match='数据格式') as failure:
    gateway.checkout_preview(candidate, region)
assert failure.value.code == 'invalid_output'
```

再测试 `price_status='verified'` 但 `quantity != 1`、`target_only=False`、`region_confirmed=False`、`payable_price_cents=None`、SKU 不同或 `cart_fallback + cart_restored=False` 均不能成为合法 verified 结果。

- [ ] **Step 3: 运行测试确认缺少契约和命令**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/automation/test_opencli_gateway.py -v`

Expected: FAIL，因为网关没有 `checkout_preview`。

- [ ] **Step 4: 实现 dataclass、Protocol 与 Pydantic 模型**

`CheckoutPreviewOutput` 设置 `ConfigDict(extra='forbid')`，用 `Literal` 限定：

```python
entry_mode: Literal['buy_now', 'cart_fallback']
price_status: Literal['verified', 'conditional', 'unavailable']
quantity: int = Field(ge=0, le=99)
target_only: bool
unavailable_code: Literal[
    'checkout_address_required', 'checkout_region_unconfirmed',
    'buy_now_unavailable', 'cart_isolation_failed',
    'sku_unconfirmed', 'price_unavailable',
] | None = None
```

加入 `model_validator(mode='after')`：verified/conditional 必须满足 `quantity == 1`、`target_only is True`、正数应付金额和已确认地区；verified 不得有 `conditional_reason`；cart fallback 未恢复时只允许 unavailable。网关还要显式比较返回 SKU 与请求 SKU，并要求结果列表恰好一条。

- [ ] **Step 5: 扩展错误映射和环境诊断**

把下列 stderr token 映射为同名小写错误：`CHECKOUT_ADDRESS_REQUIRED`、`CHECKOUT_REGION_UNCONFIRMED`、`BUY_NOW_UNAVAILABLE`、`CART_ISOLATION_FAILED`、`SKU_UNCONFIRMED`、`PRICE_UNAVAILABLE`、`SAFETY_BOUNDARY_CROSSED`。`_plugin_commands_present` 必须同时找到 `search/verify/verify-region/checkout-preview`。

- [ ] **Step 6: 运行测试并提交**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/automation/test_opencli_gateway.py -v`

Expected: PASS。

Commit: `feat: add strict checkout preview gateway`

---

### Task 4: 用纯函数建立 DOM 解析和订单付款熔断

**Files:**
- Create: `opencli-plugin-price-compare-jd/lib/jd-checkout.js`
- Create: `opencli-plugin-price-compare-jd/tests/jd-checkout.test.mjs`

**Interfaces:**
- Produces: `safetyBoundaryCode(markers)`、`actionSelector(kind, document)`、`extractCheckoutPreview(expected, document)`、`classifyCheckoutPrice(raw)`、`snapshotCart(document)`、`planCartIsolation(snapshot, sku)` 和 `cartRestored(snapshot, current)`。

- [ ] **Step 1: 写禁止动作与 URL 的失败测试**

```javascript
test('never selects order submission or payment controls', () => {
  const { document } = parseHTML(`
    <button>立即购买</button><button>提交订单</button>
    <a href="https://cashier.jd.com/pay">去支付</a>
  `)
  assert.ok(actionSelector('buy_now', document))
  assert.equal(actionSelector('submit_order', document), null)
  assert.equal(safetyBoundaryCode({ url: 'https://cashier.jd.com/pay', title: '', bodyText: '' }),
    'SAFETY_BOUNDARY_CROSSED')
})
```

覆盖禁止文本“提交订单”“确认订单”“去支付”“立即支付”“付款”，以及 `cashier.jd.com`、`pay.jd.com`、订单成功 URL。选择器只允许 `region/specification/quantity_one/buy_now/add_cart/go_checkout` 六种动作；传入其他 kind 直接抛错。

- [ ] **Step 2: 写结算字段与条件价格失败测试**

构造两个静态 DOM：

- 单 SKU、数量 1、区县和街道都匹配、明确应付金额、普通券和已应用国补，得到 verified。
- 自动应用 PLUS/新人/学生/支付/白条/分期/以旧换新任一文本，得到 conditional，并保存原因，不把差额反推为券或国补。

再覆盖 SKU 不符、数量不是 1、只有省市、缺应付金额和要求“选择收货地址”，分别得到 `sku_unconfirmed`、`checkout_region_unconfirmed`、`price_unavailable`、`checkout_address_required`。

- [ ] **Step 3: 写购物车隔离决策失败测试**

```javascript
test('refuses fallback when the target SKU already belongs to the user cart', () => {
  const snapshot = { rows: [{ sku: '1001', quantity: 2, selected: true }] }
  assert.deepEqual(planCartIsolation(snapshot, '1001'), {
    allowed: false,
    code: 'cart_isolation_failed',
  })
})
```

断言只允许“原购物车不存在目标 SKU → 新增后恰好一行目标 SKU”；恢复后原行的 SKU、数量、勾选状态必须逐项一致，且目标新增行消失。

- [ ] **Step 4: 运行 Node 测试确认失败**

Run: `pnpm --dir opencli-plugin-price-compare-jd test`

Expected: FAIL，因为 `lib/jd-checkout.js` 尚不存在。

- [ ] **Step 5: 实现最小纯函数**

金额统一复用 `jd-page.js` 的 `cents`。优惠只识别当前结算块中有明确标签与金额的“店铺优惠/促销优惠”“优惠券”“国家补贴/政府补贴”“运费”；应付金额独立读取，不用公式覆盖页面值。`discount_summary` 只拼接已看见的短标签，最长 2,000 字符。

- [ ] **Step 6: 运行测试并提交**

Run: `pnpm --dir opencli-plugin-price-compare-jd test`

Expected: PASS，且测试没有网络请求。

Commit: `feat: parse JD checkout previews safely`

---

### Task 5: 实现只读结算阶段和可恢复购物车回退命令

**Files:**
- Create: `opencli-plugin-price-compare-jd/checkout-preview.js`
- Modify: `opencli-plugin-price-compare-jd/lib/jd-checkout.js`
- Modify: `opencli-plugin-price-compare-jd/opencli-plugin.json`
- Modify: `opencli-plugin-price-compare-jd/tests/jd-checkout.test.mjs`

**Interfaces:**
- Produces: OpenCLI `price-compare-jd checkout-preview`，`strategy: Strategy.UI`、`access: 'write'`、`browser: true`，每次返回且只返回一个结构化结果。
- Internal: `runCheckoutPreview(page, args)` 可由假 page 测试，不依赖真实京东。

- [ ] **Step 1: 写主路径调用序列失败测试**

假 page 记录 `goto/click/evaluate/wait`。让商品页有唯一“立即购买”，点击后 URL 进入结算预览；断言：

```javascript
assert.deepEqual(fakePage.clickedKinds, ['quantity_one', 'buy_now'])
assert.equal(fakePage.clickCountAfterCheckout, 0)
assert.equal(result.entry_mode, 'buy_now')
assert.equal(result.price_status, 'verified')
```

进入结算 URL 后，`runCheckoutPreview` 只能调用 `evaluate`、读取 URL 或 `goto` 返回商品页，不能再调用 `click`。

- [ ] **Step 2: 写购物车回退与 finally 恢复失败测试**

覆盖以下顺序：读取原购物车快照 → 确认目标 SKU 原先不存在 → 商品页加购数量 1 → 购物车唯一选择新行 → 去结算 → 只读提取 → `finally` 返回购物车、删除本次新增行、恢复原行勾选 → 验证快照一致 → 返回商品页。

让提取结算页抛错，仍必须执行相同恢复；恢复验证失败时最终错误必须是 `CART_ISOLATION_FAILED`，不得用原解析错误掩盖残留购物车风险。

- [ ] **Step 3: 写安全边界失败测试**

假 page 在任何导航后返回收银台/支付/订单成功 URL，应立即抛出 `SAFETY_BOUNDARY_CROSSED`。DOM 同时出现“立即购买”和“提交订单”时只允许前者；结算页内即使有同样的按钮选择器，也不允许点击。

- [ ] **Step 4: 运行测试确认失败**

Run: `pnpm --dir opencli-plugin-price-compare-jd test`

Expected: FAIL，因为命令编排尚不存在。

- [ ] **Step 5: 实现命令和主路径**

命令参数固定为 SKU、省、市、区、街道、四级 area ID 与布尔 `allow-cart-fallback`。先复用 `verify.js` 已验证的 Cookie 设置/回读逻辑；为避免复制，把地区切换函数移到 `lib/jd-page.js` 并保持现有 verify 测试通过。商品页确认 URL SKU、精确规格、库存和数量 1 后，仅点击白名单得到的“立即购买”。

- [ ] **Step 6: 实现受控回退和清理**

只有没有安全“立即购买”且 `allow-cart-fallback=true` 才进入购物车分支。所有购物车变更放入 `try/finally`，日志只记录 SKU、地区代码和状态，不记录页面正文或购物车商品名称。`cart_restored` 只有回读快照逐项一致时为 true。

- [ ] **Step 7: 注册列与安全说明**

命令 columns 必须与 Task 3 的 Pydantic 模型逐字段一致；`opencli-plugin.json` 描述改为“候选读取、地区核验和受保护的结算预览”，不再声称整个插件只读。

- [ ] **Step 8: 运行测试并提交**

Run: `pnpm --dir opencli-plugin-price-compare-jd test`

Expected: PASS；假 page 断言结算页之后点击次数为 0。

Commit: `feat: add guarded JD checkout preview command`

---

### Task 6: 把价目表执行器改为候选 × 31 结算队列

**Files:**
- Modify: `backend/app/price_sheets/executor.py`
- Modify: `backend/app/price_sheets/service.py`
- Modify: `backend/app/price_sheets/coordinator.py`
- Modify: `backend/app/main.py`
- Rewrite: `backend/tests/price_sheets/test_executor.py`
- Modify: `backend/tests/price_sheets/test_service.py`

**Interfaces:**
- Consumes: Task 1 的最多 20 个候选、Task 2 的持久任务、Task 3 的 `CheckoutPreviewGateway`。
- Produces: 候选快照、幂等的 `candidate_count × 31` 任务、逐组合提交、恢复/暂停/停止/失败重试。

- [ ] **Step 1: 写 20 × 31 建队列失败测试**

假网关发现 25 个精确候选，启动一个规格后执行候选阶段：

```python
assert item.candidate_count == 20
assert db.scalar(select(func.count()).select_from(PriceSheetCheckoutTask)) == 620
assert len({(t.price_sheet_item_id, t.region_code, t.platform_sku_id) for t in tasks}) == 620
assert gateway.discover_calls == [('Apple iPhone 17 256GB 黑色', 50)]
```

任务 sequence 固定为 `(candidate_position - 1) * 31 + region.sequence`。再次恢复不得新增任务或再次 discover。

- [ ] **Step 2: 写逐组合结果与恢复失败测试**

假网关返回 verified、conditional 和 unavailable 三类结果，断言每个任务结束即能在新 Session 读到提交结果。把第 8 个任务留为 running 并模拟进程恢复：只把 running 任务重排 queued，不重跑前 7 个 completed/skipped 任务。

- [ ] **Step 3: 写暂停、停止和错误分类失败测试**

断言：

- `login_required/captcha/rate_limited/safety_boundary_crossed` 让批次进入 `waiting_user`，当前任务重新排队；
- `cart_isolation_failed` 让批次进入 `waiting_user` 并留下固定购物车人工检查标记；
- `checkout_address_required/checkout_region_unconfirmed/buy_now_unavailable/sku_unconfirmed/price_unavailable` 保存 unavailable 结果并把任务标为 skipped，继续下一组合；
- `network_error` 最多重试两次后标 failed，继续下一组合；
- `tool_unavailable` 终止批次；
- stop 只在当前命令已返回并完成购物车恢复后生效，不开启下一任务。

- [ ] **Step 4: 运行测试确认旧执行器模型失败**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_executor.py backend/tests/price_sheets/test_service.py -v
```

Expected: FAIL，因为当前执行器只创建 31 个地区任务并读取搜索页价格。

- [ ] **Step 5: 实现候选快照与幂等建队列**

首次处理规格时调用 `gateway.discover(target.query, 50)`，再 `select_price_sheet_candidates(..., limit=20)`，把候选 JSON 与数量一次提交。随后以唯一约束为边界创建 checkout tasks；恢复时只读取 `candidates_json` 与已有任务。

新批次不再创建 `PriceSheetRegionTask`；旧表只留历史兼容。`start_batch` 只把已选规格置 queued，任务由执行器在候选冻结后创建。

- [ ] **Step 6: 实现串行核价和防御性复核**

执行每条任务前通过 `get_region_target(region_code)` 取四级地区；调用 `gateway.checkout_preview(candidate, region, True)`。保存前再次检查：返回 SKU 与任务 SKU 一致、地区已确认、数量约束已由严格输出契约满足、verified 价格无条件原因、应付金额为正。全国价格使用 `payable_price_cents`，不再调用搜索页 `calculate_price_sheet_offer` 推导最终价。

- [ ] **Step 7: 刷新规格和批次状态**

`completed_region_count` 改为存在至少一条 verified 结果的 distinct region 数；`lowest_price_cents` 为 verified 应付金额最小值；所有组合终态后，覆盖 31 个地区为 completed，否则 partial。任务失败计数从 checkout task 聚合，不能把 skipped 当技术失败。

- [ ] **Step 8: 恢复与协调器保持全局单线程**

`recover_interrupted_batches` 处理新任务 running → queued。继续复用现有 `PriceSheetCoordinator(max_workers=1)`；单品自动采集与价目表是否共用浏览器槽的现有约束不得弱化。fixture 模式延迟为 0，生产保持现有节流。

- [ ] **Step 9: 运行测试并提交**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_executor.py backend/tests/price_sheets/test_service.py backend/tests/automation/test_opencli_gateway.py -v
```

Expected: PASS。

Commit: `feat: execute resumable checkout verification queue`

---

### Task 7: 聚合结算进度并按 31 地区覆盖生成结果

**Files:**
- Modify: `backend/app/schemas/price_sheets.py`
- Modify: `backend/app/price_sheets/service.py`
- Modify: `backend/app/api/price_sheets.py`
- Modify: `backend/tests/price_sheets/test_service.py`
- Modify: `backend/tests/api/test_price_sheets.py`

**Interfaces:**
- Extends: `PriceSheetBatchDetail.checkout_progress`。
- Changes: `GET /api/price-sheet-batches/{id}/results` 只从 checkout results 计算全国/部分地区最低价。
- Preserves: 现有识别、校对、start/pause/resume/stop/retry-failed 路由地址。

- [ ] **Step 1: 写汇总进度失败测试**

为一个批次写入 620 个组合，混合状态后断言 API 不返回完整任务数组，而返回：

```json
{
  "stage": "checkout_verification",
  "candidate_count": 20,
  "task_total": 620,
  "task_finished": 127,
  "verified_count": 83,
  "conditional_count": 11,
  "address_required_count": 7,
  "unavailable_count": 18,
  "failed_count": 8,
  "skipped_count": 25,
  "cart_attention_required": false,
  "current": {
    "platform_sku_id": "100209267857",
    "region_code": "110100",
    "address": "北京市 / 朝阳区 / 奥运村街道",
    "entry_mode": "buy_now"
  }
}
```

`task_finished` 只计 completed/failed/skipped；`unavailable_count` 包含全部 unavailable，`address_required_count` 是其子集，因此不要把这些字段相加当总数。

- [ ] **Step 2: 写全国最低覆盖判定失败测试**

构造 31 个地区每区至少一个 verified，外加更低的 conditional 结果；断言只用 verified 的最小应付价。删除任一地区唯一 verified 后，结果转为 `partial` 和 `30/31`，不得进入 `lower_results`。即使某些其他候选组合 failed，只要 31 个地区均有 verified，仍按规格标记 `31/31`，同时保留组合失败计数供用户判断。

- [ ] **Step 3: 写控制接口的 checkout 状态失败测试**

`retry-failed` 只把 failed checkout tasks 重排 queued，不重试 skipped；resume 重排因等待用户而保持 queued 的当前组合；stop 不删除已核验结果。购物车恢复失败后 `cart_attention_required` 刷新与重启后仍为 true。

- [ ] **Step 4: 运行测试确认 schema 缺失**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_service.py backend/tests/api/test_price_sheets.py -v
```

Expected: FAIL，因为 API 尚未返回 checkout 汇总和结算字段。

- [ ] **Step 5: 实现紧凑 schema 与聚合查询**

新增 `PriceSheetCheckoutCurrentView`、`PriceSheetCheckoutProgressView`。`PriceSheetBatchDetail.tasks` 暂时保留旧批次兼容，但新批次返回空列表；新界面只消费 `checkout_progress`。使用 SQL 聚合而不是把 620 行加载后传给前端。

`PriceSheetResultView` 改为结算口径：`entry_mode`、`price_status`、`quantity`、`target_only`、`line_original_price_cents`、`line_sale_price_cents`、`merchant_discount_cents`、`ordinary_coupon_cents`、`subsidy_amount_cents`、`shipping_fee_cents`、`payable_price_cents`、`discount_summary`、`conditional_reason`、`cart_restored`、`captured_at`。

- [ ] **Step 6: 实现结果选择**

每个规格先按 region_code 分组，仅保留 verified；覆盖率是 distinct region 数。只有覆盖 `31/31` 且全局最小 `payable_price_cents < today_price_cents` 才进入 `lower_results`；覆盖完整但不低进入 `not_lower_items`；其余进入 `partial_items`。并列按地区 sequence、候选 snapshot 顺序、SKU 稳定选择。

- [ ] **Step 7: 运行测试并提交**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_service.py backend/tests/api/test_price_sheets.py -v
```

Expected: PASS，响应体不包含手机号、Cookie、完整账号地址、订单号或支付字段。

Commit: `feat: expose checkout verification progress and results`

---

### Task 8: 更新价目表界面的结算核价阶段

**Files:**
- Modify: `frontend/src/types/price-sheets.ts`
- Modify: `frontend/src/stores/price-sheets.ts`
- Modify: `frontend/src/components/PriceSheetComparison.vue`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/price-sheet-comparison.test.ts`
- Modify: `frontend/tests/price-sheet-store.test.ts`

**Interfaces:**
- Consumes: Task 7 的 `checkout_progress` 与结算结果字段。
- Produces: 候选、组合、当前 SKU/地区/入口和分类计数；结果突出一个 verified 全国最低结算价。

- [ ] **Step 1: 写进度界面失败测试**

构造 `checkout_progress`，断言页面显示：

- “结算页核价”；
- “候选 20/20”；
- “组合进度 127/620”；
- 当前 SKU、完整代表街道和“立即购买/购物车回退”；
- 已核验、条件价、需真实地址、不可用、失败、跳过计数；
- “程序只读取结算预览，不会提交订单或付款”。

当 `cart_attention_required=true` 时固定显示“购物车可能未完全恢复，请人工检查”；后续轮询错误清除也不能隐藏，只有新建批次才清除。

- [ ] **Step 2: 写结算结果失败测试**

把现有 `sale_price_cents/trusted_price_cents` 夹具换成结算字段，断言卡片展示页面销售价、商家优惠、普通券、已确认国补、运费和“结算应付”；conditional 价格只在“待处理/条件价”区域显示，不参与绿色最低价卡片。

- [ ] **Step 3: 写 store 恢复和控制失败测试**

刷新后使用 `lastPriceSheetBatchId` 恢复 checkout progress；active 集合包含 queued/running/waiting_user，paused 不自动轮询。`retry-failed` 调用原接口并只依赖服务端重排失败组合。

- [ ] **Step 4: 运行前端测试确认失败**

Run:

```powershell
pnpm --dir frontend test -- price-sheet-comparison.test.ts price-sheet-store.test.ts
```

Expected: FAIL，因为现有类型和组件仍是搜索页地区价格口径。

- [ ] **Step 5: 更新类型和 store**

类型字段与 Pydantic schema 一一对应；不要在前端重新计算是否可信或猜优惠，只格式化后端结果。store 的 `cartAttentionSeen` 在首次发现 true 后保持 true，`reset()` 才清除。

- [ ] **Step 6: 更新组件和样式**

四步标题保持不变，但第 3 步内容改成两阶段：冻结候选、结算页核价。没有任何“自动创建地址”“提交订单”“付款”按钮。结果卡明确标注 `31/31` 或“部分地区最低”，并展示核验时间与入口模式。

- [ ] **Step 7: 运行测试、构建并提交**

Run:

```powershell
pnpm --dir frontend test
pnpm --dir frontend build
```

Expected: 全部 PASS，TypeScript 构建退出码 0。

Commit: `feat: show JD checkout verification workflow`

---

### Task 9: 离线端到端、安全回归和文档收口

**Files:**
- Modify: `backend/app/automation/fixture_gateway.py`
- Modify: `e2e/tests/price-sheet-comparison.spec.ts`
- Modify: `docs/architecture.md`
- Modify: `docs/data-source-policy.md`
- Modify: `docs/platform-adapters.md`
- Modify: `docs/testing.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: 全部前序任务。
- Produces: 完整离线验收、真实单 SKU/单地区人工验收步骤和准确的数据/安全说明。

- [ ] **Step 1: 写离线 E2E 失败场景**

fixture gateway 对一个规格返回 20 个精确候选并创建 620 个快速组合，但只为测试所需结果提供确定性数据。E2E 断言上传/校对后看到结算阶段、最终只显示一条 verified 低价、conditional 更低价没有胜出、完整 31/31 地址覆盖存在，并在刷新后恢复同一批次。

再加一个独立 fixture 批次令某地区只有 `checkout_address_required`，断言显示部分覆盖且不称为全国最低；令购物车恢复失败，断言持久警告出现。测试不得加载真实京东 URL。

- [ ] **Step 2: 运行 E2E 确认夹具尚未支持新契约**

Run: `pnpm --dir e2e test -- price-sheet-comparison.spec.ts`

Expected: FAIL，因为 fixture gateway 没有 `checkout_preview`。

- [ ] **Step 3: 实现离线 fixture gateway**

实现与生产相同 `CheckoutPreviewGateway` 方法但仅返回内存数据；测试组合不调用 OpenCLI。fixture 可按 region code/SKU 注入 verified、conditional、unavailable 或 `GatewayFailure`，默认应付金额明确且地区确认 true。

- [ ] **Step 4: 更新文档中的旧只读描述**

文档明确：

- 插件搜索/地区展示命令仍为 read，`checkout-preview` 为受控 write；
- 优先立即购买，有限购物车回退会短暂改变购物车但必须恢复；
- 程序不创建地址、不提交订单、不付款；
- 搜索页价格不再作为最终价，最终排序使用结算页明确应付金额；
- 最多 20 × 31，可能运行数小时；
- 全国最低要求 31 个地区各至少一条 verified 无条件结果；
- 真实验收由用户关闭代理后进行。

把 `docs/data-source-policy.md` 的“No Automated Ordering”改成“允许受保护的结算预览，不允许提交订单和付款”；不要保留“插件不访问购物车/结算”的过期说法。

- [ ] **Step 5: 运行针对性全栈验证**

Run:

```powershell
pnpm --dir opencli-plugin-price-compare-jd test
backend\.venv\Scripts\python.exe -m pytest backend/tests/db/test_checkout_preview_migration.py backend/tests/automation/test_opencli_gateway.py backend/tests/price_sheets backend/tests/api/test_price_sheets.py -v
pnpm --dir frontend test
pnpm --dir frontend build
pnpm --dir e2e test -- price-sheet-comparison.spec.ts
```

Expected: 全部 PASS；无测试访问 `jd.com`。

- [ ] **Step 6: 运行完整回归**

Run: `powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1`

Expected: 构建、OpenCLI 插件、后端、前端、扩展和离线 E2E 全部 PASS。

- [ ] **Step 7: 执行安全静态检查**

Run:

```powershell
rg -n "提交订单|确认订单|去支付|立即支付|付款|order_id|payment_id|payment_status|pay_url" backend opencli-plugin-price-compare-jd frontend
rg -n "姓名|手机号|收货人|address.*save|address.*delete" backend opencli-plugin-price-compare-jd frontend
git diff --check
```

Expected: 禁止词只出现在 denylist、测试断言、错误说明和文档中；没有对应点击动作、命令参数、输出字段或地址写入实现。`git diff --check` 无输出。

- [ ] **Step 8: 检查提交范围并提交**

Run:

```powershell
git status --short
git log --oneline --decorate -12
```

确认 Global Constraints 中列出的用户未提交文件未被覆盖或加入暂存。

Commit: `docs: document guarded JD checkout verification`

- [ ] **Step 9: 交给用户做真实单组合验收**

用户关闭代理、保持 Chrome/OpenCLI Browser Bridge/京东登录态可用，只运行一个 SKU × 一个地区。用户目视确认未提交订单、未进入支付页、数量为 1、SKU/区县/街道/应付金额一致；再单独测试一次需要购物车回退的商品并人工核对购物车完全恢复。两个冒烟均通过后，才启动完整 31 地区批次。

真实验收不作为自动测试成功的替代；执行者不得替用户运行真实加购或结算操作。
