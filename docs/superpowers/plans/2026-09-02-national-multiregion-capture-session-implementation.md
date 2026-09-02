# 全国多地区报价与采集会话实现计划

> **给 agentic 执行者:** 必须使用 superpowers:executing-plans 逐任务实现本计划。用户已明确要求不使用 subagent。步骤使用 checkbox（`- [ ]`）跟踪。

**目标:** 建立全国采集会话、多地区报价独立保存、工作台会话生命周期和扩展会话校验的完整离线数据闭环。

**架构:** SQLite 通过 `comparison_scope` 和 `region_key` 显式表达会话范围与报价地区身份；FastAPI 共享预览/完成结果构建和默认排序；Vue 管理采集会话与独立离线演示；MV3 扩展持久化并验证会话后才执行用户主动采集。

**技术栈:** Python 3.12、FastAPI 0.141.1、Pydantic 2.13.5、SQLAlchemy 2.0.52、Alembic 1.19.1、SQLite、Vue 3.5.42、Pinia 4.0.3、TypeScript 6.0.2、Vitest 4.1.11、Manifest V3、Playwright 1.62.1、PowerShell。

**Spec:** `docs/superpowers/specs/2026-09-02-national-multiregion-capture-session-design.md`

## 全局约束

- 仅在用户本机运行，后端继续绑定 `127.0.0.1`。
- 不保存平台账号、密码、Cookie、手机号、地址、身份信息或完整页面 HTML。
- 不增加云服务、后台爬虫、登录/验证码自动化或无关扩展权限。
- 固定夹具始终标记为 `fixture` 和 `example.invalid`；真实网站状态保持 `not_validated`。
- 估算补贴、会员价、支付价、以旧换新价和分期月供都不参与默认排序。
- 所有金额继续使用整数分；保留现有 PowerShell 构建、测试和演示流程。
- 只在 `feature/national-multiregion-capture-session` 创建本地提交；不 push、不建 PR、不合并。

---

### 任务 1：会话范围与地区身份

**文件:**
- 创建：`backend/app/services/region_identity.py`
- 创建：`backend/tests/services/test_region_identity.py`
- 创建：`backend/tests/services/test_search_session_scope.py`
- 修改：`backend/app/schemas/search_sessions.py`

**接口:**
- 产出：`normalize_region_name(value: str) -> str`
- 产出：`build_region_key(region_code: str | None, region_name: str | None) -> str`
- 产出：`CreateSearchSession.comparison_scope: Literal['national', 'regional']`

- [ ] **步骤 1：写地区身份失败测试**

```python
@pytest.mark.parametrize(("code", "name", "expected"), [
    ("310100", "上海市", "code:310100"),
    (None, "  上 海市  ", "name:上 海市"),
    (None, "全国", "national"),
    (None, None, "unknown"),
])
def test_build_region_key(code, name, expected):
    assert build_region_key(code, name) == expected

def test_region_code_conflicts_with_national_name():
    with pytest.raises(ValueError, match="地区代码不能与全国适用同时出现"):
        build_region_key("310100", "全国")
```

- [ ] **步骤 2：运行测试确认 RED**

运行：`Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests\services\test_region_identity.py -v; Pop-Location`

预期：因 `app.services.region_identity` 不存在而失败。

- [ ] **步骤 3：实现最小地区身份模块**

```python
def normalize_region_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()

def build_region_key(region_code: str | None, region_name: str | None) -> str:
    normalized = normalize_region_name(region_name) if region_name else ""
    if region_code and normalized == "全国":
        raise ValueError("地区代码不能与全国适用同时出现")
    if region_code:
        return f"code:{region_code}"
    if normalized == "全国":
        return "national"
    if normalized:
        return f"name:{normalized}"
    return "unknown"
```

- [ ] **步骤 4：写会话范围请求模型失败测试**

```python
def test_scope_is_inferred_from_region():
    assert CreateSearchSession(variant_id=1).comparison_scope == "national"
    assert CreateSearchSession(variant_id=1, region_code="310100").comparison_scope == "regional"

def test_scope_conflicts_are_rejected():
    with pytest.raises(ValidationError, match="全国会话不能设置统一地区"):
        CreateSearchSession(variant_id=1, comparison_scope="national", region_code="310100")
    with pytest.raises(ValidationError, match="地区会话必须设置地区"):
        CreateSearchSession(variant_id=1, comparison_scope="regional")
```

- [ ] **步骤 5：运行会话测试确认 RED**

