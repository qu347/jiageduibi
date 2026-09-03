# 京东 31 地区四级地址选择实现计划

> **给 agentic 执行者:** 必须使用 superpowers:executing-plans 或 superpowers:parallel-agents(subagent 驱动)逐任务实现本计划。步骤用 checkbox(`- [ ]`)语法跟踪。

**目标:** 为京东全国自动采集的 31 个固定代表地区补齐街道层级，并阻止未确认街道的页面进入报价读取阶段。

**架构:** 后端地址目录是四级地址的唯一业务来源，每次采集创建任务时把完整地址快照写入数据库。后端通过新增的 `--street` 参数把街道传给 OpenCLI；插件生成去重后的页面点击路径，并在区县和街道均被页面确认后才读取报价。前端显示任务保存的完整地址。

**技术栈:** Python 3.12、FastAPI、SQLAlchemy 2、Alembic、pytest、Vue 3、TypeScript、Vitest、Node.js test runner、OpenCLI UI 插件

**Spec:** `docs/superpowers/specs/2026-09-03-jd-four-level-region-selection-design.md`

## 全局约束

- 地址目录必须恰好包含 31 个中国大陆省级地区，不增加港澳台。
- 每个代表地址必须包含省级、市级、区县级和街道/乡镇级名称。
- 保留现有省、市、区，只为每条地址增加规格中批准的固定街道。
- 指定街道不存在时必须失败，不自动选择第一项或其他备用街道。
- 地址面板仍显示“请选择”，或者当前配送地址未同时确认区县和街道时，不得读取报价。
- 自动化测试不得访问真实京东页面；真实联调由用户关闭代理后执行。
- 不修改用户当前未提交的匹配器、候选测试、演示文件或端到端演示测试。

## 文件结构

- `backend/app/automation/regions.py`：维护 31 条四级代表地址。
- `backend/app/db/models/automation.py`：把街道作为地区任务快照持久化。
- `backend/app/schemas/collection_runs.py`：在地区任务 API 契约中公开街道。
- `backend/app/automation/run_service.py`：创建任务时保存街道。
- `backend/app/automation/executor.py`：执行任务时恢复完整 `RegionTarget`。
- `backend/alembic/versions/0007_collection_region_streets.py`：验证旧数据、回填街道并建立非空约束。
- `backend/app/automation/opencli.py`：向两个核验命令传递 `--street`。
- `opencli-plugin-price-compare-jd/lib/jd-page.js`：提供路径生成和地址确认的纯函数。
- `opencli-plugin-price-compare-jd/verify.js`：完成街道点击、等待和最终确认。
- `frontend/src/types/offers.ts`：同步地区任务的 `street` 类型。
- `frontend/src/components/AutomaticCollectionCard.vue`：显示当前完整四级地址。
- 对应测试文件只验证上述职责，不访问京东线上页面。

---

### 任务 1：保存和恢复 31 个四级代表地址

**文件:**
- 修改: `backend/app/automation/regions.py`
- 修改: `backend/app/db/models/automation.py`
- 修改: `backend/app/schemas/collection_runs.py`
- 修改: `backend/app/automation/run_service.py`
- 修改: `backend/app/automation/executor.py`
- 创建: `backend/alembic/versions/0007_collection_region_streets.py`
- 修改: `backend/tests/automation/test_regions.py`
- 修改: `backend/tests/automation/test_run_service.py`
- 修改: `backend/tests/automation/test_executor.py`
- 修改: `backend/tests/api/test_collection_runs.py`
- 创建: `backend/tests/db/test_region_street_migration.py`

**接口:**
- 消费: 已批准规格中的 31 条固定四级地址。
- 产出: `RegionTarget(region_code, province, city, district, street, sequence)` 和非空的 `CollectionRegionTask.street: str`。

- [ ] **步骤 1：为地址目录、任务快照和 API 写失败测试**

在 `backend/tests/automation/test_regions.py` 中把代表地址断言升级为四级，并要求全部街道非空：

