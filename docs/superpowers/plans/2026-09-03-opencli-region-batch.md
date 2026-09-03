# OpenCLI 地区批量核价实现计划

> **给 agentic 执行者:** 必须使用 superpowers:executing-plans 在当前会话逐任务实现本计划。步骤用 checkbox(`- [ ]`)语法跟踪。

**目标:** 把京东浏览器核价从“每个地区逐商品打开详情页”改为“每个地区只打开一次搜索页并批量读取候选”，同时准确暂停桥接断开和访问频繁状态。

**架构:** 保留现有 `BrowserGateway.verify` 兼容路径，新增可选 `RegionBatchGateway.verify_region` 能力。`CollectionExecutor` 检测到批量能力时每地区调用一次；OpenCLI 插件新增 `verify-region` 命令，从地区搜索结果生成白名单报价。

**技术栈:** Python 3.12、FastAPI、Pydantic、Node.js 24、OpenCLI 1.8.7、Node test、pytest。

**Spec:** 本会话已批准的内部修复设计；前端、数据库及全国任务接口保持不变。

## 全局约束

- 不绕过京东验证码或安全验证。
- 不保存 Cookie、密码、页面 HTML 或 OpenCLI 原始错误输出。
- 每个地区最多一次批量搜索页导航；访问频繁时暂停任务，不立即重试。
- 只接收本次候选 SKU 白名单内的报价。
- 保留原有逐商品 `verify` 作为非批量网关的兼容路径。

---

### 任务 1：错误识别与搜索报价标准化

**文件:**
- 修改: `opencli-plugin-price-compare-jd/lib/jd-page.js`
- 测试: `opencli-plugin-price-compare-jd/tests/jd-page.test.mjs`

**接口:**
- 产出: `pageFailureCode(title, bodyText)` 返回 `RATE_LIMITED` 或 `PAGE_CHANGED`。
- 产出: `searchRowsToVerifiedOffers(rows, allowedSkus, capturedAt)` 返回报价契约数组。

- [ ] **步骤 1: 写失败测试**

```javascript
assert.equal(pageFailureCode('商品搜索', '抱歉由于访问频繁导致无法搜索'), 'RATE_LIMITED')
assert.equal(pageFailureCode('京东商品', '暂时无法展示该商品的信息'), 'PAGE_CHANGED')
assert.deepEqual(searchRowsToVerifiedOffers(rows, ['1001'], capturedAt).map(x => x.platform_sku_id), ['1001'])
```

- [ ] **步骤 2: 跑测试确认失败**

运行: `node --test opencli-plugin-price-compare-jd/tests/jd-page.test.mjs`
预期: FAIL，缺少错误映射或 `searchRowsToVerifiedOffers`。

- [ ] **步骤 3: 写最小实现**

将访问频繁映射为 `RATE_LIMITED`，详情占位页映射为 `PAGE_CHANGED`；把已标准化搜索候选映射为不虚构优惠、补贴和条件价的 `VerifiedOffer`。

- [ ] **步骤 4: 跑测试确认通过**

运行: `node --test opencli-plugin-price-compare-jd/tests/jd-page.test.mjs`
预期: PASS。

### 任务 2：OpenCLI 地区批量命令与后端网关

**文件:**
- 修改: `opencli-plugin-price-compare-jd/verify.js`
- 修改: `backend/app/automation/contracts.py`
- 修改: `backend/app/automation/opencli.py`
- 测试: `backend/tests/automation/test_opencli_gateway.py`

**接口:**
- 产出: OpenCLI 命令 `verify-region <query> --skus <csv> --province --city --district`。
- 产出: `RegionBatchGateway.verify_region(query, candidates, region) -> list[VerifiedOffer]`。

- [ ] **步骤 1: 写失败测试**

```python
offers = gateway.verify_region("Apple iPhone 17 256GB", candidates, beijing)
assert runner.calls == [[OPENCLI_EXECUTABLE, "price-compare-jd", "verify-region", ...]]
assert [offer.platform_sku_id for offer in offers] == ["100000000001"]
```

- [ ] **步骤 2: 跑测试确认失败**

运行: `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/automation/test_opencli_gateway.py -q`
预期: FAIL，`OpenCliGateway` 尚无 `verify_region`。

- [ ] **步骤 3: 写最小实现**

注册 `verify-region`，设置一次地区后等待搜索结果，过滤候选白名单并输出报价；Python 网关构造参数数组、验证输出和 SKU 子集。

- [ ] **步骤 4: 跑测试确认通过**

运行插件测试及 `backend/tests/automation/test_opencli_gateway.py`，预期全部 PASS。

### 任务 3：执行器每地区只调用一次批量核价

**文件:**
- 修改: `backend/app/automation/executor.py`
- 修改: `backend/app/automation/jd_union.py`
- 测试: `backend/tests/automation/test_executor.py`
- 测试: `backend/tests/automation/test_jd_union.py`

**接口:**
- 消费: `RegionBatchGateway.verify_region(query, candidates, region)`。
- 产出: 支持批量能力时31地区恰好31次浏览器核价调用。

- [ ] **步骤 1: 写失败测试**

```python
assert len(gateway.verify_region_calls) == 31
assert gateway.verify_calls == []
assert db.scalar(select(func.count(Offer.id))) == 62
```

- [ ] **步骤 2: 跑测试确认失败**

运行: `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/automation/test_executor.py -q`
预期: FAIL，执行器仍逐商品调用。

- [ ] **步骤 3: 写最小实现**

执行器加载或发现候选时同时保留标准查询词；批量网关每地区返回报价列表并逐条走现有入库，非批量网关保持原流程。`OfficialFirstJdGateway` 透传批量核价。

- [ ] **步骤 4: 跑测试确认通过**

运行后端自动采集测试，预期全部 PASS。

### 任务 4：完整验证与现场冒烟

**文件:**
- 修改: `docs/platform-adapters.md`

- [ ] **步骤 1: 运行完整离线验证**

运行: `.\\scripts\\test.ps1`
预期: 构建、插件、后端、前端、扩展和端到端测试全部通过。

- [ ] **步骤 2: 运行三地区现场冒烟**

依次执行北京、上海、广东 `verify-region`，每次限制5条。预期: 返回白名单报价，或在京东访问频繁时明确返回 `rate_limited` 并安全暂停；不得再误报 `unsupported_region`。

- [ ] **步骤 3: 提交限定文件**

只暂存本计划列出的实现、测试和文档文件，检查不包含凭据、Cookie 或 trace 文件后提交。
