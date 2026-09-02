# 全国自动浏览器采集 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在没有平台 API 密钥的情况下，让用户从现有工作台一次点击启动京东候选搜索和中国大陆 31 个代表地区的可恢复自动核价，并把可信报价写回现有全国比价结果。

**Architecture:** FastAPI 进程内使用单工作线程执行 SQLite 持久任务队列，通过仓库自带的只读 OpenCLI 京东插件复用用户本机 Chrome 登录态。候选发现、地区任务、状态控制和 OpenCLI 进程调用使用窄接口隔离；所有有效报价继续进入现有匹配、补贴、价格、快照和排序链路，Vue 工作台轮询同一运行状态并复用现有结果区。

**Tech Stack:** Python 3.12、FastAPI 0.141.1、SQLAlchemy 2.0.52、Alembic 1.19.1、SQLite、pytest 9.1.1、Vue 3.5.42、Pinia 4.0.3、TypeScript 6.0.2、Vitest 4.1.11、Playwright、Node.js 24、OpenCLI `@jackwener/opencli`、Agent-Reach。

**Spec:** `docs/superpowers/specs/2026-09-02-national-automatic-browser-collection-design.md`

## Global Constraints

- 首个可交付版本只实现京东；淘宝/天猫和拼多多不在本计划中。
- 全国范围固定为中国大陆 31 个省级行政区，不含香港、澳门和台湾。
- 不要求官方 API 密钥；候选来源和最终核验来源均为本机浏览器。
- Agent-Reach 只用于安装检查和环境诊断；业务代码直接调用 OpenCLI。
- OpenCLI 当前内置京东只提供 `opencli jd item <sku>`，所以本项目提供独立的只读 `price-compare-jd` 插件实现搜索与地区核验，不修改或覆盖上游 `jd` 适配器。
- 浏览器任务严格串行；不得并发切换地区。
- 不加入购物车、不结算、不下单、不支付，不修改账号默认地址。
- 不保存密码、Cookie、支付信息、完整地址、页面 HTML 或含个人信息的截图。
- 验证码和登录失效只暂停并等待用户处理，不绕过验证。
- 条件价和估算国补不进入默认排名；页面只能声称“本次已采集范围最低价”。
- 现有手动扩展、固定夹具、搜索会话、报价和历史全部保持兼容。
- 所有实现遵循 TDD；每个任务先观察预期失败，再写最小实现。

## External Interface Evidence

- Agent-Reach 官方安装说明明确其职责是安装、体检和路由，实际调用上游工具：<https://github.com/Panniantong/Agent-Reach/blob/main/docs/install.md>。
- OpenCLI 官方京东适配器当前只公开 `item` 命令：<https://github.com/jackwener/OpenCLI/blob/main/docs/adapters/browser/jd.md>。
- OpenCLI 官方插件说明支持把项目目录通过 `file:///` 安装为长期维护的本地插件：<https://github.com/jackwener/OpenCLI/blob/main/docs/guide/plugins.md>。
- OpenCLI 官方机器接口给出结构化输出和退出码 `0/66/69/75/77/78/130`：<https://github.com/jackwener/OpenCLI/blob/main/llms.txt>。

## File Map

### Backend domain and persistence

- Create `backend/app/automation/regions.py`: 31 个代表地区的唯一静态来源。
- Create `backend/app/automation/contracts.py`: 候选、核验报价、环境状态、网关错误和 Protocol。
- Create `backend/app/automation/opencli.py`: 无 Shell 的 OpenCLI/Agent-Reach 子进程调用和错误归一化。
- Create `backend/app/automation/candidates.py`: 搜索词构造、匹配、去重和候选 Top 15。
- Create `backend/app/automation/run_service.py`: 采集运行与地区任务状态转换。
- Create `backend/app/automation/executor.py`: 单次运行的顺序发现/核验/保存循环。
- Create `backend/app/automation/coordinator.py`: 单工作线程调度、去重提交和关闭。
- Create `backend/app/db/models/automation.py`: 运行、候选和地区任务 ORM 模型。
- Create `backend/app/schemas/collection_runs.py`: API 请求/响应模型。
- Create `backend/app/api/collection_runs.py`: 创建、读取、暂停、继续、停止和失败重试 API。
- Create `backend/alembic/versions/0006_automatic_collection_runs.py`: 只新增自动采集表的迁移。
- Modify `backend/app/db/models/__init__.py`: 导出自动采集模型。
- Modify `backend/alembic/env.py`: 加载自动采集 metadata。
- Modify `backend/app/main.py`: 注册路由、创建协调器并在应用关闭时释放线程。
- Modify `backend/app/services/offer_ingestion.py`: 提取可复用的单条评估/保存入口。
- Create `backend/app/services/offer_retention.py`: 地区核验结束后软删除当前会话中超出 Top 10 的报价，同时保留快照。
- Modify `backend/app/services/search_sessions.py`: 每平台/地区最多返回 10 条可靠报价。

### OpenCLI plugin and setup

- Create `opencli-plugin-price-compare-jd/opencli-plugin.json`: 插件名称和最低 OpenCLI 版本。
- Create `opencli-plugin-price-compare-jd/package.json`: ESM、peer dependency 和 Node 内置测试命令。
- Create `opencli-plugin-price-compare-jd/lib/jd-page.js`: 金额、搜索行、页面状态和核验字段的纯函数。
- Create `opencli-plugin-price-compare-jd/search.js`: `opencli price-compare-jd search` 只读命令。
- Create `opencli-plugin-price-compare-jd/verify.js`: `opencli price-compare-jd verify` 只读地区核验命令。
- Create `opencli-plugin-price-compare-jd/tests/jd-page.test.mjs`: 不访问京东的 DOM/字段测试。
- Create `scripts/setup-automation.ps1`: 显式安装/诊断 Agent-Reach、OpenCLI 和本地插件。

### Frontend and end-to-end

- Create `frontend/src/components/AutomaticCollectionCard.vue`: 自动运行进度和控制面。
- Modify `frontend/src/types/offers.ts`: 自动采集运行/地区任务类型。
- Modify `frontend/src/api/client.ts`: 自动采集 API 方法。
- Modify `frontend/src/stores/comparison.ts`: 运行创建、轮询、恢复和控制动作。
- Modify `frontend/src/pages/WorkspacePage.vue`: 主按钮与运行卡接入。
- Modify `frontend/src/components/OfferTable.vue`: 默认每平台/地区 Top 5、展开 Top 10、来源/时间与可信文案。
- Modify `frontend/src/styles.css`: 只增加自动运行和展开控件样式。
- Create `fixtures/automation/jd-search.json`: 离线候选发现网关结果。
- Create `fixtures/automation/jd-verify.json`: 31 地区核验结果与等待/失败场景。
- Create `e2e/tests/automatic-collection.spec.ts`: 一键、进度、暂停恢复、部分完成和结果验收。
- Modify `README.md`, `docs/architecture.md`, `docs/data-source-policy.md`, `docs/platform-adapters.md`, `docs/testing.md`: 更新真实能力和限制。
- Modify `scripts/test.ps1`: 运行插件的 Node 内置测试。

---

### Task 1: Add the canonical 31-region catalog

**Files:**
- Create: `backend/app/automation/__init__.py`
- Create: `backend/app/automation/regions.py`
- Test: `backend/tests/automation/test_regions.py`