```python
def test_mainland_region_targets_have_31_fixed_streets() -> None:
    assert len(MAINLAND_REGION_TARGETS) == 31
    assert len({item.region_code for item in MAINLAND_REGION_TARGETS}) == 31
    assert all(item.street.strip() for item in MAINLAND_REGION_TARGETS)
    assert get_region_target("110100").street == "奥运村街道"
    assert get_region_target("440100").street == "天河南街道"
    assert get_region_target("650100").street == "解放南路街道"
```

在 `backend/tests/automation/test_run_service.py` 的 31 任务测试中增加：

```python
assert tasks[0].street == "奥运村街道"
assert tasks[-1].street == "解放南路街道"
```

在 `backend/tests/api/test_collection_runs.py` 的任务响应测试中增加：

```python
assert tasks[0]["street"] == "奥运村街道"
assert tasks[-1]["street"] == "解放南路街道"
```

在 `backend/tests/automation/test_executor.py` 的 `BatchGateway` 中保存收到的 `RegionTarget`，并增加：

```python
assert gateway.received_regions[0].street == "奥运村街道"
assert gateway.received_regions[-1].street == "解放南路街道"
```

再增加一个失败地区测试，使北京任务返回 `unsupported_region`，并断言任务与运行的安全错误都包含完整目标地址：

```python
assert get_task(db, run_id, "110100").error_summary.startswith(
    "北京市 / 朝阳区 / 奥运村街道："
)
assert get_run(db, run_id).last_error_summary.startswith(
    "北京市 / 朝阳区 / 奥运村街道："
)
```

- [ ] **步骤 2：运行测试确认缺少街道契约**

运行：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests/automation/test_regions.py tests/automation/test_run_service.py tests/automation/test_executor.py tests/api/test_collection_runs.py -v
```

预期：FAIL，错误分别指出 `RegionTarget`、任务模型或 API 响应没有 `street`。

- [ ] **步骤 3：为数据库迁移写失败测试**

创建 `backend/tests/db/test_region_street_migration.py`。第一个测试先升级到 `0006_automatic_collection_runs`，插入一个北京任务，再升级到 `head`，验证回填值和非空约束：

```python
def test_region_street_migration_backfills_existing_task(alembic_config: Config) -> None:
    command.upgrade(alembic_config, "0006_automatic_collection_runs")
    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    with engine.begin() as connection:
        connection.execute(sa.text("""
            INSERT INTO collection_runs (
                id, search_session_id, platform, status, stage, candidate_source,
                candidate_count, selected_candidate_count, completed_region_count,
                failed_region_count, skipped_region_count, pause_requested,
                stop_requested, updated_at
            ) VALUES (
                1, 1, 'jd', 'queued', 'verifying', 'browser',
                0, 0, 0, 0, 0, 0, 0, '2026-09-03 00:00:00'
            )
        """))
        connection.execute(sa.text("""
            INSERT INTO collection_region_tasks (
                collection_run_id, region_code, province, city, district,
                sequence, status, attempts, verified_candidate_count,
                accepted_offer_count
            ) VALUES (
                1, '110100', '北京市', '北京市', '朝阳区',
                1, 'queued', 0, 0, 0
            )
        """))
    engine.dispose()

    command.upgrade(alembic_config, "head")
    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    columns = {item["name"]: item for item in inspect(engine).get_columns("collection_region_tasks")}
    with engine.connect() as connection:
        street = connection.scalar(sa.text(
            "SELECT street FROM collection_region_tasks WHERE region_code = '110100'"
        ))
    assert columns["street"]["nullable"] is False
    assert street == "奥运村街道"
    engine.dispose()
```

第二个测试插入 `region_code='999999'`，断言升级抛出 `RuntimeError("存在无法回填街道的地区任务: 999999")`，并确认失败后表中还没有 `street` 列。

- [ ] **步骤 4：运行迁移测试确认 0007 尚不存在**

运行：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests/db/test_region_street_migration.py -v
```

预期：FAIL，Alembic `head` 尚未包含街道迁移。

