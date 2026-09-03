# 价目表图片 OCR 与京东全国最低价实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 上传竖版手机价目表后，在本机识别并校对每个颜色规格，自动核验京东 31 个代表街道，只展示严格低于今日价的一条可信最低结果。

**Architecture:** 新增独立的 `price_sheets` 后端域，不把 OCR 条目写入现有商品目录或 `SearchSession`。批次、条目、地区任务和每地区最低结果持久化到 SQLite；单线程执行器复用现有 `BrowserGateway`，但使用颜色精确匹配和不重复扣减的价目表价格计算器。Vue 工作台增加独立四步流程。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy 2、Alembic、Pillow 12.3.0、PaddleOCR 3.7.0、PaddlePaddle 3.3.0 CPU、pytest、Vue 3、Pinia、TypeScript、Vitest、OpenCLI、Node.js test runner

**Spec:** `docs/superpowers/specs/2026-09-03-price-sheet-ocr-jd-comparison-design.md`

## Global Constraints

- 先完整执行 `docs/superpowers/plans/2026-09-03-jd-four-level-region-selection.md`；本计划依赖 `RegionTarget.street` 和 OpenCLI `--street`。
- 首版只支持京东和竖版“标题 + 规格行”手机行情表。
- 精确比较键固定为品牌、机型、容量和颜色；不忽略颜色。
- 原图最大 10 MiB、20,000,000 像素，只在随机临时文件中存在，OCR 后立即删除。
- OCR 条目不能创建或修改正式商品目录记录。
- 每个规格只有 31/31 地区完成且最低到手价严格小于今日价，才进入低价列表。
- 页面已明确显示到手价、券后价或国补领后价时，不重复扣减已包含优惠。
- 不使用会员、PLUS、支付、以旧换新、分期、新人或预约条件价格。
- 生产只允许一个浏览器任务；自动测试不得访问京东或下载 OCR 模型。
- 不修改用户已有的匹配器和演示文件未提交改动。

---

### Task 1: 完成四级代表街道前置计划

**Files:**
- Follow: `docs/superpowers/plans/2026-09-03-jd-four-level-region-selection.md`

**Interfaces:**
- Consumes: 当前三层 `RegionTarget`、地区任务、OpenCLI 插件和前端采集卡片。
- Produces: `RegionTarget.street: str`、持久化的 `CollectionRegionTask.street`，以及要求 `--street` 的两个 OpenCLI 核验命令。

- [ ] **Step 1: 按前置计划逐任务执行 RED → GREEN**

严格执行该计划 Task 1 至 Task 4；每个实现前先运行新增测试并确认因缺少街道能力失败。

- [ ] **Step 2: 运行前置计划完整验证**

Run:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests/automation/test_regions.py tests/automation/test_run_service.py tests/automation/test_executor.py tests/automation/test_opencli_gateway.py tests/api/test_collection_runs.py tests/db/test_region_street_migration.py -v
Set-Location ..
pnpm --dir opencli-plugin-price-compare-jd test
pnpm --dir frontend test
pnpm --dir frontend build
```

Expected: 全部 PASS；31 个地址都有街道，直辖市点击路径去重，前端显示完整地址。

---

### Task 2: OCR 行契约与价目表解析器

**Files:**
- Create: `backend/app/price_sheets/__init__.py`
- Create: `backend/app/price_sheets/contracts.py`
- Create: `backend/app/price_sheets/parser.py`
- Create: `backend/tests/price_sheets/test_parser.py`

**Interfaces:**
- Consumes: `list[OcrLine]`，其中 `OcrLine(text: str, confidence: float, polygon: tuple[tuple[float, float], ...])`。
- Produces: `parse_price_sheet(lines, uploaded_at) -> ParsedPriceSheet`；条目字段为 `brand`、`model_name`、`storage`、`color`、`today_price_cents`、`raw_text`、`confidence`、`review_required`。

- [ ] **Step 1: 写示例文本解析失败测试**

用手工构造的 OCR 行覆盖 `17-256G 黑5900白5900紫5900绿5900`、`17Pro256 白7990橙7890蓝7940`、`17ProMAX1TB` 和 `17Air 256`。断言每个颜色生成独立条目，并得到 `iPhone 17 Pro Max / 1TB / 橙色` 等字面值。

- [ ] **Step 2: 运行解析器测试确认失败**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_parser.py -v`

Expected: FAIL，因为 `app.price_sheets.parser` 尚不存在。

- [ ] **Step 3: 实现最小解析器**