运行：`Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests\services\test_search_session_scope.py -v; Pop-Location`

预期：请求模型缺少 `comparison_scope`。

- [ ] **步骤 6：实现 Pydantic 推断与冲突校验**

在 `CreateSearchSession` 使用 `model_validator(mode="after")`：缺省范围按 `region_code` 推断，显式冲突抛出 `ValueError`。`SearchSessionView` 和 `SearchResult` 的响应字段在任务 2 与数据库列一起加入。

```python
comparison_scope: Literal["national", "regional"] | None = None

@model_validator(mode="after")
def resolve_scope(self):
    scope = self.comparison_scope or ("regional" if self.region_code else "national")
    if scope == "national" and self.region_code is not None:
        raise ValueError("全国会话不能设置统一地区")
    if scope == "regional" and self.region_code is None:
        raise ValueError("地区会话必须设置地区")
    self.comparison_scope = scope
    return self
```

- [ ] **步骤 7：运行任务 1 测试并提交**

运行：`Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests\services\test_region_identity.py tests\services\test_search_session_scope.py -v; Pop-Location`

提交：`git commit -am "feat(domain): define comparison scope and region identity"`，并显式 `git add` 新测试和模块。

---

### 任务 2：SQLite 多地区迁移

**文件:**
- 创建：`backend/alembic/versions/0005_national_multiregion_sessions.py`
- 创建：`backend/tests/db/test_multiregion_migration.py`
- 修改：`backend/app/db/models/offers.py`
- 修改：`backend/app/schemas/search_sessions.py`
- 修改：`backend/app/services/search_sessions.py`
- 修改：`backend/tests/api/test_search_flow.py`

**接口:**
- 消费：`build_region_key(...)`
- 产出：`SearchSession.comparison_scope`
- 产出：`Offer.region_key`
- 产出：唯一约束 `uq_offers_session_platform_sku_region`

- [ ] **步骤 1：写迁移与 API 响应失败测试**

测试从 `0004_offer_regions` 建库并插入旧会话/报价，升级后断言：空地区会话为 `national`、有地区会话为 `regional`、报价为 `code:310100`、新列非空且新唯一约束允许同 SKU 不同 `region_key`。另建两个不同地区身份的同 SKU 报价，断言降级抛出 `RuntimeError("存在跨地区重复报价")` 且两条报价仍存在。API 测试断言旧调用推断后的响应始终返回明确 `comparison_scope`，冲突请求返回结构化 422。

- [ ] **步骤 2：运行迁移测试确认 RED**

运行：`Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests\db\test_multiregion_migration.py -v; Pop-Location`

预期：Alembic head 不含 0005，新列查询失败。

- [ ] **步骤 3：实现迁移与 ORM 字段**

迁移先添加可空列并通过 SQL 回填，再用 `batch_alter_table` 改为非空并替换唯一约束。降级第一条语句执行：

```sql
SELECT search_session_id, platform_id, platform_sku_id
FROM offers
GROUP BY search_session_id, platform_id, platform_sku_id
HAVING COUNT(*) > 1
LIMIT 1
```

有结果即抛出 `RuntimeError("存在跨地区重复报价；请先备份并人工处理后再降级")`，不执行任何 DDL。

- [ ] **步骤 4：运行迁移与既有数据库测试**

运行：`Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests\db\test_multiregion_migration.py tests\db\test_migrations.py -v; Pop-Location`

预期：全部通过，空库可升级/降级，冲突库拒绝降级且不丢数据。

- [ ] **步骤 5：提交**

提交：`git add backend/alembic/versions/0005_national_multiregion_sessions.py backend/app/db/models/offers.py backend/tests/db; git commit -m "feat(db): preserve offers across regions"`

---

### 任务 3：多地区报价写入与地区补贴

**文件:**
- 修改：`backend/app/services/search_sessions.py`
- 修改：`backend/app/services/offer_ingestion.py`
- 修改：`backend/app/subsidy/engine.py`
- 修改：`backend/tests/db/test_offer_persistence.py`
- 修改：`backend/tests/api/test_search_flow.py`
- 修改：`backend/tests/subsidy/test_engine.py`

**接口:**
- 消费：`build_region_key(...)`
- 产出：`resolve_offer_region(search, raw) -> tuple[str | None, str | None, str]`

- [ ] **步骤 1：写同 SKU 多地区和同地区更新失败测试**

在同一全国会话保存两次上海报价和一次北京报价，使用相同 `platform_sku_id`。断言当前报价两条、上海为最新价格、北京独立存在、上海两条快照、北京一条快照。