- [ ] **步骤 5：实现四级地址目录**

在 `backend/app/automation/regions.py` 中增加 `street` 字段，并把地址表改成以下精确值：

```python
@dataclass(frozen=True, slots=True)
class RegionTarget:
    region_code: str
    province: str
    city: str
    district: str
    street: str
    sequence: int


_REGION_ROWS = (
    ("110100", "北京市", "北京市", "朝阳区", "奥运村街道"),
    ("120100", "天津市", "天津市", "和平区", "劝业场街道"),
    ("130100", "河北省", "石家庄市", "长安区", "建北街道"),
    ("140100", "山西省", "太原市", "小店区", "坞城街道"),
    ("150100", "内蒙古自治区", "呼和浩特市", "新城区", "中山东路街道"),
    ("210100", "辽宁省", "沈阳市", "沈河区", "五里河街道"),
    ("220100", "吉林省", "长春市", "朝阳区", "红旗街道"),
    ("230100", "黑龙江省", "哈尔滨市", "南岗区", "花园街道"),
    ("310100", "上海市", "上海市", "浦东新区", "陆家嘴街道"),
    ("320100", "江苏省", "南京市", "玄武区", "新街口街道"),
    ("330100", "浙江省", "杭州市", "上城区", "湖滨街道"),
    ("340100", "安徽省", "合肥市", "蜀山区", "三里庵街道"),
    ("350100", "福建省", "福州市", "鼓楼区", "东街街道"),
    ("360100", "江西省", "南昌市", "东湖区", "百花洲街道"),
    ("370100", "山东省", "济南市", "历下区", "泉城路街道"),
    ("410100", "河南省", "郑州市", "金水区", "花园路街道"),
    ("420100", "湖北省", "武汉市", "武昌区", "中南路街道"),
    ("430100", "湖南省", "长沙市", "芙蓉区", "定王台街道"),
    ("440100", "广东省", "广州市", "天河区", "天河南街道"),
    ("450100", "广西壮族自治区", "南宁市", "青秀区", "新竹街道"),
    ("460100", "海南省", "海口市", "龙华区", "金贸街道"),
    ("500100", "重庆市", "重庆市", "渝中区", "解放碑街道"),
    ("510100", "四川省", "成都市", "锦江区", "春熙路街道"),
    ("520100", "贵州省", "贵阳市", "南明区", "中华南路街道"),
    ("530100", "云南省", "昆明市", "五华区", "护国街道"),
    ("540100", "西藏自治区", "拉萨市", "城关区", "八廓街道"),
    ("610100", "陕西省", "西安市", "雁塔区", "小寨路街道"),
    ("620100", "甘肃省", "兰州市", "城关区", "张掖路街道"),
    ("630100", "青海省", "西宁市", "城西区", "西关大街街道"),
    ("640100", "宁夏回族自治区", "银川市", "兴庆区", "解放西街街道"),
    ("650100", "新疆维吾尔自治区", "乌鲁木齐市", "天山区", "解放南路街道"),
)

MAINLAND_REGION_TARGETS = tuple(
    RegionTarget(code, province, city, district, street, sequence)
    for sequence, (code, province, city, district, street) in enumerate(_REGION_ROWS, start=1)
)
```

- [ ] **步骤 6：实现数据库、服务和 API 街道字段**

在 SQLAlchemy 模型和 Pydantic 视图中分别增加非空 `street: str`。`create_run()` 创建任务时使用 `street=target.street`；`CollectionExecutor._execute_region()` 构造 `RegionTarget` 时使用 `street=task.street`。

在执行器中增加 `_task_address(task)`，按省、市、区、街道去除连续重复项并用 ` / ` 连接。`_handle_task_gateway_failure()` 把任务和运行的错误信息统一保存为 `f"{_task_address(task)}：{failure.safe_message}"[:300]`，确保插件的安全错误映射不会丢失失败地址。