实现坐标排序、规格正则、颜色价格对正则、容量与颜色规范化。价格范围使用字面边界 `100_000 <= cents <= 3_000_000`，置信度取组成条目的最低值，低于 `0.80` 标记复核。

- [ ] **Step 4: 增加日期、坏行和空识别测试**

断言标题 `9.3收货行情` 在 2026 年上传时得到 `2026-09-03`；无日期回退上传日；价格越界、缺颜色或缺规格的行不生成错误条目，原始无法解析行进入 `unparsed_lines`。

- [ ] **Step 5: 运行测试并提交**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_parser.py -v`

Expected: PASS。

Commit: `feat: parse color-specific price sheets`

---

### Task 3: 安全图片输入与 PaddleOCR 适配器

**Files:**
- Create: `backend/app/price_sheets/ocr.py`
- Create: `backend/tests/price_sheets/test_ocr.py`
- Modify: `backend/pyproject.toml`
- Modify: `scripts/bootstrap.ps1`

**Interfaces:**
- Consumes: 原始图片字节和声明的 MIME 类型。
- Produces: `recognize_image(data: bytes, content_type: str, engine: OcrEngine) -> list[OcrLine]`；`PaddleOcrEngine.recognize(path: Path) -> list[OcrLine]`。

- [ ] **Step 1: 写图片边界和临时文件失败测试**

使用 Pillow 在内存创建小 PNG，断言有效图片传给假 OCR 引擎；伪造 MIME、错误魔数、超过 10 MiB 和超过 20,000,000 像素均抛出稳定业务错误；引擎成功和抛错后临时路径都不存在。

- [ ] **Step 2: 运行测试确认失败**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_ocr.py -v`

Expected: FAIL，因为 OCR 模块尚不存在。

- [ ] **Step 3: 实现图片校验和适配器**

只接受 `image/jpeg`、`image/png`、`image/webp`；使用 `PIL.Image.verify()` 和宽高乘积校验；用 `NamedTemporaryFile(delete=False)` 建立随机文件并在 `finally` 删除。Paddle 适配器延迟导入 `PaddleOCR`，调用 `predict(path)`，从结果的 `json['res']` 读取 `rec_texts`、`rec_scores` 和 `rec_polys`，缺依赖时抛出 `OcrUnavailableError`。

- [ ] **Step 4: 添加依赖和安装脚本**

在基础依赖加入 `Pillow==12.3.0`，增加可选组 `ocr = ["paddleocr==3.7.0"]`。`bootstrap.ps1` 先从 Paddle 官方 CPU 索引安装 `paddlepaddle==3.3.0`，再安装 `${backendRoot}[dev,ocr]`，并保持原有错误检查。

- [ ] **Step 5: 运行测试并提交**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_ocr.py backend/tests/price_sheets/test_parser.py -v`

Expected: PASS，测试使用假引擎且不下载模型。

Commit: `feat: add local PaddleOCR input pipeline`

---

### Task 4: 批次持久化、迁移与校对 API

**Files:**
- Create: `backend/app/db/models/price_sheets.py`
- Modify: `backend/app/db/models/__init__.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0008_price_sheet_batches.py`
- Create: `backend/app/schemas/price_sheets.py`
- Create: `backend/app/price_sheets/service.py`
- Create: `backend/app/api/price_sheets.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/db/test_price_sheet_migration.py`
- Create: `backend/tests/price_sheets/test_service.py`
- Create: `backend/tests/api/test_price_sheets.py`

**Interfaces:**
- Consumes: Task 2 的 `ParsedPriceSheet`、Task 3 的 `OcrEngine`。
- Produces: 规格中的 9 个 `/api/price-sheet-batches` 接口，以及 `PriceSheetBatchView`、`PriceSheetItemView`、`PriceSheetResultView`。

- [ ] **Step 1: 写 0008 迁移失败测试**

从 `0007_collection_region_streets` 升级到 `head`，断言创建 `price_sheet_batches`、`price_sheet_items`、`price_sheet_region_tasks`、`price_sheet_region_results`，外键和三组唯一约束存在；降级后四表删除且既有表保留。

- [ ] **Step 2: 写识别、编辑和启动失败测试**

API 测试注入固定 `OcrEngine`：原始图片请求返回 `reviewing` 批次且数据库没有图片列；`PUT items` 可完整替换 reviewing 条目；重复 `(model_name, storage, color)`、空字段和越界价格返回 422；`start` 创建每个已选条目的 31 个含街道任务。

- [ ] **Step 3: 运行测试确认缺表和接口**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/db/test_price_sheet_migration.py backend/tests/price_sheets/test_service.py backend/tests/api/test_price_sheets.py -v
```