- [ ] **步骤 2：运行持久化测试确认 RED**

运行：`Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests\db\test_offer_persistence.py -v; Pop-Location`

预期：报价查询仍按旧三字段更新，或新非空 `region_key` 未写入。

- [ ] **步骤 3：实现地区解析和四字段报价身份**

```python
def resolve_offer_region(search: SearchSession, code: str | None, name: str | None):
    resolved_code = code
    if search.comparison_scope == "regional" and resolved_code is None:
        resolved_code = search.region_code
    key = build_region_key(resolved_code, name)
    return resolved_code, name, key
```

报价查找加入 `Offer.region_key == region_key`，写入同步设置三个地区字段。全国会话不回退会话地区。

- [ ] **步骤 4：写独立地区补贴失败测试**

向全国会话提交上海、北京和未知地区报价，数据库只配置北京规则。断言北京为 `estimated`、上海和未知为 `unknown`，未知原因是“该报价未提供适用地区，无法匹配地区补贴规则”。

- [ ] **步骤 5：运行补贴测试确认 RED**

运行：`Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests\api\test_search_flow.py tests\subsidy\test_engine.py -v; Pop-Location`

预期：旧的缺地区文案或地区回退逻辑使断言失败。

- [ ] **步骤 6：实现每条报价独立补贴上下文**

在进入 `evaluate_subsidy` 前只解析一次地区，并把同一结果传给 `evaluated`；把缺地区原因更新为指定文案。平台明确确认补贴仍优先且只影响同一 SKU 的确认价格。

- [ ] **步骤 7：运行任务 3 测试并提交**

运行：`Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests\db\test_offer_persistence.py tests\api\test_search_flow.py tests\subsidy\test_engine.py -v; Pop-Location`

提交：`git add backend/app backend/tests; git commit -m "fix(domain): keep regional offers and subsidies independent"`

---

### 任务 4：预览接口与统一默认排序

**文件:**
- 修改：`backend/app/services/search_sessions.py`
- 修改：`backend/app/api/search_sessions.py`
- 修改：`backend/app/pricing/sorting.py`
- 修改：`backend/tests/api/test_search_flow.py`
- 修改：`backend/tests/pricing/test_sorting.py`

**接口:**
- 产出：`build_search_result(db: Session, session_id: int) -> SearchResult`
- 产出：`GET /api/search-sessions/{session_id}/result`

- [ ] **步骤 1：写预览/完成顺序失败测试**

创建 collecting 会话并导入价格顺序打乱的报价，调用预览，断言状态仍为 `collecting`；再完成会话，断言报价 ID 顺序与预览完全相同且状态为 `completed`。不存在 ID 的预览返回结构化 404。

- [ ] **步骤 2：写条件价排序不变量测试**

构造普通价 499900 和普通价 509900/条件价 399900 两条报价，断言 `sort_offers` 仍返回 `[499900, 509900]`。

- [ ] **步骤 3：运行测试确认 RED**

运行：`Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests\api\test_search_flow.py tests\pricing\test_sorting.py -v; Pop-Location`

预期：预览路由 404，完成服务仍复制排序代码。

- [ ] **步骤 4：实现共享结果构建**

```python
def build_search_result(db: Session, session_id: int) -> SearchResult:
    search = require_search_session(db, session_id)
    offers = sort_offers(list_offer_views(db, session_id))
    return SearchResult(id=search.id, comparison_scope=search.comparison_scope,
                        status=search.status, offers=offers,
                        excluded_count=count_excluded(db, session_id))
```

预览只调用该函数；完成接口先更新状态并提交，再调用该函数。删除服务内复制的 lambda 排序。

- [ ] **步骤 5：运行任务 4 测试并提交**

运行：`Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests\api\test_search_flow.py tests\pricing\test_sorting.py -v; Pop-Location`

提交：`git add backend/app backend/tests; git commit -m "feat(api): preview collection sessions with shared sorting"`

---

### 任务 5：四地区夹具与报价展示不变量

**文件:**
- 修改：`fixtures/jd/search-results.json`
- 修改：`fixtures/pdd/search-results.json`
- 修改：`frontend/src/stores/comparison.ts`
- 修改：`frontend/src/components/OfferTable.vue`
- 修改：`frontend/src/components/OfferDetails.vue`
- 修改：`frontend/src/styles.css`
- 修改：`frontend/tests/comparison-results.test.ts`