创建 revision `0007_collection_region_streets`，`down_revision` 指向 `0006_automatic_collection_runs`。迁移先查询所有不在批准映射中的 `region_code` 并抛出上述 `RuntimeError`；验证通过后增加可空 `street`，使用参数化 `UPDATE` 按 31 个代码回填，再用 `op.batch_alter_table("collection_region_tasks")` 把 `street` 改成 `nullable=False`。降级使用 batch alter 删除该列。

迁移内的映射必须是任务 1 步骤 5 中 31 个 `region_code` 与 `street` 的精确配对，不导入运行时代码，保证历史迁移不可变。

- [ ] **步骤 7：运行任务 1 测试确认通过**

运行：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests/automation/test_regions.py tests/automation/test_run_service.py tests/automation/test_executor.py tests/api/test_collection_runs.py tests/db/test_region_street_migration.py -v
```

预期：全部 PASS。

- [ ] **步骤 8：提交任务 1**

```powershell
git add -- backend/app/automation/regions.py backend/app/db/models/automation.py backend/app/schemas/collection_runs.py backend/app/automation/run_service.py backend/app/automation/executor.py backend/alembic/versions/0007_collection_region_streets.py backend/tests/automation/test_regions.py backend/tests/automation/test_run_service.py backend/tests/automation/test_executor.py backend/tests/api/test_collection_runs.py backend/tests/db/test_region_street_migration.py
git commit -m "feat: persist representative streets"
```

---

### 任务 2：把街道传入 OpenCLI 核验命令

**文件:**
- 修改: `backend/app/automation/opencli.py`
- 修改: `backend/tests/automation/test_opencli_gateway.py`

**接口:**
- 消费: 任务 1 的 `RegionTarget.street: str`。
- 产出: `verify` 和 `verify-region` 命令均包含 `--street <固定街道>`。

- [ ] **步骤 1：写失败测试**

在两个现有命令数组断言的 `--district` 后加入：

```python
"--street",
"奥运村街道",
```

- [ ] **步骤 2：运行测试确认命令缺少街道**

运行：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests/automation/test_opencli_gateway.py::test_verify_passes_region_names_and_parses_offer tests/automation/test_opencli_gateway.py::test_verify_region_uses_one_batch_command_for_candidate_allowlist -v
```

预期：FAIL，实际参数数组没有 `--street`。

- [ ] **步骤 3：写最小实现**

在 `OpenCliGateway.verify()` 和 `OpenCliGateway.verify_region()` 的 `--district` 参数后增加：

```python
"--street",
region.street,
```

- [ ] **步骤 4：运行 OpenCLI 网关测试确认通过**

运行：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests/automation/test_opencli_gateway.py -v
```

预期：全部 PASS。

- [ ] **步骤 5：提交任务 2**

```powershell
git add -- backend/app/automation/opencli.py backend/tests/automation/test_opencli_gateway.py
git commit -m "feat: pass streets to JD verifier"
```

---

### 任务 3：在京东页面选择并确认街道

**文件:**
- 修改: `opencli-plugin-price-compare-jd/lib/jd-page.js`
- 修改: `opencli-plugin-price-compare-jd/verify.js`
- 修改: `opencli-plugin-price-compare-jd/tests/jd-page.test.mjs`

**接口:**
- 消费: `--province`、`--city`、`--district`、`--street` 四个字符串。
- 产出: `regionSelectionPath(province, city, district, street): string[]` 和 `regionSelectionConfirmed(target, state): boolean`。

- [ ] **步骤 1：为路径和最终确认写失败测试**

在 `jd-page.test.mjs` 中增加：

```javascript
test('builds four-level paths and collapses municipality duplicates', () => {
  assert.deepEqual(
    jdPage.regionSelectionPath('广东省', '广州市', '天河区', '天河南街道'),
    ['广东省', '广州市', '天河区', '天河南街道'],
  )
  assert.deepEqual(
    jdPage.regionSelectionPath('北京市', '北京市', '朝阳区', '奥运村街道'),
    ['北京市', '朝阳区', '奥运村街道'],
  )
})