**Interfaces:**
- Produces: `RegionTarget(region_code: str, province: str, city: str, district: str, sequence: int)`。
- Produces: `MAINLAND_REGION_TARGETS: tuple[RegionTarget, ...]` and `get_region_target(region_code: str) -> RegionTarget`。
- Consumed by: run creation, OpenCLI verification and progress display.

- [ ] **Step 1: Write the failing region catalog tests**

```python
from app.automation.regions import MAINLAND_REGION_TARGETS, get_region_target


def test_mainland_region_targets_are_exactly_31_unique_entries() -> None:
    assert len(MAINLAND_REGION_TARGETS) == 31
    assert [item.sequence for item in MAINLAND_REGION_TARGETS] == list(range(1, 32))
    assert len({item.region_code for item in MAINLAND_REGION_TARGETS}) == 31
    assert not {"香港特别行政区", "澳门特别行政区", "台湾省"} & {
        item.province for item in MAINLAND_REGION_TARGETS
    }


def test_region_catalog_uses_approved_representative_districts() -> None:
    beijing = get_region_target("110100")
    guangdong = get_region_target("440100")
    xinjiang = get_region_target("650100")
    assert (beijing.province, beijing.city, beijing.district) == ("北京市", "北京市", "朝阳区")
    assert (guangdong.province, guangdong.city, guangdong.district) == ("广东省", "广州市", "天河区")
    assert (xinjiang.province, xinjiang.city, xinjiang.district) == (
        "新疆维吾尔自治区", "乌鲁木齐市", "天山区"
    )
```

- [ ] **Step 2: Run the focused test and verify the missing-module failure**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/automation/test_regions.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.automation'`.

- [ ] **Step 3: Implement the immutable region catalog**

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegionTarget:
    region_code: str
    province: str
    city: str
    district: str
    sequence: int


_ROWS = (
    ("110100", "北京市", "北京市", "朝阳区"),
    ("120100", "天津市", "天津市", "和平区"),
    ("130100", "河北省", "石家庄市", "长安区"),
    ("140100", "山西省", "太原市", "小店区"),
    ("150100", "内蒙古自治区", "呼和浩特市", "新城区"),
    ("210100", "辽宁省", "沈阳市", "沈河区"),
    ("220100", "吉林省", "长春市", "朝阳区"),
    ("230100", "黑龙江省", "哈尔滨市", "南岗区"),
    ("310100", "上海市", "上海市", "浦东新区"),
    ("320100", "江苏省", "南京市", "玄武区"),
    ("330100", "浙江省", "杭州市", "上城区"),
    ("340100", "安徽省", "合肥市", "蜀山区"),
    ("350100", "福建省", "福州市", "鼓楼区"),
    ("360100", "江西省", "南昌市", "东湖区"),
    ("370100", "山东省", "济南市", "历下区"),
    ("410100", "河南省", "郑州市", "金水区"),
    ("420100", "湖北省", "武汉市", "武昌区"),
    ("430100", "湖南省", "长沙市", "芙蓉区"),
    ("440100", "广东省", "广州市", "天河区"),
    ("450100", "广西壮族自治区", "南宁市", "青秀区"),
    ("460100", "海南省", "海口市", "龙华区"),
    ("500100", "重庆市", "重庆市", "渝中区"),
    ("510100", "四川省", "成都市", "锦江区"),
    ("520100", "贵州省", "贵阳市", "南明区"),
    ("530100", "云南省", "昆明市", "五华区"),
    ("540100", "西藏自治区", "拉萨市", "城关区"),
    ("610100", "陕西省", "西安市", "雁塔区"),
    ("620100", "甘肃省", "兰州市", "城关区"),
    ("630100", "青海省", "西宁市", "城西区"),
    ("640100", "宁夏回族自治区", "银川市", "兴庆区"),
    ("650100", "新疆维吾尔自治区", "乌鲁木齐市", "天山区"),
)

MAINLAND_REGION_TARGETS = tuple(
    RegionTarget(code, province, city, district, index)
    for index, (code, province, city, district) in enumerate(_ROWS, start=1)
)
_BY_CODE = {item.region_code: item for item in MAINLAND_REGION_TARGETS}


def get_region_target(region_code: str) -> RegionTarget:
    return _BY_CODE[region_code]
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/automation/test_regions.py -v`

Expected: 2 tests PASS.

- [ ] **Step 5: Commit the region catalog**

```powershell
git add backend/app/automation backend/tests/automation/test_regions.py
git commit -m "feat(automation): define mainland region targets"
```

### Task 2: Persist collection runs, candidates and region tasks

**Files:**
- Create: `backend/app/db/models/automation.py`
- Create: `backend/alembic/versions/0006_automatic_collection_runs.py`
- Modify: `backend/app/db/models/__init__.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/db/test_automatic_collection_migration.py`

**Interfaces:**
- Produces: ORM classes `CollectionRun`, `CollectionCandidate`, `CollectionRegionTask`.
- Database identities: one run per `(search_session_id, platform)`, one candidate per `(collection_run_id, platform_sku_id)`, one task per `(collection_run_id, region_code)`.
- Consumed by: Tasks 5–8.

- [ ] **Step 1: Write the failing migration test**

```python
@pytest.fixture
def alembic_config(tmp_path: Path) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{(tmp_path / 'automatic.db').as_posix()}")
    return config


from alembic import command
from sqlalchemy import create_engine, inspect


def test_automatic_collection_migration_adds_only_new_tables(alembic_config) -> None:
    command.upgrade(alembic_config, "0005_national_multiregion_sessions")
    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    before = set(inspect(engine).get_table_names())
    engine.dispose()

    command.upgrade(alembic_config, "head")
    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    after = set(inspect(engine).get_table_names())
    assert after - before == {
        "collection_runs", "collection_candidates", "collection_region_tasks"
    }
    assert {"search_sessions", "offers", "price_snapshots"} <= after
    engine.dispose()


def test_automatic_collection_migration_downgrades_without_touching_offers(alembic_config) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "0005_national_multiregion_sessions")
    engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    tables = set(inspect(engine).get_table_names())
    assert "collection_runs" not in tables
    assert {"search_sessions", "offers", "price_snapshots"} <= tables
    engine.dispose()
```

- [ ] **Step 2: Run the migration test and verify revision lookup fails**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/db/test_automatic_collection_migration.py -v`

Expected: FAIL because revision `0006_automatic_collection_runs` and its tables do not exist.

- [ ] **Step 3: Add focused ORM models**