**接口:**
- 产出：`selectVisibleOffers(offers, options) -> OfferView[]` 始终保持输入顺序
- 产出：`lowestOfferSummary(offers) -> { price: number | null; regions: string[] }`

- [ ] **步骤 1：写前端排序和地区展示失败测试**

断言勾选前后报价 ID 都为 `[1, 2]`；两条同价报价显示“最低价地区：上海市、北京市”；每行显示自己的适用地区；未知地区显示“地区未确认”；全部 `comparable_price_cents=null` 时没有“最低”且显示“暂无可靠可比价”。

- [ ] **步骤 2：运行组件测试确认 RED**

运行：`pnpm --dir frontend test -- comparison-results.test.ts`

预期：条件价排序变成 `[2, 1]`，非首行地区和并列最低文案缺失。

- [ ] **步骤 3：实现最小展示逻辑**

`selectVisibleOffers` 返回 `offers`；最低价 computed 只读取非空 comparable price。每行地区文案优先 `region_name`、`region_code`、`地区未确认`。可靠最低报价行显示“最低”，并在列表顶部显示并列地区摘要。

- [ ] **步骤 4：升级固定夹具**

京东 JSON 增加相同 `jd-sku-256-black` 的北京报价 519900；拼多多有效北京报价增加 `conditional_price_cents: 399900`。四条有效报价的默认价格固定为 499900、504900、509900、519900。

- [ ] **步骤 5：运行组件与后端流程测试并提交**

运行：`pnpm --dir frontend test -- comparison-results.test.ts`

运行：`Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests\api\test_search_flow.py -v; Pop-Location`

提交：`git add fixtures frontend; git commit -m "fix(ui): show every region without conditional reranking"`

---

### 任务 6：工作台采集会话 store 与恢复

**文件:**
- 修改：`backend/app/api/catalog.py`
- 修改：`backend/app/services/catalog.py`
- 修改：`backend/app/schemas/catalog.py`
- 修改：`backend/tests/api/test_catalog.py`
- 修改：`frontend/src/api/client.ts`
- 修改：`frontend/src/stores/catalog.ts`
- 修改：`frontend/src/stores/comparison.ts`
- 修改：`frontend/src/types/offers.ts`
- 创建：`frontend/tests/collection-session.test.ts`

**接口:**
- 产出：`GET /api/catalog/variants/{variant_id}`
- 产出：store actions `createCollectionSession`, `refreshCollectionSession`, `finalizeCollectionSession`, `restoreCollectionSession`, `runFixtureComparison`

- [ ] **步骤 1：写标准 SKU 恢复 API 失败测试**

调用现有 variant ID，断言返回完整 `CatalogVariantView`；不存在 ID 返回结构化 404。

- [ ] **步骤 2：运行后端测试确认 RED**

运行：`Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests\api\test_catalog.py -v; Pop-Location`

预期：路由不存在。

- [ ] **步骤 3：实现只读 variant 路由**

新增 `get_catalog_variant(db, id) -> CatalogVariantView`，只查询 active、未删除变体；API 将缺失映射为结构化 404。

- [ ] **步骤 4：写 Pinia 会话生命周期失败测试**

使用真实 store 和按 URL 返回完整 JSON 的 fetch fake，断言创建时发送 `comparison_scope=national` 并保存两个 ID；刷新调用 `/result`；完成调用 `/finalize`；恢复按顺序读取 session、variant、result；404 清除 ID，网络错误保留 ID。

- [ ] **步骤 5：运行前端 store 测试确认 RED**

运行：`pnpm --dir frontend test -- collection-session.test.ts`

预期：actions 不存在。

- [ ] **步骤 6：实现 store 与类型**

状态增加 `session: SearchSessionView | null` 和 `restoreMessage`。`CreateSearchCommand` 明确发送 `comparison_scope: 'national'`；固定演示动作保留自动导入和完成。成功创建/恢复时同步 `lastSessionId`、`lastVariantId`；仅确认 404 失效时清理。

- [ ] **步骤 7：运行任务 6 测试并提交**

运行：`Push-Location backend; .\.venv\Scripts\python.exe -m pytest tests\api\test_catalog.py -v; Pop-Location`

运行：`pnpm --dir frontend test -- collection-session.test.ts`

提交：`git add backend frontend; git commit -m "feat(ui): manage national collection session lifecycle"`

---

### 任务 7：工作台采集会话界面