test('requires both district and street with no pending selector', () => {
  const target = { district: '朝阳区', street: '奥运村街道' }
  assert.equal(jdPage.regionSelectionConfirmed(target, {
    selectedArea: '配送至 北京朝阳区奥运村街道',
    pending: false,
  }), true)
  assert.equal(jdPage.regionSelectionConfirmed(target, {
    selectedArea: '配送至 北京朝阳区',
    pending: true,
  }), false)
})
```

- [ ] **步骤 2：运行插件测试确认辅助函数不存在**

运行：

```powershell
node --test opencli-plugin-price-compare-jd/tests/jd-page.test.mjs
```

预期：FAIL，`regionSelectionPath` 或 `regionSelectionConfirmed` 尚未定义。

- [ ] **步骤 3：实现可离线测试的路径和确认函数**

在 `jd-page.js` 中导出两个纯函数。路径函数使用 `regionLabelCandidates(part)` 的最后一个短标签作为相邻去重键，但保留原始值作为点击参数。确认函数接收页面端已经提取好的状态，压缩空白，检查当前配送地址包含区县和街道的任一候选标签，并要求 `pending` 为 `false`。

最小接口形状：

```javascript
export function regionSelectionPath(province, city, district, street) {
  const path = []
  const keys = []
  for (const part of [province, city, district, street]) {
    const key = regionLabelCandidates(part).at(-1)
    if (keys.at(-1) !== key) {
      path.push(part)
      keys.push(key)
    }
  }
  return path
}

export function regionSelectionConfirmed({ district, street }, { selectedArea, pending }) {
  const compact = (value) => String(value || '').replace(/\s+/g, '').trim()
  const normalizedArea = compact(selectedArea)
  const has = (part) => regionLabelCandidates(part).some(
    (label) => normalizedArea.includes(compact(label)),
  )
  return !pending && has(district) && has(street)
}
```

- [ ] **步骤 4：升级插件命令和页面操作**

在 `verify.js` 中：

- 两个命令的 `args` 都增加 `{ name: 'street', required: true, help: 'Street or town display name' }`。
- 两个 `func` 都接收 `street` 并传入 `chooseRegion`。
- `chooseRegion` 签名改为 `chooseRegion(page, province, city, district, street)`。
- 点击循环改用 `regionSelectionPath(province, city, district, street)`。
- `exactTextSelector` 只接受位于可见地址面板 `#area-selector`、`.ui-area-content-wrap` 或 `[class*="jd_area_wrap_"]` 内的候选节点。
- 街道点击后等待 1 秒，再通过一个自包含的 `page.evaluate()` 读取原 `opener` 指向的当前配送地址文本，并检测可见地址面板中是否仍有“请选择”，得到 `{ selectedArea, pending }`。
- 在 Node 侧调用 `regionSelectionConfirmed({ district, street }, state)`；不要把引用模块函数的闭包直接传入浏览器执行上下文。
- 确认失败时抛出 `PAGE_CHANGED: 页面未确认目标区县和街道`；找不到具体层级继续由 `waitForRegionOption` 抛出包含该层级名称的 `UNSUPPORTED_REGION`。

- [ ] **步骤 5：运行插件测试确认通过**

运行：

```powershell
pnpm --dir opencli-plugin-price-compare-jd test
```

预期：全部 PASS，且没有启动 Chrome 或访问京东网络。

- [ ] **步骤 6：提交任务 3**

```powershell
git add -- opencli-plugin-price-compare-jd/lib/jd-page.js opencli-plugin-price-compare-jd/verify.js opencli-plugin-price-compare-jd/tests/jd-page.test.mjs
git commit -m "feat: require JD street selection"
```

---

### 任务 4：在采集卡片显示完整目标地址

**文件:**
- 修改: `frontend/src/types/offers.ts`
- 修改: `frontend/src/components/AutomaticCollectionCard.vue`
- 修改: `frontend/tests/automatic-collection.test.ts`
- 修改: `frontend/tests/workspace-collection-session.test.ts`