Expected: FAIL，因为模型、迁移、服务和接口尚不存在。

- [ ] **Step 4: 实现模型、迁移、服务和 API**

按规格建立四表。候选白名单在 `price_sheet_items.candidates_json` 保存，初始为 `NULL`。`recognize` 使用原始请求体和 `X-File-Name`，限制读取 10 MiB 后交给 OCR；`PUT items` 只允许 `reviewing`；`start` 在事务中验证并创建地区任务，重复调用返回当前批次而不重复建任务。

- [ ] **Step 5: 实现 app 注入边界**

`create_app(..., ocr_engine_factory: Callable[[], OcrEngine] | None = None)` 把工厂保存到 `app.state`；默认工厂创建 `PaddleOcrEngine`。注册新路由，但不在应用启动时初始化模型。

- [ ] **Step 6: 运行测试并提交**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/db/test_price_sheet_migration.py backend/tests/price_sheets/test_service.py backend/tests/api/test_price_sheets.py -v
```

Expected: PASS。

Commit: `feat: persist editable price sheet batches`

---

### Task 5: 精确颜色候选与可信价格计算

**Files:**
- Create: `backend/app/price_sheets/matching.py`
- Create: `backend/app/price_sheets/pricing.py`
- Create: `backend/tests/price_sheets/test_matching.py`
- Create: `backend/tests/price_sheets/test_pricing.py`
- Modify: `backend/app/automation/contracts.py`
- Modify: `backend/app/automation/opencli.py`
- Modify: `backend/tests/automation/test_opencli_gateway.py`

**Interfaces:**
- Consumes: `PriceSheetTarget(brand, model_name, storage, color)`、`DiscoveredCandidate`、`VerifiedOffer`。
- Produces: `select_price_sheet_candidates(..., limit=15)` 和 `calculate_price_sheet_offer(offer) -> PriceSheetCalculatedPrice`。

- [ ] **Step 1: 写精确匹配失败测试**

断言查询词包含颜色；`iPhone 17 Pro` 不接受 `Pro Max` 或 `Air`；`橙色` 不接受蓝色或未明确颜色；容量必须精确；配件、海外版、二手、定金、分期和以旧换新被排除；符合项按初始价与 SKU 稳定排序并最多 15 条。

- [ ] **Step 2: 写价格口径失败测试**

为 `VerifiedOffer` 增加 `sale_price_includes_coupon`、`sale_price_includes_subsidy` 两个默认 `False` 字段。断言普通页面价扣明确券和 confirmed 国补；已含券/国补的销售价不重复扣；estimated 国补不扣；会员/支付折扣存在时仍不扣；结果为负时拒绝。

- [ ] **Step 3: 运行测试确认失败**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_matching.py backend/tests/price_sheets/test_pricing.py backend/tests/automation/test_opencli_gateway.py -v
```

Expected: FAIL，因为精确匹配、价格计算和新契约字段尚不存在。

- [ ] **Step 4: 实现最小匹配与价格计算**

使用明确的型号、容量和中文颜色正则，不调用或修改用户正在编辑的通用 matcher。价格计算先扣商家普通优惠和平台普通券，再按两个 `includes_*` 标记决定是否扣 confirmed 国补，最后加运费；完全忽略会员与支付折扣。

- [ ] **Step 5: 扩展 OpenCLI JSON 契约**

在 `VerifiedOffer` 和 `VerifiedOfferOutput` 末尾加入两个布尔字段，默认 `False`，保持现有夹具兼容。网关继续拒绝额外未知字段和非法类型。