**文件:**
- 创建：`frontend/src/components/CollectionSessionCard.vue`
- 修改：`frontend/src/pages/WorkspacePage.vue`
- 修改：`frontend/src/styles.css`
- 修改：`frontend/tests/workspace-model-selection.test.ts`
- 创建：`frontend/tests/workspace-collection-session.test.ts`

**接口:**
- 消费：任务 6 的 store actions 和状态
- 产出：`data-testid`：`create-collection-session`、`collection-session-id`、`copy-session-id`、`refresh-session`、`finalize-session`、`run-fixture-comparison`

- [ ] **步骤 1：写界面失败测试**

断言未确认 SKU 时创建和演示按钮禁用；确认后创建会话，显示 ID、采集中、全国和 SKU；复制按钮调用 `navigator.clipboard.writeText('123')`；完成后完成按钮禁用；页面挂载调用恢复动作；固定演示说明含“固定夹具，不代表真实平台价格”。

- [ ] **步骤 2：运行界面测试确认 RED**

运行：`pnpm --dir frontend test -- workspace-collection-session.test.ts workspace-model-selection.test.ts`

预期：采集会话控件不存在。

- [ ] **步骤 3：实现会话卡和页面动作**

会话卡只接收会话、SKU、loading props 和 create/refresh/finalize/recreate/copy emits。页面在 `onMounted` 调用恢复；真实采集与离线演示使用独立按钮和 loading 文案。CSS 在 520px 下让操作按钮换行且 `min-width: 0`。

- [ ] **步骤 4：运行所有前端测试和构建并提交**

运行：`pnpm --dir frontend test`

运行：`pnpm --dir frontend build`

提交：`git add frontend; git commit -m "feat(ui): expose collection sessions in workspace"`

---

### 任务 8：扩展会话持久化、校验与提交反馈

**文件:**
- 创建：`extension/src/shared/collection-session.ts`
- 修改：`extension/src/shared/api.ts`
- 修改：`extension/src/shared/types.ts`
- 修改：`extension/src/popup/main.ts`
- 修改：`extension/src/popup/index.html`
- 修改：`extension/src/background/index.ts`
- 创建：`extension/tests/collection-session.test.ts`
- 修改：`extension/tests/pairing.test.ts`

**接口:**
- 产出：`saveSearchSessionId(value: number, storage: ExtensionStorage) -> Promise<void>`
- 产出：`loadSearchSessionId(storage) -> Promise<number | null>`
- 产出：`validateCollectionSession(id, backendUrl, fetcher) -> Promise<SearchSessionView>`
- 产出：`formatIngestionSummary(summary, sessionId) -> string`

- [ ] **步骤 1：写扩展会话失败测试**

用内存 storage 断言 ID 写入/恢复；fake fetch 分别返回不存在、completed、regional、服务抛错和有效 national collecting；断言中文错误类别不同。用 accepted/excluded JSON 断言成功和全部排除反馈包含实际计数和原因。

- [ ] **步骤 2：运行扩展测试确认 RED**

运行：`pnpm --dir extension test -- collection-session.test.ts`

预期：模块与函数不存在。

- [ ] **步骤 3：实现共享会话函数**

持久化键固定为 `searchSessionId` 字符串。校验先请求 `/api/search-sessions/{id}`，要求 `status==='collecting'` 且 `comparison_scope==='national'`。网络异常、404、完成和地区会话分别抛出不同安全文案。

- [ ] **步骤 4：接入弹窗与后台提交**

弹窗加载时恢复 ID，输入变化时保存有效正整数；采集前后台再次验证会话，然后注入、解析、提交。提交响应读取 `accepted_count`、`excluded_count`、`exclusions` 并格式化，不记录 Authorization 头或令牌。

- [ ] **步骤 5：运行扩展测试和构建并提交**

运行：`pnpm --dir extension test`

运行：`pnpm --dir extension build`

提交：`git add extension; git commit -m "feat(extension): persist and validate collection sessions"`

---

### 任务 9：内容脚本幂等安装与隐私边界

**文件:**
- 修改：`extension/src/content/capture.ts`
- 创建：`extension/tests/capture-listener.test.ts`
- 修改：`extension/tests/privacy-boundary.test.ts`

**接口:**
- 产出：`installCaptureListener(runtime, capture, target) -> void`
- 唯一标记：`__personalSubsidyPriceCaptureInstalledV1`

- [ ] **步骤 1：写监听器失败测试**

使用记录 `addListener` 次数的 fake runtime：同一 target 调用两次只注册一次；新 target 再调用会注册；触发 listener 的 `CAPTURE_PAGE` 消息会返回 capture 结果。