**接口:**
- 消费: API 返回的 `CollectionRegionTaskView.street: string`。
- 产出: 当前地区显示为去除连续重复后的“省 / 市 / 区县 / 街道”。

- [ ] **步骤 1：写失败测试并补齐测试夹具**

在所有 `CollectionRegionTaskView` 测试夹具中增加 `street`。把采集卡片当前地区断言改为：

```typescript
expect(wrapper.text()).toContain('当前地区：上海市 / 浦东新区 / 陆家嘴街道')
```

卡片测试任务使用：

```typescript
{
  province: '上海市',
  city: '上海市',
  district: '浦东新区',
  street: '陆家嘴街道',
}
```

- [ ] **步骤 2：运行前端测试确认类型或显示失败**

运行：

```powershell
pnpm --dir frontend test -- automatic-collection.test.ts workspace-collection-session.test.ts
```

预期：FAIL，类型没有 `street` 或页面仍只显示省份。

- [ ] **步骤 3：实现完整地址显示**

在 `CollectionRegionTaskView` 中增加 `street: string`。在 `AutomaticCollectionCard.vue` 中增加一个小型计算函数，按顺序读取省、市、区、街道并消除连续重复值：

```typescript
function taskAddress(task: CollectionRegionTaskView): string {
  return [task.province, task.city, task.district, task.street]
    .filter((part, index, parts) => index === 0 || part !== parts[index - 1])
    .join(' / ')
}

const currentRegion = computed(() => {
  const code = props.run?.current_region_code
  if (!code) return null
  const task = props.tasks.find((item) => item.region_code === code)
  return task ? taskAddress(task) : code
})
```

保持现有卡片布局和其他文案不变。

- [ ] **步骤 4：运行前端测试和构建确认通过**

运行：

```powershell
pnpm --dir frontend test
pnpm --dir frontend build
```

预期：全部 PASS，构建退出码为 0。

- [ ] **步骤 5：提交任务 4**

```powershell
git add -- frontend/src/types/offers.ts frontend/src/components/AutomaticCollectionCard.vue frontend/tests/automatic-collection.test.ts frontend/tests/workspace-collection-session.test.ts
git commit -m "feat: show full collection addresses"
```

---

### 任务 5：离线集成验证和本机插件更新

**文件:**
- 验证: `scripts/test.ps1`
- 验证: `scripts/setup-automation.ps1`
- 验证: `opencli-plugin-price-compare-jd/verify.js`

**接口:**
- 消费: 任务 1 至 4 的数据库、后端、插件和前端改动。
- 产出: 全部离线检查通过，并让本机 OpenCLI 加载新插件代码；不访问真实京东商品页。

- [ ] **步骤 1：运行完整离线测试套件**

运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
```

预期：构建、插件、后端、前端、扩展和离线端到端测试全部通过。

- [ ] **步骤 2：检查提交范围**

运行：

```powershell
git status --short
git diff HEAD~4 --check
git diff HEAD~4 --stat
```

预期：本功能的已提交改动只涉及计划列出的地址、数据库、OpenCLI、插件、前端及测试文件；用户原有未提交改动仍保持未提交且内容不变。

- [ ] **步骤 3：重新安装本地 OpenCLI 插件并验证参数契约**

在不打开京东页面的前提下运行：

```powershell
$pluginRoot = (Resolve-Path '.\opencli-plugin-price-compare-jd').Path
$pluginUri = ([System.Uri]$pluginRoot).AbsoluteUri
opencli plugin install $pluginUri
opencli price-compare-jd --help -f json
```

预期：安装命令成功，帮助输出中的 `verify` 和 `verify-region` 都包含必填 `street` 参数。若 OpenCLI 当前不可用，只记录环境阻塞，不改变已验证的代码结果。

- [ ] **步骤 4：交付用户测试说明**

明确告知用户：关闭代理后使用 `启动比价工具.bat`，先测试北京、天津、广东；确认地址显示到街道后再执行全部 31 地区。不得由执行者运行真实京东自动采集。