```python
class CollectionRun(Base):
    __tablename__ = "collection_runs"
    __table_args__ = (
        UniqueConstraint("search_session_id", "platform", name="uq_collection_run_session_platform"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    search_session_id: Mapped[int] = mapped_column(ForeignKey("search_sessions.id"), index=True)
    platform: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(32), index=True)
    stage: Mapped[str] = mapped_column(String(32))
    candidate_source: Mapped[str] = mapped_column(String(32), default="browser")
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    selected_candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_region_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_region_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_region_count: Mapped[int] = mapped_column(Integer, default=0)
    current_region_code: Mapped[str | None] = mapped_column(String(12))
    pause_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    stop_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CollectionCandidate(Base):
    __tablename__ = "collection_candidates"
    __table_args__ = (
        UniqueConstraint("collection_run_id", "platform_sku_id", name="uq_collection_candidate_sku"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    collection_run_id: Mapped[int] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    platform_sku_id: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(Text)
    product_url: Mapped[str] = mapped_column(Text)
    platform_shop_id: Mapped[str | None] = mapped_column(String(160))
    shop_name: Mapped[str] = mapped_column(String(200))
    shop_type: Mapped[str] = mapped_column(String(40))
    initial_price_cents: Mapped[int] = mapped_column(Integer)
    match_score: Mapped[int] = mapped_column(Integer)


class CollectionRegionTask(Base):
    __tablename__ = "collection_region_tasks"
    __table_args__ = (
        UniqueConstraint("collection_run_id", "region_code", name="uq_collection_task_region"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    collection_run_id: Mapped[int] = mapped_column(ForeignKey("collection_runs.id"), index=True)
    region_code: Mapped[str] = mapped_column(String(12))
    province: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(80))
    district: Mapped[str] = mapped_column(String(80))
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    verified_candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_offer_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 4: Add migration `0006_automatic_collection_runs` with matching columns and unique constraints**

Use `op.create_table` in dependency order `collection_runs` → `collection_candidates` → `collection_region_tasks`, create indexes for foreign keys and statuses, and downgrade in exact reverse order. Set `down_revision = "0005_national_multiregion_sessions"`; do not alter existing tables.

- [ ] **Step 5: Import the models into Alembic metadata and run upgrade/downgrade tests**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/db/test_automatic_collection_migration.py backend/tests/db/test_multiregion_migration.py -v`

Expected: all migration tests PASS.

- [ ] **Step 6: Commit the persistence layer**

```powershell
git add backend/app/db/models backend/alembic backend/tests/db/test_automatic_collection_migration.py
git commit -m "feat(automation): persist collection runs"
```

### Task 3: Define the OpenCLI gateway and safe subprocess adapter

**Files:**
- Create: `backend/app/automation/contracts.py`
- Create: `backend/app/automation/opencli.py`
- Test: `backend/tests/automation/test_opencli_gateway.py`
- Fixture: `backend/tests/automation/fixtures/opencli-search.json`
- Fixture: `backend/tests/automation/fixtures/opencli-verify.json`

**Interfaces:**
- Produces: `DiscoveredCandidate`, `VerifiedOffer`, `AutomationEnvironment`, `GatewayFailure`.
- Produces: `BrowserGateway` Protocol with `diagnose()`, `discover(query, limit)`, `verify(candidate, region)`.
- Produces: `OpenCliGateway(command_runner: CommandRunner)` and `SubprocessCommandRunner`.
- Consumed by: candidate selection, executor and API environment endpoint.

- [ ] **Step 1: Write failing exit-code, argument and JSON contract tests**

```python
def test_discover_uses_argument_array_and_parses_json() -> None:
    runner = FakeRunner(stdout=SEARCH_JSON, returncode=0)
    gateway = OpenCliGateway(runner)
    items = gateway.discover("Apple iPhone 17 256GB", limit=30)
    assert runner.calls == [[
        "opencli", "price-compare-jd", "search", "Apple iPhone 17 256GB",
        "--limit", "30", "-f", "json",
    ]]
    assert items[0].platform_sku_id == "100000000001"
    assert items[0].initial_price_cents == 519900


@pytest.mark.parametrize(
    ("returncode", "stderr", "code"),
    [
        (66, "", "empty_result"),
        (69, "", "tool_unavailable"),
        (75, "", "network_error"),
        (77, "", "login_required"),
        (78, "", "tool_unavailable"),
        (1, '{"error":{"code":"CAPTCHA","message":"需要验证"}}', "captcha"),
        (1, '{"error":{"code":"PAGE_CHANGED","message":"结构变化"}}', "page_changed"),
    ],
)
def test_gateway_maps_structured_failures(returncode: int, stderr: str, code: str) -> None:
    gateway = OpenCliGateway(FakeRunner(returncode=returncode, stderr=stderr))
    with pytest.raises(GatewayFailure) as failure:
        gateway.discover("iPhone 17", 30)
    assert failure.value.code == code
```

- [ ] **Step 2: Run the focused tests and verify missing contracts fail**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/automation/test_opencli_gateway.py -v`

Expected: FAIL because the gateway classes do not exist.

- [ ] **Step 3: Implement immutable gateway contracts**

```python
@dataclass(frozen=True, slots=True)
class DiscoveredCandidate:
    platform_sku_id: str
    title: str
    product_url: str
    shop_name: str
    platform_shop_id: str | None
    shop_type: str
    initial_price_cents: int


@dataclass(frozen=True, slots=True)
class VerifiedOffer:
    platform_sku_id: str
    title: str
    product_url: str
    shop_name: str
    platform_shop_id: str | None
    shop_type: str
    listed_price_cents: int | None
    sale_price_cents: int
    merchant_discount_cents: int
    platform_coupon_cents: int
    member_discount_cents: int
    payment_discount_cents: int
    subsidy_amount_cents: int
    subsidy_status: str
    shipping_fee_cents: int
    installation_fee_cents: int
    conditional_price_cents: int | None
    stock_status: str
    captured_at: datetime


class GatewayFailure(RuntimeError):
    def __init__(self, code: str, safe_message: str):
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message[:300]
```

- [ ] **Step 4: Implement a no-shell subprocess runner and strict JSON parsing**

```python
completed = subprocess.run(
    args,
    shell=False,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    timeout=timeout_seconds,
    check=False,
)
```

Limit query length to 200 characters, cap stdout/stderr parsing at 1 MiB, require list-shaped JSON output, reject unknown fields through Pydantic, and never include raw stdout/stderr in API-facing failures. `diagnose()` checks `agent-reach doctor --json` when the binary exists, then checks `opencli doctor` and `opencli list -f json` for `price-compare-jd/search` and `price-compare-jd/verify`.

- [ ] **Step 5: Run focused tests and static import smoke**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/automation/test_opencli_gateway.py -v`

Expected: all gateway tests PASS.

- [ ] **Step 6: Commit the gateway**

```powershell
git add backend/app/automation/contracts.py backend/app/automation/opencli.py backend/tests/automation
git commit -m "feat(automation): add safe OpenCLI gateway"
```

### Task 4: Add the read-only JD OpenCLI plugin and setup script

**Files:**
- Create: `opencli-plugin-price-compare-jd/opencli-plugin.json`
- Create: `opencli-plugin-price-compare-jd/package.json`
- Create: `opencli-plugin-price-compare-jd/lib/jd-page.js`
- Create: `opencli-plugin-price-compare-jd/search.js`
- Create: `opencli-plugin-price-compare-jd/verify.js`
- Create: `opencli-plugin-price-compare-jd/tests/jd-page.test.mjs`
- Create: `scripts/setup-automation.ps1`

**Interfaces:**
- Produces CLI: `opencli price-compare-jd search <query> --limit <1..50> -f json`.
- Produces CLI: `opencli price-compare-jd verify <sku> --province <name> --city <name> --district <name> -f json`.
- Both commands are declared `access: 'read'`; no cart/order command exists in this plugin.
- Consumed by: `OpenCliGateway` from Task 3.

- [ ] **Step 1: Write failing pure-function tests for price and search normalization**

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'
import { cents, normalizeSearchRows, pageFailureCode } from '../lib/jd-page.js'

test('converts visible RMB text to integer cents', () => {
  assert.equal(cents('￥5,199.00'), 519900)
  assert.equal(cents('到手价 ¥4,999'), 499900)
})