- [ ] **Step 6: 运行测试并提交**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_matching.py backend/tests/price_sheets/test_pricing.py backend/tests/automation/test_opencli_gateway.py -v
```

Expected: PASS。

Commit: `feat: match exact color and calculate trusted prices`

---

### Task 6: 京东卡片价格语义与普通券解析

**Files:**
- Modify: `opencli-plugin-price-compare-jd/lib/jd-page.js`
- Modify: `opencli-plugin-price-compare-jd/verify.js`
- Modify: `opencli-plugin-price-compare-jd/tests/jd-page.test.mjs`

**Interfaces:**
- Consumes: 京东搜索卡片的价格文本、完整卡片文本和销售价。
- Produces: `platform_coupon_cents`、`subsidy_amount_cents`、`subsidy_status`、`sale_price_includes_coupon`、`sale_price_includes_subsidy`。

- [ ] **Step 1: 写价格标签与优惠券失败测试**

构造 DOM 卡片覆盖：`¥5419 国补领后价`、`¥4399 到手价 券满2500减300 券满5000减430`、普通 `¥5999 券满5000减300`、PLUS 专享和以旧换新。断言到手价标记已含券；国补领后价标记已含国补；普通页面价只选择满足门槛的最大普通券；条件优惠不进入字段。

- [ ] **Step 2: 运行 Node 测试确认失败**

Run: `pnpm --dir opencli-plugin-price-compare-jd test`

Expected: FAIL，因为搜索行没有价格语义字段。

- [ ] **Step 3: 实现卡片提取和归一化**

`extractSearchRows` 返回价格附近标签和完整卡片文本；纯函数解析 `到手价/券后价/国补领后价`。只有未标记已含券时才从 `券满X减Y` 中选择 `X <= salePriceYuan` 的最大 `Y`。国补没有明确金额时仅设置已含标记和 `confirmed`，金额为 0。

- [ ] **Step 4: 传递新字段并保持商品页兼容**

`searchCandidatesToVerifiedOffers` 和 `normalizeVerifiedOffer` 返回两个布尔字段。`VERIFIED_COLUMNS` 增加字段；商品详情页按标签决定字段，不能根据差价猜优惠金额。

- [ ] **Step 5: 运行测试并提交**

Run: `pnpm --dir opencli-plugin-price-compare-jd test`

Expected: PASS，且不访问京东网络。

Commit: `feat: preserve JD final-price semantics`

---

### Task 7: 可恢复的价目表批量执行器与结果 API

**Files:**
- Create: `backend/app/price_sheets/executor.py`
- Create: `backend/app/price_sheets/coordinator.py`
- Modify: `backend/app/price_sheets/service.py`
- Modify: `backend/app/api/price_sheets.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/price_sheets/test_executor.py`
- Modify: `backend/tests/api/test_price_sheets.py`

**Interfaces:**
- Consumes: Task 4 的持久批次、Task 5 的匹配与计算、现有 `BrowserGateway`、31 个 `RegionTarget`。
- Produces: `PriceSheetExecutor.execute(batch_id)`、单线程 `PriceSheetCoordinator`、暂停/继续/停止/重试和结果查询。

- [ ] **Step 1: 写执行与恢复失败测试**

用假网关执行两个规格：每个只搜索一次、创建并完成 31 个地区任务、每地区只保存最低可信结果；中断后恢复不重跑 completed；停止保留结果；只重试 failed；登录/验证码/访问频率进入 waiting_user；网络最多重试两次。

- [ ] **Step 2: 写全国结果判定失败测试**

断言 31/31 且最低价低于今日价时返回一条；相等或更高进入 `not_lower`；30/31 返回 `partial` 且不进入低价数组；并列按地区 sequence 与 SKU 稳定选择。

- [ ] **Step 3: 运行测试确认失败**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_executor.py backend/tests/api/test_price_sheets.py -v
```

Expected: FAIL，因为执行器和控制 API 尚未实现。

- [ ] **Step 4: 实现顺序执行器**

复用现有失败分类，按条目和地区顺序执行；候选白名单 JSON 只在首次搜索后写入；`RegionBatchGateway` 可用时每地区只调用一次；每条报价再次验证精确颜色并计算可信到手价；地区完成时 upsert 一条最低结果。

- [ ] **Step 5: 实现控制、恢复和单线程协调器**

控制请求在事务中修改批次/条目/地区状态。应用启动时把遗留 `running` 重新排队并提交 queued 批次。生产延迟复用 8 秒/每 3 地区 60 秒；`PRICE_COMPARE_AUTOMATION_FIXTURE=1` 时两个执行器延迟均为 0。

- [ ] **Step 6: 实现结果 API**

返回 `lower_results`、`not_lower_items`、`partial_items`；`lower_results` 每个条目最多一个，完整包含四级地址、店铺、价格拆分、口径标记、链接、时间和 `31/31`。