- [ ] **步骤 2：运行测试确认 RED**

运行：`pnpm --dir extension test -- capture-listener.test.ts`

预期：导出函数不存在。

- [ ] **步骤 3：实现幂等安装**

```typescript
const MARKER = '__personalSubsidyPriceCaptureInstalledV1'
export function installCaptureListener(runtime, capture, target) {
  if (target[MARKER]) return
  target[MARKER] = true
  runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.type !== 'CAPTURE_PAGE') return false
    sendResponse(capture())
    return false
  })
}
```

模块入口以 `globalThis` 作为 target，调用真实 runtime 和当前 document capture。

- [ ] **步骤 4：加强权限与敏感字段测试**

断言权限仍精确为 `activeTab/storage/scripting`，host 仍仅回环地址；扩展 storage 允许键集合只有 `backendUrl/extensionToken/searchSessionId`，没有 cookie/password/address/phone/html。

- [ ] **步骤 5：运行完整扩展套件并提交**

运行：`pnpm --dir extension test`

提交：`git add extension; git commit -m "fix(extension): install capture listener once per document"`

---

### 任务 10：离线 E2E、文档、构建与人工验收

**文件:**
- 修改：`e2e/tests/offline-comparison.spec.ts`
- 修改：`README.md`
- 修改：`docs/architecture.md`
- 修改：`docs/data-source-policy.md`
- 修改：`docs/platform-adapters.md`
- 修改：`docs/subsidy-rules.md`
- 修改：`docs/testing.md`
- 创建：`docs/collection-session.md`

**接口:**
- 消费：前九个任务的公开 API、测试 ID 和固定夹具
- 产出：阶段 1 可重复验收证据

- [ ] **步骤 1：先更新 E2E 为完整失败验收**

测试创建采集会话，读取 ID，通过 page request 向同一会话导入四地区夹具，手动刷新并断言四行报价和 ID 顺序；勾选条件价后顺序不变；刷新页面恢复；完成会话；完成后 POST 报价为 422；随后运行独立离线演示并确认仍为四条固定报价。

- [ ] **步骤 2：运行 E2E 确认 RED 或记录首次 GREEN 原因**

运行：`pnpm --dir e2e test`

预期：在页面流程尚未完全接线时失败；若前序任务已经使其首次通过，记录它是跨组件验收补充，核心行为均已分别完成 RED→GREEN。

- [ ] **步骤 3：补齐 E2E 所需最小接线并运行 GREEN**

运行：`pnpm --dir e2e test`

预期：1 个完整 Edge 离线场景通过且不访问真实购物网站。

- [ ] **步骤 4：更新文档**

文档明确全国采集只覆盖已采集地区、同 SKU 多地区身份、会话状态机、扩展保存 ID、预览/完成共享排序、未知地区补贴、真实网站仍未验证和阶段 2 前置条件。

- [ ] **步骤 5：运行完整自动化与构建**

依次记录退出码、数量和耗时：

```powershell
.\scripts\build.ps1
.\scripts\test.ps1
Push-Location backend
.\.venv\Scripts\python.exe -m pytest -v
Pop-Location
pnpm --dir frontend test
pnpm --dir frontend build
pnpm --dir extension test
pnpm --dir extension build
pnpm --dir e2e test
```

- [ ] **步骤 6：运行演示与人工 Edge 验收**

运行 `.\scripts\demo.ps1`，验证健康接口、生产页面、采集会话、四地区报价、条件价顺序、恢复、完成、窄屏和扩展弹窗；记录 Windows 与 Edge 版本。演示保持运行只到验收结束，然后安全停止测试进程。

- [ ] **步骤 7：安全与隐私检查**

运行 `git grep -n -I -E "cookie|password|authorization|bearer|token|手机号|身份证|收货地址"`，人工确认只有代码字段或文档说明，没有真实秘密；检查 manifest、绑定地址和工作树。

- [ ] **步骤 8：提交文档与最终接线**

提交：`git add e2e README.md docs; git commit -m "docs: document nationwide collection workflow"`

- [ ] **步骤 9：最终验证、状态与报告数据**

运行：`git diff origin/main...HEAD --check; git status --short; git log origin/main..HEAD --oneline; git rev-parse HEAD`

工作树必须干净。输出阶段 1 报告所需的分支、完整 SHA、提交列表、迁移、报价表、排序、会话、扩展、测试、构建、人工验收、安全、文件清单和已知限制；不 push。