test('deduplicates search rows by sku and rejects deposit/monthly prices', () => {
  const rows = normalizeSearchRows([
    { sku: '1', title: 'Apple iPhone 17 256GB 全新国行', price: '5199', url: '//item.jd.com/1.html' },
    { sku: '1', title: 'duplicate', price: '5099', url: '//item.jd.com/1.html' },
    { sku: '2', title: 'iPhone 17 定金', price: '100', url: '//item.jd.com/2.html' },
  ], 30)
  assert.deepEqual(rows.map((row) => row.platform_sku_id), ['1'])
  assert.equal(rows[0].initial_price_cents, 519900)
})

test('detects login and captcha pages without returning offers', () => {
  assert.equal(pageFailureCode('京东登录', '请登录京东'), 'AUTH_REQUIRED')
  assert.equal(pageFailureCode('安全验证', '请完成滑块验证码'), 'CAPTCHA')
})
```

- [ ] **Step 2: Run Node tests and verify the missing module failure**

Run: `node --test opencli-plugin-price-compare-jd/tests/*.test.mjs`

Expected: FAIL because `lib/jd-page.js` does not exist.

- [ ] **Step 3: Implement pure normalization helpers**

`cents` accepts only a single visible total price, rejects `月供|定金|预售价|起`, removes comma and currency symbols, and returns integer cents. `normalizeSearchRows` requires SKU, title, URL and positive price, canonicalizes `//item.jd.com/<sku>.html` to HTTPS, deduplicates by SKU and returns at most the requested limit. `pageFailureCode` returns `AUTH_REQUIRED`, `CAPTCHA`, `PAGE_CHANGED` or `null` from title/body markers.

- [ ] **Step 4: Implement the search command with the approved output contract**

```javascript
cli({
  site: 'price-compare-jd',
  name: 'search',
  description: 'Search JD product candidates without account mutations',
  domain: 'search.jd.com',
  strategy: Strategy.UI,
  access: 'read',
  browser: true,
  args: [
    { name: 'query', positional: true, required: true, help: 'Exact product model query' },
    { name: 'limit', type: 'int', default: 30, help: 'Maximum candidates, 1-50' },
  ],
  columns: ['platform_sku_id', 'title', 'product_url', 'shop_name', 'platform_shop_id', 'shop_type', 'initial_price_cents'],
  func: async (page, { query, limit = 30 }) => {
    const max = Math.min(50, Math.max(1, Number(limit)))
    await page.goto(`https://search.jd.com/Search?keyword=${encodeURIComponent(String(query))}`)
    await page.waitForSelector('#J_goodsList .gl-item')
    const rows = await page.evaluate((rowLimit) => Array.from(
      document.querySelectorAll('#J_goodsList .gl-item')
    ).slice(0, rowLimit).map((node) => ({
      sku: node.getAttribute('data-sku') || '',
      title: node.querySelector('.p-name em')?.textContent || '',
      price: node.querySelector('.p-price i')?.textContent || '',
      url: node.querySelector('.p-name a')?.getAttribute('href') || '',
      shop_name: node.querySelector('.p-shop a')?.textContent || '未知店铺',
      platform_shop_id: node.querySelector('.p-shop a')?.getAttribute('data-shopid') || null,
    })), max)
    return normalizeSearchRows(rows, max)
  },
})
```

Before returning rows, read page title and a bounded body marker string and throw `AuthRequiredError`, `CommandExecutionError('CAPTCHA: ...')`, `EmptyResultError` or `CommandExecutionError('PAGE_CHANGED: ...')` so the Python adapter can classify failures.

- [ ] **Step 5: Implement the region verification command**

Navigate to `https://item.jd.com/<sku>.html`, open the first visible selector from `#area-selector`, `.ui-area-text`, `.delivery-address`, `[class*="address"]`, then select exact province/city/district text using a read-only DOM lookup that returns a stable ID/data-attribute/CSS path followed by `page.click`. After each click, refresh the lookup; never mutate DOM through `page.evaluate`. Verify the resulting visible area text contains the requested district before extracting price and stock.

Return exactly these keys:

```javascript
{
  platform_sku_id: String(sku),
  title,
  product_url: `https://item.jd.com/${sku}.html`,
  shop_name,
  platform_shop_id,
  shop_type,
  listed_price_cents,
  sale_price_cents,
  merchant_discount_cents,
  platform_coupon_cents,
  member_discount_cents,
  payment_discount_cents,
  subsidy_amount_cents,
  subsidy_status,
  shipping_fee_cents,
  installation_fee_cents,
  conditional_price_cents,
  stock_status,
  captured_at: new Date().toISOString(),
}
```

Only explicit page values populate discounts and fees. Unknown values are zero or `null`; unconfirmed subsidy is `unknown` with amount zero. If selected area cannot be verified, throw `CommandExecutionError('UNSUPPORTED_REGION: ...')`; out of stock returns `stock_status: 'out_of_stock'` rather than a system error.

- [ ] **Step 6: Add plugin manifests and setup script**

`opencli-plugin.json`:

```json
{
  "name": "price-compare-jd",
  "version": "0.1.0",
  "opencli": ">=1.8.0",
  "description": "Read-only JD candidate search and representative-region verification"
}
```

`package.json` uses `"type": "module"`, peer dependency `"@jackwener/opencli": ">=1.8.0"`, and `"test": "node --test tests/*.test.mjs"`.

`scripts/setup-automation.ps1` checks for `agent-reach`; when absent it prints the exact `pipx install https://github.com/Panniantong/agent-reach/archive/main.zip` command and exits nonzero. With Agent-Reach available it runs:

```powershell
agent-reach install --env=auto --system --channels=opencli
opencli plugin install ("file:///" + ($pluginRoot -replace '\\', '/'))
opencli doctor
opencli list -f json
```

The script must not install the Chrome extension silently; it prints the official extension URL and asks the user to complete that browser-controlled step when `opencli doctor` reports no bridge.

- [ ] **Step 7: Run plugin tests and commit**

Run: `node --test opencli-plugin-price-compare-jd/tests/*.test.mjs`

Expected: all plugin tests PASS.

```powershell
git add opencli-plugin-price-compare-jd scripts/setup-automation.ps1
git commit -m "feat(automation): add read-only JD OpenCLI plugin"
```

### Task 5: Select and persist 10–15 comparable candidates

**Files:**
- Create: `backend/app/automation/candidates.py`
- Test: `backend/tests/automation/test_candidates.py`
- Modify: `backend/app/services/offer_ingestion.py`
- Test: `backend/tests/services/test_browser_offer_ingestion.py`

**Interfaces:**
- Produces: `build_search_query(target: MatchTarget) -> str`.
- Produces: `select_candidates(raw: list[DiscoveredCandidate], target: MatchTarget, limit: int = 15) -> CandidateSelection`.
- Produces: `ingest_verified_browser_offer(db, search_id, raw: RawOffer, adapter_version: str) -> IngestionSummary`.
- Consumed by: executor.

- [ ] **Step 1: Write failing selection tests**

```python
def test_selection_filters_wrong_models_deposits_and_duplicate_skus(target) -> None:
    selection = select_candidates(discovered_candidates(), target, limit=15)
    assert [item.platform_sku_id for item in selection.selected] == ["good-cheap", "good-next"]
    assert selection.exclusions == {"deposit": 1, "model_mismatch": 1, "duplicate_sku": 1}


def test_selection_uses_initial_price_only_for_candidate_cutoff(target) -> None:
    selected = select_candidates(valid_candidates(20), target, limit=15).selected
    assert len(selected) == 15
    assert [item.initial_price_cents for item in selected] == sorted(
        item.initial_price_cents for item in selected
    )
```

- [ ] **Step 2: Run focused tests and verify missing selector failure**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/automation/test_candidates.py -v`

Expected: FAIL because `app.automation.candidates` does not exist.

- [ ] **Step 3: Implement query construction and selection**

Build the query from non-empty brand, model code, model name and storage; normalize whitespace and cap at 200 characters. Convert each discovered row to a `RawOffer(platform="jd", source price, no region)`, call existing `match_offer`, require `match.accepted`, positive initial price and a non-empty SKU, deduplicate by SKU, sort by `(initial_price_cents, platform_sku_id)` and take 15.

- [ ] **Step 4: Extract a single verified-offer ingestion path without changing existing batch behavior**

Refactor the existing per-item body into:

```python
def evaluate_and_save_candidate(
    db: Session,
    search: SearchSession,
    target: MatchTarget,
    rules: list[SubsidyRuleInput],
    payload: PlatformOfferBatch,
    raw: RawOffer,
) -> str | None:
    """Save one accepted/excluded candidate and return its exclusion reason."""
```

`ingest_candidates` continues to call it for every existing API item and records one `AdapterRun` per batch. `ingest_verified_browser_offer` wraps one `RawOffer` in browser metadata, calls the same function, commits immediately, and does not create hundreds of misleading `AdapterRun` rows.

- [ ] **Step 5: Run candidate and existing ingestion regression tests**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/automation/test_candidates.py backend/tests/services/test_browser_offer_ingestion.py backend/tests/api/test_search_flow.py -v`

Expected: all focused and regression tests PASS.

- [ ] **Step 6: Commit candidate selection and ingestion reuse**

```powershell
git add backend/app/automation/candidates.py backend/app/services/offer_ingestion.py backend/tests/automation/test_candidates.py backend/tests/services/test_browser_offer_ingestion.py
git commit -m "feat(automation): select browser candidates"
```

### Task 6: Implement the persistent run state machine

**Files:**
- Create: `backend/app/automation/run_service.py`
- Create: `backend/app/schemas/collection_runs.py`
- Test: `backend/tests/automation/test_run_service.py`

**Interfaces:**
- Produces: `create_run(db, search_session_id, platform="jd") -> CollectionRunView`.
- Produces: `request_pause`, `resume_run`, `request_stop`, `retry_failed_regions`, `recover_interrupted_runs`, `refresh_run_counts`.
- Run statuses: `queued`, `running`, `paused`, `waiting_user`, `completed`, `completed_partial`, `stopped`, `failed`.
- Region statuses: `queued`, `running`, `waiting_user`, `completed`, `failed`, `skipped`.
- Consumed by: executor and API.

- [ ] **Step 1: Write failing creation, transition and recovery tests**

```python
def test_create_run_builds_31_ordered_tasks_for_national_collecting_session(db, search_id) -> None:
    view = create_run(db, search_id, "jd")
    tasks = list_region_tasks(db, view.id)
    assert view.status == "queued"
    assert len(tasks) == 31
    assert [task.sequence for task in tasks] == list(range(1, 32))


def test_create_run_rejects_regional_completed_or_duplicate_sessions(db) -> None:
    with pytest.raises(ValueError, match="全国"):
        create_run(db, regional_session_id, "jd")
    with pytest.raises(ValueError, match="采集中"):
        create_run(db, completed_session_id, "jd")


def test_recovery_requeues_only_interrupted_work(db, running_run) -> None:
    mark_task_completed(db, running_run, "110100")
    mark_task_running(db, running_run, "310100")
    recover_interrupted_runs(db)
    assert get_task(db, running_run, "110100").status == "completed"
    assert get_task(db, running_run, "310100").status == "queued"
    assert get_run(db, running_run).status == "queued"
```

- [ ] **Step 2: Run focused tests and verify state functions are absent**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/automation/test_run_service.py -v`

Expected: FAIL on missing module/functions.

- [ ] **Step 3: Implement creation and idempotent controls**

`create_run` requires an existing `comparison_scope="national"`, `status="collecting"` search session and `platform == "jd"`; it creates one run and the immutable 31-task snapshot in one transaction. Pause only sets `pause_requested=True`. Resume clears pause, converts run `paused|waiting_user` to `queued`, converts task `waiting_user` to `queued`, and clears only transient errors. Stop sets `stop_requested=True`. Retrying failed regions clears errors for failed tasks, sets them to queued, resets stop/pause, and queues the run.

- [ ] **Step 4: Implement counts and restart recovery**

`refresh_run_counts` computes completed/failed/skipped counts from tasks rather than incrementing counters blindly. Recovery changes run `running` to `queued`, task `running` to `queued`, preserves completed/skipped tasks, and leaves `waiting_user`, `paused`, `completed`, `completed_partial`, `stopped`, `failed` unchanged.

- [ ] **Step 5: Run state service and migration tests**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/automation/test_run_service.py backend/tests/db/test_automatic_collection_migration.py -v`

Expected: all tests PASS.

- [ ] **Step 6: Commit the state machine**

```powershell
git add backend/app/automation/run_service.py backend/app/schemas/collection_runs.py backend/tests/automation/test_run_service.py
git commit -m "feat(automation): manage collection run state"
```

### Task 7: Execute discovery and 31-region verification sequentially

**Files:**
- Create: `backend/app/automation/executor.py`
- Test: `backend/tests/automation/test_executor.py`
- Fixture: `fixtures/automation/jd-search.json`
- Fixture: `fixtures/automation/jd-verify.json`

**Interfaces:**
- Produces: `CollectionExecutor(session_factory, gateway_factory, retry_delays=(0.0, 0.0))`.
- Produces: `execute(run_id: int) -> None`.
- Calls `BrowserGateway` serially and `ingest_verified_browser_offer` immediately after each valid verification.
- Consumed by: coordinator.

- [ ] **Step 1: Write failing happy-path and ordering tests**

```python
def test_executor_discovers_once_and_verifies_regions_sequentially(executor, gateway, run_id, db) -> None:
    executor.execute(run_id)
    assert gateway.discover_calls == [("Apple iPhone 17 256GB", 30)]
    assert gateway.max_concurrent_calls == 1
    assert gateway.verify_calls[:2] == [
        ("sku-cheapest", "110100"),
        ("sku-next", "110100"),
    ]
    assert gateway.verify_calls[-1][1] == "650100"
    assert get_run(db, run_id).status == "completed"
    assert get_run(db, run_id).completed_region_count == 31
```

- [ ] **Step 2: Write failing pause, captcha, retry and partial-completion tests**

```python
def test_captcha_pauses_current_task_without_losing_completed_regions(...):
    gateway.fail_once(region="310100", code="captcha")
    executor.execute(run_id)
    assert get_run(db, run_id).status == "waiting_user"
    assert get_task(db, run_id, "110100").status == "completed"
    assert get_task(db, run_id, "310100").status == "waiting_user"


def test_network_error_retries_twice_then_continues_to_next_region(...):
    gateway.always_fail(region="540100", code="network_error")
    executor.execute(run_id)
    assert gateway.attempts_for("540100") == 3
    assert get_task(db, run_id, "540100").status == "failed"
    assert get_task(db, run_id, "610100").status == "completed"
    assert get_run(db, run_id).status == "completed_partial"
```

- [ ] **Step 3: Run executor tests and verify missing executor failure**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/automation/test_executor.py -v`

Expected: FAIL because `CollectionExecutor` does not exist.

- [ ] **Step 4: Implement discovery and candidate persistence**

```python
def execute(self, run_id: int) -> None:
    self._recover_and_mark_running(run_id)
    try:
        candidates = self._load_or_discover_candidates(run_id)
        if not candidates:
            self._fail_run(run_id, "empty_result", "没有找到可比较的候选商品")
            return
        for task_id in self._queued_task_ids(run_id):
            if not self._may_continue(run_id):
                return
            if not self._execute_region(run_id, task_id, candidates):
                return
        self._finish_run(run_id)
    except GatewayFailure as exc:
        self._handle_run_failure(run_id, exc)
```

Discovery runs only when no persisted candidates exist. Store all discovered/selected counts, but persist only the selected 10–15 whitelist rows needed for recovery.

- [ ] **Step 5: Implement per-region verification with safe checkpoints**

For each task, set it running and increment attempts in a short transaction. For each candidate, call the gateway, skip `out_of_stock`, convert `VerifiedOffer` to `RawOffer` with the task's `region_code` and province display name, and pass batch metadata `source_type="browser"` plus the installed plugin version to `ingest_verified_browser_offer` so the quote is committed immediately. Check pause/stop after each candidate. A task with zero in-stock offers completes with `accepted_offer_count=0`; this is not a failure.

Map failures as follows:

```python
WAITING_CODES = {"captcha", "login_required"}
RETRYABLE_CODES = {"network_error"}
TASK_FAILURE_CODES = {"page_changed", "unsupported_region", "invalid_output"}
RUN_FAILURE_CODES = {"tool_unavailable"}
```

Retry `network_error` twice after the first attempt. Do not retry page changes. A user pause finishes the current gateway call, marks the run `paused`, leaves the next work queued, and returns. A stop marks remaining queued tasks `skipped` and the run `stopped` without deleting offers.

- [ ] **Step 6: Run executor, ingestion and search-result tests**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/automation/test_executor.py backend/tests/services/test_browser_offer_ingestion.py backend/tests/api/test_search_flow.py -v`

Expected: all tests PASS.

- [ ] **Step 7: Commit the executor**

```powershell
git add backend/app/automation/executor.py backend/tests/automation/test_executor.py fixtures/automation
git commit -m "feat(automation): execute sequential regional checks"
```

### Task 8: Expose run APIs and wire the single-worker coordinator

**Files:**
- Create: `backend/app/automation/coordinator.py`
- Create: `backend/app/api/collection_runs.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/test_collection_runs.py`
- Test: `backend/tests/automation/test_coordinator.py`

**Interfaces:**
- Produces endpoints:
  - `POST /api/search-sessions/{session_id}/collection-runs`
  - `GET /api/collection-runs/{run_id}`
  - `GET /api/collection-runs/{run_id}/tasks`
  - `POST /api/collection-runs/{run_id}/pause`
  - `POST /api/collection-runs/{run_id}/resume`
  - `POST /api/collection-runs/{run_id}/stop`
  - `POST /api/collection-runs/{run_id}/retry-failed`
  - `GET /api/automation/environment`
- Produces `CollectionCoordinator.submit(run_id) -> bool` with one `ThreadPoolExecutor(max_workers=1)`.
- Consumed by: frontend.

- [ ] **Step 1: Write failing API creation/read/control tests with a fake coordinator**

```python
def test_post_collection_run_creates_31_tasks_and_submits_once(client, national_session_id, coordinator) -> None:
    response = client.post(
        f"/api/search-sessions/{national_session_id}/collection-runs",
        json={"platform": "jd"},
    )
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "queued"
    assert run["total_region_count"] == 31
    assert coordinator.submitted == [run["id"]]


def test_run_controls_are_idempotent(client, run_id) -> None:
    assert client.post(f"/api/collection-runs/{run_id}/pause").status_code == 200
    assert client.post(f"/api/collection-runs/{run_id}/pause").status_code == 200
    assert client.post(f"/api/collection-runs/{run_id}/resume").status_code == 200
    assert client.post(f"/api/collection-runs/{run_id}/resume").status_code == 200
```

- [ ] **Step 2: Run API tests and verify 404/missing router failures**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/api/test_collection_runs.py backend/tests/automation/test_coordinator.py -v`

Expected: FAIL because endpoints and coordinator do not exist.

- [ ] **Step 3: Implement a deduplicating single-worker coordinator**

```python
class CollectionCoordinator:
    def __init__(self, executor: CollectionExecutor):
        self._executor = executor
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="collection")
        self._submitted: set[int] = set()
        self._lock = Lock()

    def submit(self, run_id: int) -> bool:
        with self._lock:
            if run_id in self._submitted:
                return False
            self._submitted.add(run_id)
        self._pool.submit(self._execute_and_release, run_id)
        return True
```

Always remove the ID in `finally`. `close()` calls `shutdown(wait=False, cancel_futures=True)` during app shutdown.

- [ ] **Step 4: Implement router methods with structured safe errors**

All writes use existing `{what_happened, possible_cause, partial_saved, next_action}` error shape. Creation commits before coordinator submission. Resume and retry commit, then submit. Pause and stop only persist the request; they do not kill a subprocess mid-command. `GET /api/automation/environment` returns booleans, versions and a safe next action, never raw command output.

- [ ] **Step 5: Wire coordinator lifecycle into `create_app` with injectable factories**

Extend `create_app` with optional `browser_gateway_factory` and `collection_coordinator_factory` test seams. After session factory creation, call `recover_interrupted_runs` once, create the coordinator and register a FastAPI shutdown handler. Register `collection_runs_router` before the SPA fallback.

- [ ] **Step 6: Run API, health and shutdown tests**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/api/test_collection_runs.py backend/tests/automation/test_coordinator.py backend/tests/api/test_health.py -v`

Expected: all tests PASS with no non-daemon worker left running.

- [ ] **Step 7: Commit the API and coordinator**

```powershell
git add backend/app/automation/coordinator.py backend/app/api/collection_runs.py backend/app/main.py backend/tests/api/test_collection_runs.py backend/tests/automation/test_coordinator.py
git commit -m "feat(api): control automatic collection runs"
```

### Task 9: Add the automatic collection control card and polling store

**Files:**
- Create: `frontend/src/components/AutomaticCollectionCard.vue`
- Modify: `frontend/src/types/offers.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/stores/comparison.ts`
- Modify: `frontend/src/pages/WorkspacePage.vue`
- Modify: `frontend/src/styles.css`
- Test: `frontend/tests/automatic-collection.test.ts`
- Test: `frontend/tests/workspace-collection-session.test.ts`

**Interfaces:**
- Produces frontend types `CollectionRunView`, `CollectionRegionTaskView`, `AutomationEnvironment` matching backend JSON.
- Store actions: `startAutomaticCollection`, `refreshAutomaticCollection`, `pauseAutomaticCollection`, `resumeAutomaticCollection`, `stopAutomaticCollection`, `retryFailedRegions`, `restoreAutomaticCollection`, `startAutomaticPolling`, `stopAutomaticPolling`.
- Poll interval: 1500 ms only while status is `queued|running|waiting_user`.

- [ ] **Step 1: Write failing component/store tests**

```typescript
it('starts a JD nationwide run with one click and shows coverage', async () => {
  const wrapper = mountWorkspaceWithConfirmedVariant(fetchMock)
  await wrapper.get('[data-testid="start-automatic-collection"]').trigger('click')
  await flushPromises()
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/search-sessions/123/collection-runs',
    expect.objectContaining({ method: 'POST' }),
  )
  expect(wrapper.get('[data-testid="automatic-progress"]').text()).toContain('已核验 3/31')
  expect(wrapper.text()).toContain('当前地区：上海市')
})

it('renders login/captcha waiting as a user action instead of failure', () => {
  const wrapper = mount(AutomaticCollectionCard, {
    props: { run: run({ status: 'waiting_user', last_error_code: 'captcha' }), tasks: [] },
  })
  expect(wrapper.text()).toContain('请在浏览器完成验证')
  expect(wrapper.get('[data-testid="resume-automatic-collection"]').exists()).toBe(true)
})
```

- [ ] **Step 2: Run frontend tests and verify missing component/actions fail**

Run: `pnpm --dir frontend test -- automatic-collection.test.ts workspace-collection-session.test.ts`

Expected: FAIL because the component and store actions do not exist.

- [ ] **Step 3: Add API types and client methods**

Use literal unions matching the backend states. Client methods call the exact Task 8 endpoints through existing JSON/error handling. Store `lastAutomaticRunId` in localStorage next to the existing session/variant IDs; never store command output or login data.

- [ ] **Step 4: Implement polling with terminal-state cleanup**

```typescript
const activeRunStatuses = new Set(['queued', 'running', 'waiting_user'])

function startAutomaticPolling(): void {
  stopAutomaticPolling()
  if (!automaticRun.value || !activeRunStatuses.has(automaticRun.value.status)) return
  pollingTimer = window.setInterval(async () => {
    await refreshAutomaticCollection()
    if (!automaticRun.value || !activeRunStatuses.has(automaticRun.value.status)) {
      stopAutomaticPolling()
    }
  }, 1500)
}
```

Treat `paused` as terminal for polling until the user clicks continue. Every refresh also calls the existing search result preview so newly committed offers appear incrementally.

- [ ] **Step 5: Implement the control card and workspace wiring**

The main button creates a national search session when needed, then creates the JD run. The card displays platform, stage, candidate counts, current province, completed/failed/skipped counts, `已核验 N/31`, last safe error and only the actions legal for the current state. Keep the existing manual session card below a clearly labelled “手动采集备用” disclosure; keep fixture demo independent.

- [ ] **Step 6: Run frontend regression tests and build**

Run: `pnpm --dir frontend test`

Expected: all frontend tests PASS.

Run: `pnpm --dir frontend build`

Expected: `vue-tsc` and Vite exit 0.

- [ ] **Step 7: Commit the automatic collection UI**

```powershell
git add frontend/src frontend/tests
git commit -m "feat(ui): control automatic nationwide collection"
```

### Task 10: Enforce Top 10 persistence view and Top 5 default display

**Files:**
- Create: `backend/app/services/offer_retention.py`
- Modify: `backend/app/services/search_sessions.py`
- Test: `backend/tests/services/test_result_limits.py`
- Modify: `backend/app/automation/executor.py`
- Modify: `frontend/src/stores/comparison.ts`
- Modify: `frontend/src/components/OfferTable.vue`
- Modify: `frontend/src/components/OfferDetails.vue`
- Test: `frontend/tests/comparison-results.test.ts`

**Interfaces:**
- Produces backend `retain_region_top_offers(db, search_session_id, platform, region_code, limit=10) -> int` which soft-deletes excess current offers but keeps snapshots.
- Produces backend helper `limit_offers_per_platform_region(offers, limit=10)` preserving global ranked order.
- Produces frontend helper `limitOffersPerPlatformRegion(offers, limit)` preserving backend order.
- UI default limit 5, expanded limit 10.

- [ ] **Step 1: Write failing backend Top 10 test**

```python
def test_result_keeps_ten_per_platform_region_without_changing_global_order() -> None:
    ranked = make_ranked_offers(jd_beijing=12, jd_shanghai=3, taobao_beijing=2)
    limited = limit_offers_per_platform_region(ranked, limit=10)
    assert count_group(limited, "jd", "110100") == 10
    assert count_group(limited, "jd", "310100") == 3
    assert [offer.id for offer in limited] == [
        offer.id for offer in ranked
        if offer.id not in ids_of_two_most_expensive_jd_beijing_offers
    ]


def test_retention_soft_deletes_excess_offers_but_keeps_price_snapshots(db, populated_session) -> None:
    removed = retain_region_top_offers(db, populated_session, "jd", "110100", limit=10)
    assert removed == 2
    assert visible_offer_count(db, populated_session, "jd", "110100") == 10
    assert snapshot_count(db, populated_session, "jd", "110100") == 12
```

- [ ] **Step 2: Write failing frontend Top 5/10 and source display test**

```typescript
it('shows five per platform-region and expands to ten without resorting', async () => {
  const offers = rankedOffersForOneGroup(10)
  const wrapper = mount(OfferTable, { props: { offers } })
  expect(wrapper.findAll('[data-testid="offer-row"]')).toHaveLength(5)
  await wrapper.get('[data-testid="expand-region-offers"]').trigger('click')
  expect(wrapper.findAll('[data-testid="offer-row"]')).toHaveLength(10)
  expect(wrapper.findAll('[data-testid="offer-row"]').map(row => row.attributes('data-offer-id')))
    .toEqual(offers.map(offer => String(offer.id)))
  expect(wrapper.text()).toContain('浏览器核验')
  expect(wrapper.text()).toContain('本次已采集范围最低价')
})
```

- [ ] **Step 3: Run focused tests and verify limits are absent**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/services/test_result_limits.py -v`

Run: `pnpm --dir frontend test -- comparison-results.test.ts`

Expected: both commands FAIL on missing limits/copy.

- [ ] **Step 4: Implement persistent Top 10 retention and stable response limits**

At the end of each completed region task, load its accepted, non-deleted offers with platform/shop data, rank them through the existing `sort_offers`, and set `deleted_at` on items after position 10. Do not delete `PriceSnapshot` or `OfferMatch` rows. The response-level group key is `(platform, region_code or normalized region_name or "unknown")`; iterate already ranked offers once, retain an item while the group's count is below the limit, and never sort inside the helper. Backend `build_search_result` applies the defensive limit 10 after `sort_offers`; frontend applies limit 5 or 10 to the backend order.

- [ ] **Step 5: Add result provenance and captured time**

Map `browser` to “浏览器核验”, `manual` to “手动采集”, and `fixture` to “固定夹具”. Display `captured_at` in local Chinese date/time and keep the raw product link. Change the minimum summary to `本次已采集范围最低价：<region list>`.

- [ ] **Step 6: Run backend/frontend result regressions**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/services/test_result_limits.py backend/tests/api/test_search_flow.py backend/tests/pricing -v`

Run: `pnpm --dir frontend test -- comparison-results.test.ts history.test.ts`

Expected: all tests PASS and conditional-price ordering remains unchanged.

- [ ] **Step 7: Commit result limits and trust labels**

```powershell
git add backend/app/services/offer_retention.py backend/app/services/search_sessions.py backend/app/automation/executor.py backend/tests/services/test_result_limits.py frontend/src frontend/tests/comparison-results.test.ts
git commit -m "feat(results): show verified regional top offers"
```

### Task 11: Complete offline E2E, setup diagnostics and documentation

**Files:**
- Create: `e2e/tests/automatic-collection.spec.ts`
- Modify: `scripts/test.ps1`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/data-source-policy.md`
- Modify: `docs/platform-adapters.md`
- Modify: `docs/testing.md`

**Interfaces:**
- Produces a deterministic fake gateway selected only by test app configuration; production continues to use `OpenCliGateway`.
- Produces one documented setup command: `.\scripts\setup-automation.ps1`.
- Produces one full verification command: `.\scripts\test.ps1`.

- [ ] **Step 1: Write the failing offline E2E scenario**

```typescript
test('runs, pauses, resumes and restores a 31-region automatic JD collection', async ({ page }) => {
  await selectExactVariant(page, '苹果17')
  await page.getByTestId('start-automatic-collection').click()
  await expect(page.getByTestId('automatic-progress')).toContainText('/31')
  await page.getByTestId('pause-automatic-collection').click()
  await expect(page.getByText('已暂停')).toBeVisible()
  await page.getByTestId('resume-automatic-collection').click()
  await expect(page.getByTestId('automatic-progress')).toContainText('已核验 31/31')
  await expect(page.getByTestId('offer-row')).toHaveCount(5)
  await expect(page.getByText('本次已采集范围最低价')).toBeVisible()
  await page.reload()
  await expect(page.getByTestId('automatic-progress')).toContainText('已核验 31/31')
})
```

The E2E server starts with a fixture gateway whose search and verification data come from `fixtures/automation`; it introduces a short controllable delay so pause is observable without relying on a real website.

- [ ] **Step 2: Run the E2E test and verify the fixture gateway/startup gap**

Run: `pnpm --dir e2e test -- automatic-collection.spec.ts`

Expected: FAIL until the test gateway selection and UI flow are wired.

- [ ] **Step 3: Add the offline gateway seam and make the E2E deterministic**

Use an explicit environment value only in the E2E web server command, for example `PRICE_COMPARE_AUTOMATION_FIXTURE=1`. Production ignores fixture files unless that exact value is set. The fixture gateway records no external state and returns the same 31-region results on every run.

- [ ] **Step 4: Add plugin tests to the full PowerShell test gate**

Insert after build and before backend tests:

```powershell
node --test (Join-Path $projectRoot 'opencli-plugin-price-compare-jd\tests\*.test.mjs')
if ($LASTEXITCODE -ne 0) { throw 'OpenCLI plugin tests failed' }
```

Use PowerShell-resolved file enumeration if Node does not expand the Windows wildcard; pass the resulting explicit test file array without invoking another shell.

- [ ] **Step 5: Update operational and policy documentation**

Document:

- setup requires Agent-Reach, OpenCLI, the official Browser Bridge extension and a user-controlled Chrome JD login;
- Agent-Reach installs/diagnoses while the app calls OpenCLI directly;
- the project-owned plugin is read-only and does not replace upstream `jd`;
- automatic collection is user-started, sequential, local and resumable;
- login/CAPTCHA waits for the user;
- no credentials, HTML or personal addresses are stored;
- “nationwide” means the displayed completed coverage, not guaranteed complete marketplace coverage;
- fixture tests are not proof of live JD compatibility;
- crawler fallback remains unimplemented.

- [ ] **Step 6: Run the entire automated suite**

Run: `.\scripts\test.ps1`

Expected: plugin, backend, frontend, extension and E2E suites all exit 0.

- [ ] **Step 7: Run the local automation environment diagnostic**

Run: `backend\.venv\Scripts\python.exe -c "from app.automation.opencli import OpenCliGateway, SubprocessCommandRunner; print(OpenCliGateway(SubprocessCommandRunner()).diagnose())"`

Expected: a structured status. Missing OpenCLI/bridge/plugin is reported as unavailable with a safe next action; it is not reported as a code-test failure.

- [ ] **Step 8: Perform the real three-region JD smoke gate when the user-controlled browser is ready**

Run `.\scripts\setup-automation.ps1`, let the user complete the official extension installation and JD login if prompted, then execute:

```powershell
$smokeItems = opencli price-compare-jd search "Apple iPhone 17 256GB" --limit 3 -f json | ConvertFrom-Json
$smokeSku = $smokeItems[0].platform_sku_id
opencli price-compare-jd verify $smokeSku --province 北京市 --city 北京市 --district 朝阳区 -f json
opencli price-compare-jd verify $smokeSku --province 上海市 --city 上海市 --district 浦东新区 -f json
opencli price-compare-jd verify $smokeSku --province 广东省 --city 广州市 --district 天河区 -f json
```

Verify:

- search returns non-empty candidates with real JD SKU links;
- each displayed district matches the requested region before price extraction;
- no cart/order/account-address mutation occurs;
- prices, stock and source timestamps are visible;
- CAPTCHA pauses and resumes when encountered.

Do not enable the 31-region production button as “live validated” until this smoke gate passes. If it fails because the live page changed, keep offline tests passing, set live status to `not_validated`, record the safe adapter failure and stop; do not claim real nationwide collection works.

- [ ] **Step 9: Commit E2E and documentation**

```powershell
git add e2e scripts/test.ps1 README.md docs fixtures/automation
git commit -m "test: cover automatic nationwide collection"
```

### Task 12: Final verification and delivery report

**Files:**
- Modify only if verification reveals a defect in files created or changed by Tasks 1–11.

**Interfaces:**
- Produces final evidence: branch, full commit SHA, worktree status, test counts, build results, automation environment status and live validation status.

- [ ] **Step 1: Run migration round-trip and focused security assertions**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/tests/db backend/tests/automation backend/tests/api/test_collection_runs.py -v`

Expected: all tests PASS.

Confirm by test/search that production subprocess calls use `shell=False`, query length is bounded, errors are scrubbed, and no new model contains password, cookie, token, street, phone, HTML or screenshot fields.

- [ ] **Step 2: Run the full repository verification from a clean process state**

Run: `.\scripts\test.ps1`

Expected: exit 0 and `All tests passed.`.

- [ ] **Step 3: Inspect the production build manually at desktop and narrow widths**

Run: `.\scripts\build.ps1` then `.\scripts\demo.ps1`.

Check the automatic collection card at desktop and 390 px width, status copy for queued/running/paused/waiting/partial/completed, Top 5/10 expansion, source/time labels, and manual/fixture fallback visibility.

- [ ] **Step 4: Review the complete feature diff and worktree status**

Run:

```powershell
git diff origin/main...HEAD --check
git diff origin/main...HEAD --stat
git status --short --branch
git log --oneline --decorate origin/main..HEAD
```

Expected: no whitespace errors; only intended untracked prototype artifacts may remain outside feature commits and must be listed in the report.

- [ ] **Step 5: Confirm verification did not leave uncommitted tracked changes**

Run: `git status --short`

Expected: no modified or staged tracked files. If a verification defect required a fix, return to the owning task, reproduce it with a failing test, make that focused test pass, and commit those named files before repeating Steps 1–5. Do not create an empty final commit.

- [ ] **Step 6: Deliver the evidence-backed report**

Report the final branch, full HEAD SHA, new commits, exact automated commands and outcomes, live JD status (`validated` or `not_validated`), setup action still required from the user, known platform limitations, and worktree status. Do not push, merge or create a PR unless the user separately requests it.