- [ ] **Step 7: 运行测试并提交**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/price_sheets/test_executor.py backend/tests/api/test_price_sheets.py backend/tests/automation -v
```

Expected: PASS。

Commit: `feat: run recoverable price sheet comparisons`

---

### Task 8: Vue 四步价目表批量比价界面

**Files:**
- Create: `frontend/src/types/price-sheets.ts`
- Create: `frontend/src/stores/price-sheets.ts`
- Create: `frontend/src/components/PriceSheetComparison.vue`
- Modify: `frontend/src/pages/WorkspacePage.vue`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/tests/price-sheet-comparison.test.ts`
- Create: `frontend/tests/price-sheet-store.test.ts`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: Task 4 和 Task 7 的批次、条目、任务和结果 API。
- Produces: 上传、校对、进度和结果四步界面；刷新后根据本地保存的 `batch_id` 恢复。

- [ ] **Step 1: 写组件与 store 失败测试**

测试 JPG/PNG/WebP 和 10 MiB 客户端校验；上传后显示颜色级可编辑行；低置信度可见；删除、新增和选择有效；启动发送完整条目；轮询显示 `商品 x/y`、`地区 m/31`；控制按钮调用正确 API；结果每规格只显示一条且有完整街道和价格拆分。

- [ ] **Step 2: 运行前端测试确认失败**

Run: `pnpm --dir frontend test -- price-sheet-comparison.test.ts price-sheet-store.test.ts`

Expected: FAIL，因为组件和 store 尚不存在。

- [ ] **Step 3: 实现 API 与 Pinia store**

增加原始二进制 `apiUpload`，设置 `Content-Type` 和经 `encodeURIComponent` 处理的 `X-File-Name`。store 保存 `lastPriceSheetBatchId`，负责识别、校对、启动、轮询、恢复和控制；终态停止轮询。

- [ ] **Step 4: 实现四步组件并接入工作台**

按已批准原型实现。工作台顶部增加“单品比价 / 价目表批量比价”本地页签；原有单品流程默认不变。结果页签固定为“低于今日价”和“未发现更低价/待处理”。

- [ ] **Step 5: 运行前端测试和构建并提交**

Run:

```powershell
pnpm --dir frontend test
pnpm --dir frontend build
```

Expected: 全部 PASS，构建退出码 0。

Commit: `feat: add price sheet comparison workspace`

---

### Task 9: 离线端到端、文档和本机安装验证

**Files:**
- Create: `e2e/tests/price-sheet-comparison.spec.ts`
- Modify: `scripts/test.ps1`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/testing.md`
- Modify: `docs/data-source-policy.md`
- Modify: `docs/platform-adapters.md`

**Interfaces:**
- Consumes: 全部前序任务。
- Produces: 不访问京东和不下载 OCR 模型的完整离线验收，以及用户可执行的安装/使用说明。

- [ ] **Step 1: 写离线 E2E 失败测试**

使用后端注入的固定 OCR 和浏览器夹具，上传一张小 PNG，校对两个颜色规格，启动任务，等待 31/31，断言只显示低于今日价的一条结果且包含颜色与街道；刷新页面后恢复同一批次。

- [ ] **Step 2: 运行 E2E 确认失败**

Run: `pnpm --dir e2e test -- price-sheet-comparison.spec.ts`

Expected: FAIL，因为夹具启动参数或页面流程尚未覆盖批量比价。

- [ ] **Step 3: 完成夹具入口和文档**

让 E2E 环境通过显式变量注入固定 OCR 结果；不在生产默认启用。文档写明 Paddle 首次模型下载、原图不保存、仅京东、精确颜色、31 街道、代理关闭后真实验收和部分结果不等于全国最低。

- [ ] **Step 4: 运行全量验证**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

Expected: 后端、前端、扩展、OpenCLI 插件、构建和离线 E2E 全部 PASS。

- [ ] **Step 5: 安装并验证 OCR 运行时**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
backend\.venv\Scripts\python.exe -c "import paddle, paddleocr; print(paddle.__version__, paddleocr.__version__)"
```

Expected: 输出 PaddlePaddle `3.3.0` 和 PaddleOCR `3.7.0`。模型首次下载若受网络影响，报告为真实环境阻塞，不伪造 OCR 成功。

- [ ] **Step 6: 检查范围并提交**

Run:

```powershell
git status --short
git diff --check
git log --oneline --decorate -12
```

确认用户原有未提交文件未被覆盖；提交仅包含本计划文件。

Commit: `docs: document price sheet comparison`

- [ ] **Step 7: 用户真实验收说明**

用户关闭代理，启动软件，上传价目图片；先选择一个规格验证北京、天津、广东，再运行全部 31 地区。执行者不得代替用户处理验证码或运行真实京东批量采集。
