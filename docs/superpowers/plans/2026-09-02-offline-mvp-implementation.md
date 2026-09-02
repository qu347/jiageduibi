# Personal Subsidy Price Comparison Offline MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a locally runnable, test-driven vertical slice that searches the iPhone 17 catalog, imports fixed JD/Taobao/PDD offers, excludes mismatches, separates confirmed and estimated subsidies, sorts comparable prices, persists history, and connects a loadable Edge extension skeleton.

**Architecture:** A synchronous FastAPI/SQLAlchemy service owns catalog, matching, pricing, subsidy, persistence, and extension pairing. A Vue single-page workbench consumes the API. A Manifest V3 extension parses only the active supported page and sends normalized candidates to the loopback service. All automated acceptance uses local fixtures; live platform verification is a later plan.

**Tech Stack:** Python 3.12; FastAPI 0.141.1; Uvicorn 0.52.4; Pydantic 2.13.5; SQLAlchemy 2.0.52; Alembic 1.19.1; RapidFuzz 3.14.6; httpx 0.28.1; pytest 9.1.1; Vue 3.5.42; Vite 8.2.2; TypeScript 7.0.2; Pinia 4.0.3; Vue Router 5.3.0; Element Plus 2.14.5; Vitest 4.1.11; Playwright 1.62.1.

**Spec:** `docs/superpowers/specs/2026-09-02-personal-subsidy-price-comparison-design.md`

## Global Constraints

- Run only on Windows and bind the backend to `127.0.0.1`.
- Keep all user data local; never read or store passwords, cookies, identity documents, addresses, orders, or payment data.
- Use integer cents for money and timezone-aware UTC timestamps for persistence.
- Require an exact standard SKU confirmation before accepting offers into a comparison session.
- Keep estimated subsidy out of the default `comparable_price` sort.
- Treat fixed fixtures as automated test data, never as proof of live platform support.
- Do not modify global Python, Node.js, browser, or system environment settings.
- Use Alembic for every schema change; do not rely on runtime `create_all` in the application.
- Work test-first: observe the intended test fail before writing behavior, then run the focused and affected suites.
- Make surgical commits after each task; do not refactor unrelated code.

## Plan Boundary

This plan delivers the approved offline MVP and extension skeleton. Two later plans cover independently reviewable work:

1. Live JD, Taobao/Tmall, and PDD page adaptation and manual acceptance.
2. Full settings management, hardened backup/restore, Windows delivery documentation, and Tauri reassessment.

Do not begin either later plan while executing this one.

## File Map

- `backend/app/main.py`: FastAPI application composition and static frontend mounting.
- `backend/app/core/config.py`: loopback paths, database URL, and application version.
- `backend/app/db/`: SQLAlchemy engine/session, Alembic metadata, seed command, and models.
- `backend/app/schemas/`: API and domain boundary types.
- `backend/app/services/`: catalog, sessions, offer ingestion, history, pairing, and platform status orchestration.
- `backend/app/matching/`: deterministic extraction, exclusion, and scoring.
- `backend/app/pricing/`: comparable-price calculation and sorting.
- `backend/app/subsidy/`: region-aware rule evaluation.
- `backend/app/api/`: thin FastAPI routers.
- `frontend/src/pages/WorkspacePage.vue`: selected single-page workbench.
- `frontend/src/components/`: SKU selector, filters, offer table/details, status and history views.
- `frontend/src/stores/`: catalog and comparison state only; API calls stay in `frontend/src/api/`.
- `extension/src/parsers/`: isolated platform parsers that return one shared candidate shape.
- `extension/src/popup/`: pairing, connection status, and explicit “capture current page” action.
- `fixtures/`: catalog and platform documents used by tests and the local demonstration.
- `scripts/`: repeatable bootstrap, development, test, build, and demo commands.

---

### Task 1: Backend Package and Health Contract

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/api/test_health.py`

**Interfaces:**
- Produces: `app.main:create_app() -> FastAPI`
- Produces: `GET /api/health -> {"status":"ok","version":"0.1.0","database":"pending"}`

- [ ] **Step 1: Add the pinned backend package metadata**

```toml
[project]
name = "personal-subsidy-price-compare"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "fastapi==0.141.1",
  "uvicorn==0.52.4",
  "pydantic==2.13.5",
  "sqlalchemy==2.0.52",
  "alembic==1.19.1",
  "rapidfuzz==3.14.6",
  "httpx==0.28.1",
]

[project.optional-dependencies]
dev = ["pytest==9.1.1", "pytest-cov==7.1.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Create the environment and write the failing health test**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_reports_version_and_pending_database() -> None:
    response = TestClient(create_app()).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "database": "pending",
    }
```

Run:

```powershell
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
backend\.venv\Scripts\python.exe -m pytest backend\tests\api\test_health.py -v
```

Expected: FAIL because `app.main` or `create_app` does not exist.

- [ ] **Step 3: Implement the minimum application factory**

```python
from fastapi import FastAPI


APP_VERSION = "0.1.0"


def create_app() -> FastAPI:
    app = FastAPI(title="个人国补比价工具", version=APP_VERSION)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": APP_VERSION, "database": "pending"}

    return app


app = create_app()
```

- [ ] **Step 4: Run the focused backend test**

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\api\test_health.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the backend baseline**

```powershell
git add backend
git commit -m "feat: add backend health service"
```

### Task 2: Catalog Database and Alembic Baseline

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_catalog.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/db/models/catalog.py`
- Create: `backend/app/db/models/__init__.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/db/test_migrations.py`

**Interfaces:**
- Produces: `app.db.session:build_engine(database_url: str) -> Engine`
- Produces: `app.db.session:session_factory(engine: Engine) -> sessionmaker[Session]`
- Produces SQL tables: `brands`, `product_series`, `product_models`, `product_variants`, `product_aliases`
- Produces model classes: `Brand`, `ProductSeries`, `ProductModel`, `ProductVariant`, `ProductAlias`

- [ ] **Step 1: Write the failing migration test**

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_catalog_migration_upgrades_and_downgrades(tmp_path: Path) -> None:
    database = tmp_path / "catalog.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")

    command.upgrade(config, "head")
    tables = set(inspect(create_engine(f"sqlite:///{database.as_posix()}")).get_table_names())
    assert {"brands", "product_series", "product_models", "product_variants", "product_aliases"} <= tables

    command.downgrade(config, "base")
    assert inspect(create_engine(f"sqlite:///{database.as_posix()}")).get_table_names() == []
```

Run from `backend`: `.\.venv\Scripts\python.exe -m pytest tests\db\test_migrations.py -v`

Expected: FAIL because Alembic configuration and migration do not exist.

- [ ] **Step 2: Define focused catalog models**

```python
class Brand(Base):
    __tablename__ = "brands"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductSeries(Base):
    __tablename__ = "product_series"
    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductModel(Base):
    __tablename__ = "product_models"
    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("product_series.id"), index=True)
    model_name: Mapped[str] = mapped_column(String(160))
    model_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    active: Mapped[bool] = mapped_column(default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductVariant(Base):
    __tablename__ = "product_variants"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("product_models.id"))
    sku_code: Mapped[str] = mapped_column(String(120), unique=True)
    storage: Mapped[str] = mapped_column(String(32))
    memory: Mapped[str | None] = mapped_column(String(32))
    color: Mapped[str] = mapped_column(String(80))
    region_version: Mapped[str] = mapped_column(String(80))
    condition: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductAlias(Base):
    __tablename__ = "product_aliases"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("product_models.id"), index=True)
    alias: Mapped[str] = mapped_column(String(180))
    normalized_alias: Mapped[str] = mapped_column(String(180), index=True)
    active: Mapped[bool] = mapped_column(default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Add unique constraints for `(brand_id, name)`, `(series_id, model_name)`, `(model_id, storage, memory, color, region_version, condition)`, and `(model_id, normalized_alias)`.

- [ ] **Step 3: Implement migration 0001 with matching columns and foreign keys**

The migration `upgrade()` creates the five tables in dependency order and indexes `product_aliases.normalized_alias`, `product_models.model_code`, and `product_variants.sku_code`. Its `downgrade()` drops them in reverse order.

Run: `.\.venv\Scripts\python.exe -m alembic upgrade head`

Expected: a new local database can be upgraded without runtime table creation.

- [ ] **Step 4: Run upgrade, downgrade, and health checks**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\db\test_migrations.py tests\api\test_health.py -v
```

Expected: both tests PASS and health reports `database: ok` after application startup checks the migrated database.

- [ ] **Step 5: Commit the catalog migration**

```powershell
git add backend
git commit -m "feat: add catalog database migration"
```

### Task 3: Catalog Seed, Search, and Import/Export Contract

**Files:**
- Create: `fixtures/catalog/iphone17.json`
- Create: `backend/app/db/seed_catalog.py`
- Create: `backend/app/schemas/catalog.py`
- Create: `backend/app/services/catalog.py`
- Create: `backend/app/api/catalog.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/test_catalog.py`

**Interfaces:**
- Produces: `normalize_keyword(value: str) -> str`
- Produces: `search_catalog(session: Session, query: str) -> list[CatalogModelSummary]`
- Produces: `GET /api/catalog/search?q=苹果17`
- Produces: `POST /api/catalog/import` and `GET /api/catalog/export`

- [ ] **Step 1: Add a fixed catalog fixture and failing API tests**

```json
{
  "brands": [{"name": "Apple"}],
  "series": [{"brand": "Apple", "name": "iPhone 17 系列"}],
  "models": [
    {"series": "iPhone 17 系列", "name": "iPhone 17", "code": "APPLE_IPHONE_17", "aliases": ["苹果17", "iPhone17"]},
    {"series": "iPhone 17 系列", "name": "iPhone 17 Pro", "code": "APPLE_IPHONE_17_PRO", "aliases": ["苹果17pro", "iPhone17Pro"]},
    {"series": "iPhone 17 系列", "name": "iPhone 17 Pro Max", "code": "APPLE_IPHONE_17_PRO_MAX", "aliases": ["苹果17promax", "iPhone17ProMax"]}
  ],
  "variants": [
    {"model_code": "APPLE_IPHONE_17", "sku_code": "APPLE_IPHONE_17_256_CN_NEW_ANY", "storage": "256GB", "color": "不限", "region_version": "中国大陆国行", "condition": "全新"}
  ]
}
```

```python
def test_search_apple_17_returns_standard_models(client: TestClient) -> None:
    response = client.get("/api/catalog/search", params={"q": "苹果17"})
    assert response.status_code == 200
    assert [item["model_code"] for item in response.json()["items"]] == [
        "APPLE_IPHONE_17",
        "APPLE_IPHONE_17_PRO",
        "APPLE_IPHONE_17_PRO_MAX",
    ]


def test_catalog_import_is_atomic_on_invalid_variant(client: TestClient) -> None:
    response = client.post("/api/catalog/import", json={"models": [], "variants": [{"model_code": "MISSING"}]})
    assert response.status_code == 422
    assert response.json()["detail"]["partial_saved"] is False
```

Run: `.\.venv\Scripts\python.exe -m pytest tests\api\test_catalog.py -v`

Expected: FAIL because catalog routes and services do not exist.

- [ ] **Step 2: Implement deterministic catalog normalization and ranking**

```python
def normalize_keyword(value: str) -> str:
    return "".join(value.casefold().split()).replace("苹果", "iphone")


def model_rank(query: str, aliases: list[str]) -> int:
    normalized = normalize_keyword(query)
    scores = [100 if normalize_keyword(alias) == normalized else fuzz.ratio(normalized, normalize_keyword(alias)) for alias in aliases]
    return max(scores, default=0)
```

Return exact alias matches first, then fuzzy candidates by score and model specificity. Search only active, non-deleted records.

- [ ] **Step 3: Implement transactional import and deterministic export**

Validate all references before inserting. On success, upsert by stable brand name, model code, SKU code, and normalized alias. Export arrays sorted by stable code so round-trip tests are deterministic.

- [ ] **Step 4: Run catalog tests and a migration-backed API suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\api\test_catalog.py tests\db\test_migrations.py -v
```

Expected: all tests PASS; “苹果17” returns three model choices and never platform offers.

- [ ] **Step 5: Commit the catalog feature**

```powershell
git add backend fixtures
git commit -m "feat: add searchable product catalog"
```

### Task 4: Deterministic Offer Matching and Exclusion

**Files:**
- Create: `backend/app/schemas/offers.py`
- Create: `backend/app/matching/extractors.py`
- Create: `backend/app/matching/exclusions.py`
- Create: `backend/app/matching/matcher.py`
- Test: `backend/tests/matching/test_matcher.py`

**Interfaces:**
- Consumes: standard SKU fields from `ProductVariant`
- Produces: `match_offer(raw: RawOffer, target: MatchTarget) -> MatchResult`
- Produces: `MatchResult(score: int, accepted: bool, review_required: bool, reasons: list[str], excluded_reason: str | None)`

- [ ] **Step 1: Write parameterized failing exclusion and match tests**

```python
@pytest.mark.parametrize(
    ("title", "reason"),
    [
        ("iPhone 17 手机壳 透明防摔", "accessory"),
        ("iPhone 17 Pro 256GB 国行全新", "model_mismatch"),
        ("iPhone 17 512GB 国行全新", "storage_mismatch"),
        ("二手 iPhone 17 256GB 国行", "condition_mismatch"),
        ("iPhone 17 256GB 每月 199 元", "installment_only"),
        ("以旧换新至高抵扣后 3999 元", "trade_in_only"),
    ],
)
def test_rejects_non_comparable_offer(title: str, reason: str, target: MatchTarget) -> None:
    result = match_offer(RawOffer(title=title, platform="jd", listed_price_cents=None, sale_price_cents=499900), target)
    assert result.accepted is False
    assert result.excluded_reason == reason


def test_accepts_exact_new_mainland_256gb_offer(target: MatchTarget) -> None:
    result = match_offer(RawOffer(title="Apple iPhone 17 256GB 黑色 全新国行", platform="jd", sale_price_cents=519900), target)
    assert result.score >= 95
    assert result.accepted is True
    assert "型号完全匹配" in result.reasons
```

Run: `.\.venv\Scripts\python.exe -m pytest tests\matching\test_matcher.py -v`

Expected: FAIL because matching types and functions do not exist.

- [ ] **Step 2: Implement longest-model-first extraction and explicit exclusions**

```python
MODEL_PATTERNS = (
    ("APPLE_IPHONE_17_PRO_MAX", re.compile(r"iphone\s*17\s*pro\s*max", re.I)),
    ("APPLE_IPHONE_17_PRO", re.compile(r"iphone\s*17\s*pro(?!\s*max)", re.I)),
    ("APPLE_IPHONE_17", re.compile(r"iphone\s*17(?!\s*pro)", re.I)),
)

ACCESSORY_TERMS = ("手机壳", "钢化膜", "充电器", "数据线", "碎屏险", "延保")
NON_NEW_TERMS = ("二手", "翻新", "展示机", "官换机")
```

Use word and unit boundaries for `256GB` and `512GB`. Evaluate exclusions before score calculation.

- [ ] **Step 3: Implement required-field scoring and review thresholds**

```python
WEIGHTS = {"brand": 20, "model": 35, "storage": 20, "region": 15, "condition": 10}


def classify_score(score: int) -> tuple[bool, bool]:
    if score >= 85:
        return True, score < 95
    if score >= 70:
        return False, True
    return False, False
```

Any explicit mismatch in model, storage, region, or condition excludes regardless of fuzzy title score. Append one Chinese reason per matched or missing field.

- [ ] **Step 4: Run matching tests with coverage**

Run: `.\.venv\Scripts\python.exe -m pytest tests\matching\test_matcher.py --cov=app.matching --cov-report=term-missing -v`

Expected: all cases PASS and the report shows each exclusion branch exercised.

- [ ] **Step 5: Commit the matcher**

```powershell
git add backend
git commit -m "feat: add deterministic offer matching"
```

### Task 5: Comparable Price Calculator

**Files:**
- Create: `backend/app/pricing/calculator.py`
- Create: `backend/app/pricing/sorting.py`
- Modify: `backend/app/schemas/offers.py`
- Test: `backend/tests/pricing/test_calculator.py`
- Test: `backend/tests/pricing/test_sorting.py`

**Interfaces:**
- Produces: `calculate_price(offer: OfferPriceInput) -> PriceBreakdown`
- Produces: `sort_offers(offers: Sequence[ComparableOffer]) -> list[ComparableOffer]`
- `PriceBreakdown` fields: `ordinary_price_cents`, `confirmed_final_price_cents`, `estimated_final_price_cents`, `comparable_price_cents`, `conditions`

- [ ] **Step 1: Write failing price-calculation tests**

```python
def test_confirmed_discounts_and_subsidy_enter_comparable_price() -> None:
    result = calculate_price(OfferPriceInput(
        sale_price_cents=600000,
        merchant_discount_cents=20000,
        platform_coupon_cents=10000,
        subsidy_amount_cents=50000,
        subsidy_status="confirmed",
        shipping_fee_cents=0,
        installation_fee_cents=0,
    ))
    assert result.ordinary_price_cents == 570000
    assert result.comparable_price_cents == 520000


def test_estimated_subsidy_never_changes_default_comparable_price() -> None:
    result = calculate_price(OfferPriceInput(
        sale_price_cents=600000,
        subsidy_amount_cents=50000,
        subsidy_status="estimated",
    ))
    assert result.comparable_price_cents == 600000
    assert result.estimated_final_price_cents == 550000
```

Run: `.\.venv\Scripts\python.exe -m pytest tests\pricing -v`

Expected: FAIL because price types and functions do not exist.

- [ ] **Step 2: Implement integer-only price calculation**

```python
def calculate_price(value: OfferPriceInput) -> PriceBreakdown:
    ordinary = value.sale_price_cents - value.merchant_discount_cents - value.platform_coupon_cents
    ordinary += value.shipping_fee_cents + value.installation_fee_cents
    confirmed = ordinary - value.subsidy_amount_cents if value.subsidy_status == "confirmed" else ordinary
    estimated = ordinary - value.subsidy_amount_cents if value.subsidy_status == "estimated" else None
    return PriceBreakdown(
        ordinary_price_cents=ordinary,
        confirmed_final_price_cents=confirmed,
        estimated_final_price_cents=estimated,
        comparable_price_cents=confirmed,
        conditions=value.conditions,
    )
```

Reject negative totals and omit discounts whose applicability is not confirmed.

- [ ] **Step 3: Implement a stable sort key**

```python
SHOP_RANK = {"self_operated": 0, "official_flagship": 1, "authorized": 2, "third_party": 3}


def offer_sort_key(offer: ComparableOffer) -> tuple[int, int, int, int, int]:
    missing = 1 if offer.comparable_price_cents is None else 0
    price = offer.comparable_price_cents if offer.comparable_price_cents is not None else 2**63 - 1
    captured_desc = -int(offer.captured_at.timestamp())
    return (missing, price, SHOP_RANK[offer.shop_type], captured_desc, offer.id)
```

- [ ] **Step 4: Run calculator, sorting, and matcher suites**

Run: `.\.venv\Scripts\python.exe -m pytest tests\pricing tests\matching -v`

Expected: all tests PASS, including identical-price stable ordering.

- [ ] **Step 5: Commit the pricing engine**

```powershell
git add backend
git commit -m "feat: calculate comparable offer prices"
```

### Task 6: Search, Offer, and Snapshot Persistence

**Files:**
- Create: `backend/alembic/versions/0002_offers.py`
- Create: `backend/app/db/models/offers.py`
- Create: `backend/app/schemas/search_sessions.py`
- Create: `backend/app/services/search_sessions.py`
- Test: `backend/tests/db/test_offer_persistence.py`

**Interfaces:**
- Consumes: `ProductVariant.id`, `MatchResult`, and `PriceBreakdown`
- Produces tables: `platforms`, `shops`, `platform_products`, `search_sessions`, `offers`, `price_components`, `price_snapshots`, `offer_matches`, `manual_corrections`, `adapter_runs`
- Produces: `create_search_session(db: Session, command: CreateSearchSession) -> SearchSessionView`
- Produces: `save_evaluated_offer(db: Session, session_id: int, offer: EvaluatedOffer) -> OfferView`

- [ ] **Step 1: Write a failing transaction and deduplication test**

```python
def test_offer_and_snapshot_are_saved_once_per_platform_sku(db_session: Session, seeded_variant: ProductVariant) -> None:
    search = create_search_session(db_session, CreateSearchSession(
        variant_id=seeded_variant.id,
        region_code="110100",
        include_conditional=False,
    ))
    first = save_evaluated_offer(db_session, search.id, evaluated_offer(platform_sku_id="sku-1", price=519900))
    second = save_evaluated_offer(db_session, search.id, evaluated_offer(platform_sku_id="sku-1", price=509900))

    assert second.id == first.id
    assert db_session.scalar(select(func.count(Offer.id))) == 1
    assert db_session.scalar(select(func.count(PriceSnapshot.id))) == 2
```

Run: `.\.venv\Scripts\python.exe -m pytest tests\db\test_offer_persistence.py -v`

Expected: FAIL because offer persistence models and services do not exist.

- [ ] **Step 2: Add migration 0002 and mapped models**

```python
class SearchSession(Base):
    __tablename__ = "search_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"), index=True)
    region_code: Mapped[str | None] = mapped_column(String(12))
    include_conditional: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(24), default="collecting")
    created_at: Mapped[datetime]
    finalized_at: Mapped[datetime | None]


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (UniqueConstraint("search_session_id", "platform_id", "platform_sku_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    search_session_id: Mapped[int] = mapped_column(ForeignKey("search_sessions.id"), index=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"))
    platform_sku_id: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(Text)
    product_url: Mapped[str] = mapped_column(Text)
    comparable_price_cents: Mapped[int | None]
    subsidy_status: Mapped[str] = mapped_column(String(24))
    match_confidence: Mapped[int]
    captured_at: Mapped[datetime]
    deleted_at: Mapped[datetime | None]


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), index=True)
    comparable_price_cents: Mapped[int | None]
    estimated_final_price_cents: Mapped[int | None]
    subsidy_status: Mapped[str] = mapped_column(String(24))
    captured_at: Mapped[datetime]
    source_type: Mapped[str] = mapped_column(String(32))
```

Use these columns for the other migration-0002 tables:

| Table | Required columns |
|---|---|
| `platforms` | `id`, unique `code`, `name`, `enabled` |
| `shops` | `id`, `platform_id`, `platform_shop_id`, `name`, `shop_type`; unique `(platform_id, platform_shop_id)` |
| `platform_products` | `id`, `platform_id`, `shop_id`, `platform_product_id`, `title`, `product_url`, `adapter_version`, `last_seen_at`; unique `(platform_id, platform_product_id)` |
| `offers` additional fields | `platform_product_id`, `shop_id`, `brand`, `model_name`, `model_code`, `storage`, `memory`, `color`, `region_version`, `condition`, `category`, `listed_price_cents`, `sale_price_cents`, `merchant_discount_cents`, `platform_coupon_cents`, `member_discount_cents`, `payment_discount_cents`, `subsidy_amount_cents`, `shipping_fee_cents`, `installation_fee_cents`, `final_price_cents`, `estimated_final_price_cents`, `conditional_price_cents`, `price_type`, `price_conditions_json`, `stock_status`, `excluded_reason`, `region_code`, `source_type`, `adapter_version` |
| `price_components` | `id`, `offer_id`, `component_type`, `amount_cents`, `confirmed`, `condition_code`, `description` |
| `offer_matches` | `id`, `offer_id`, `score`, `accepted`, `review_required`, `reasons_json`, `excluded_reason`, `rule_version`, `created_at` |
| `manual_corrections` | `id`, `offer_id`, `field_name`, `old_value`, `new_value`, `reason`, `created_at` |
| `adapter_runs` | `id`, `platform_id`, `adapter_version`, `source_type`, `status`, `duration_ms`, `success_count`, `excluded_count`, `error_summary`, `started_at`, `finished_at` |

- [ ] **Step 3: Implement upsert plus append-only snapshots in one transaction**

```python
with db.begin_nested():
    offer = find_offer_by_session_platform_sku(db, session_id, value.platform, value.platform_sku_id)
    if offer is None:
        offer = Offer(search_session_id=session_id, platform_id=platform.id, platform_sku_id=value.platform_sku_id)
        db.add(offer)
    apply_current_offer_values(offer, value)
    db.flush()
    db.add(PriceSnapshot.from_evaluated(offer.id, value))
```

Do not catch and suppress `IntegrityError`; convert it to the unified API error at the router boundary.

- [ ] **Step 4: Run migrations and persistence tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pytest tests\db -v
```

Expected: migration upgrade/downgrade and two-snapshot deduplication tests PASS.

- [ ] **Step 5: Commit persistence**

```powershell
git add backend
git commit -m "feat: persist search offers and snapshots"
```

### Task 7: Region-Aware Subsidy Rule Engine

**Files:**
- Create: `backend/alembic/versions/0003_subsidy_settings.py`
- Create: `backend/app/db/models/subsidy.py`
- Create: `backend/app/db/models/settings.py`
- Create: `backend/app/schemas/subsidy.py`
- Create: `backend/app/subsidy/engine.py`
- Create: `backend/app/services/subsidy_rules.py`
- Create: `backend/app/api/subsidy_rules.py`
- Test: `backend/tests/subsidy/test_engine.py`
- Test: `backend/tests/api/test_subsidy_rules.py`

**Interfaces:**
- Produces tables: `subsidy_rules`, `app_settings`, `backups`
- Produces: `evaluate_subsidy(rules: Sequence[SubsidyRuleInput], context: SubsidyContext) -> SubsidyDecision`
- Produces: `GET/POST /api/subsidy-rules`, `PUT /api/subsidy-rules/{rule_id}`

- [ ] **Step 1: Write failing precedence and state tests**

```python
def test_city_rule_beats_province_rule_for_estimate() -> None:
    decision = evaluate_subsidy(
        rules=[province_rule(rate_basis_points=1000), city_rule(rate_basis_points=1500)],
        context=context(region_code="110100", platform="jd", shop_type="self_operated", price_cents=500000),
    )
    assert decision.status == "estimated"
    assert decision.amount_cents == 75000
    assert decision.rule_level == "city"


def test_missing_region_returns_unknown() -> None:
    decision = evaluate_subsidy(rules=[province_rule()], context=context(region_code=None))
    assert decision.status == "unknown"
    assert decision.reason == "需要先选择省市"


def test_platform_confirmation_overrides_estimate_only_for_same_sku() -> None:
    decision = evaluate_subsidy(
        rules=[city_rule()],
        context=context(region_code="110100", platform_confirmed=True, platform_sku_matches=True),
    )
    assert decision.status == "confirmed"
```

Run: `.\.venv\Scripts\python.exe -m pytest tests\subsidy tests\api\test_subsidy_rules.py -v`

Expected: FAIL because rules and engine do not exist.

- [ ] **Step 2: Add the versioned rule schema**

```python
class SubsidyRule(Base):
    __tablename__ = "subsidy_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    region_code: Mapped[str] = mapped_column(String(12), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    valid_from: Mapped[date]
    valid_to: Mapped[date]
    max_unit_price_cents: Mapped[int | None]
    subsidy_rate_basis_points: Mapped[int]
    subsidy_cap_cents: Mapped[int | None]
    participating_platforms_json: Mapped[str]
    participating_shop_types_json: Mapped[str]
    notes: Mapped[str]
    source_url: Mapped[str]
    verified_at: Mapped[datetime | None]
    active: Mapped[bool] = mapped_column(default=True)
    deleted_at: Mapped[datetime | None]
```

Validate `valid_from <= valid_to`, basis points between 0 and 10000, non-negative caps, and a non-empty source URL for active rules.

- [ ] **Step 3: Implement deterministic rule selection and amount calculation**

```python
def subsidy_amount(price_cents: int, rate_basis_points: int, cap_cents: int | None) -> int:
    calculated = price_cents * rate_basis_points // 10_000
    return min(calculated, cap_cents) if cap_cents is not None else calculated


def rule_specificity(rule: SubsidyRuleInput, region_code: str) -> int:
    if rule.region_code == region_code:
        return 2
    if rule.region_code[:2] == region_code[:2] and rule.region_code.endswith("0000"):
        return 1
    return 0
```

Sort eligible rules by specificity, verified flag, and `verified_at` descending. Return `unknown` for unresolved conflicts. Never seed active real-value subsidy data without a verified source.

- [ ] **Step 4: Run subsidy, migration, and pricing tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests\subsidy tests\api\test_subsidy_rules.py tests\pricing tests\db\test_migrations.py -v`

Expected: all tests PASS and estimated amounts remain outside default comparable price.

- [ ] **Step 5: Commit subsidy rules**

```powershell
git add backend
git commit -m "feat: add configurable subsidy rules"
```

### Task 8: Search Session and Fixed-Offer API Flow

**Files:**
- Create: `fixtures/jd/search-results.json`
- Create: `fixtures/taobao/search-results.json`
- Create: `fixtures/pdd/search-results.json`
- Create: `backend/app/services/offer_ingestion.py`
- Create: `backend/app/api/search_sessions.py`
- Create: `backend/app/api/offers.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/test_search_flow.py`

**Interfaces:**
- Consumes: catalog variant, matcher, calculator, subsidy engine, and persistence services
- Produces: `POST /api/search-sessions`
- Produces: `POST /api/search-sessions/{id}/offers`
- Produces: `POST /api/search-sessions/{id}/finalize`
- Produces: `GET /api/search-sessions/{id}` and `GET /api/offers`

- [ ] **Step 1: Create deterministic three-platform fixtures**

Write the records below to the named JSON file. Every URL uses the reserved `example.invalid` domain, so automated tests cannot open a real storefront.

| File | Product/SKU | Title | Shop type | Price fields | Expected result |
|---|---|---|---|---|---|
| `fixtures/jd/search-results.json` | `jd-phone-1` / `jd-sku-256-black` | `Apple iPhone 17 256GB 黑色 全新国行` | `self_operated` | sale `549900`, confirmed subsidy `50000` | accepted, comparable `499900` |
| same | `jd-case-1` / `jd-case-clear` | `iPhone 17 手机壳 透明防摔` | `third_party` | sale `3900` | excluded `accessory` |
| `fixtures/taobao/search-results.json` | `tb-phone-1` / `tb-sku-256-white` | `Apple iPhone 17 256GB 白色 全新国行` | `official_flagship` | sale `504900`, subsidy unknown | accepted, comparable `504900` |
| same | `tb-pro-1` / `tb-pro-256` | `Apple iPhone 17 Pro 256GB 全新国行` | `official_flagship` | sale `489900` | excluded `model_mismatch` |
| same | `tb-used-1` / `tb-used-256` | `二手 iPhone 17 256GB 国行` | `third_party` | sale `409900` | excluded `condition_mismatch` |
| `fixtures/pdd/search-results.json` | `pdd-phone-1` / `pdd-sku-256-blue` | `iPhone 17 256GB 蓝色 全新国行` | `authorized` | sale `509900`; eligible test rule estimate `30000` | accepted, comparable `509900`, estimated `479900` |
| same | `pdd-512-1` / `pdd-sku-512` | `iPhone 17 512GB 全新国行` | `authorized` | sale `489900` | excluded `storage_mismatch` |
| same | `pdd-monthly-1` / `pdd-monthly` | `iPhone 17 256GB 每月 199 元` | `third_party` | price type `installment`, monthly `19900`, no total | excluded `installment_only` |
| same | `pdd-trade-1` / `pdd-trade` | `iPhone 17 256GB 以旧换新后 3999 元` | `third_party` | price type `trade_in`, advertised `399900` | excluded `trade_in_only` |

The API test fixture inserts a Beijing/PDD rule with `source_url=https://example.invalid/rules/beijing-pdd`, rate `1000` basis points, cap `30000`, and `verified_at=None`. It exists only in the test database and therefore yields `estimated`, never `confirmed`.

- [ ] **Step 2: Write the failing full-flow API test**

```python
def test_fixed_offers_produce_three_sorted_comparable_results(client: TestClient, variant_id: int) -> None:
    session_id = client.post("/api/search-sessions", json={
        "variant_id": variant_id,
        "region_code": "110100",
        "include_conditional": False,
    }).json()["id"]

    for fixture in ("jd", "taobao", "pdd"):
        payload = json.loads(Path(f"../fixtures/{fixture}/search-results.json").read_text(encoding="utf-8"))
        response = client.post(f"/api/search-sessions/{session_id}/offers", json=payload)
        assert response.status_code == 200

    result = client.post(f"/api/search-sessions/{session_id}/finalize").json()
    assert [offer["platform"] for offer in result["offers"]] == ["jd", "taobao", "pdd"]
    assert [offer["comparable_price_cents"] for offer in result["offers"]] == [499900, 504900, 509900]
    assert result["offers"][2]["estimated_final_price_cents"] == 479900
    assert result["excluded_count"] == 6
```

Run: `.\.venv\Scripts\python.exe -m pytest tests\api\test_search_flow.py -v`

Expected: FAIL because the API orchestration is missing.

- [ ] **Step 3: Implement thin routers and one ingestion transaction per platform payload**

```python
def ingest_candidates(db: Session, search_id: int, payload: PlatformOfferBatch) -> IngestionSummary:
    search = require_collecting_session(db, search_id)
    target = load_match_target(db, search.variant_id)
    summary = IngestionSummary(platform=payload.platform)
    for raw in payload.items:
        match = match_offer(raw, target)
        if not match.accepted:
            summary.add_excluded(raw, match)
            continue
        subsidy = evaluate_subsidy(load_rules(db, search.region_code), subsidy_context(raw, search))
        priced = calculate_price(price_input(raw, subsidy))
        save_evaluated_offer(db, search_id, evaluated(raw, match, subsidy, priced))
        summary.accepted_count += 1
    db.commit()
    return summary
```

Return the unified error structure with `what_happened`, `possible_cause`, `partial_saved`, and `next_action` for invalid sessions or payloads.

- [ ] **Step 4: Run all backend domain and API tests**

Run: `.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing -v`

Expected: all backend tests PASS; the fixed flow returns exactly three accepted offers and at least five exclusions.

- [ ] **Step 5: Commit the offline search flow**

```powershell
git add backend fixtures
git commit -m "feat: add fixture-based comparison flow"
```

### Task 9: Price History and Platform Status API

**Files:**
- Create: `backend/app/schemas/history.py`
- Create: `backend/app/services/history.py`
- Create: `backend/app/services/platform_status.py`
- Create: `backend/app/api/history.py`
- Create: `backend/app/api/platforms.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/test_history.py`
- Test: `backend/tests/api/test_platform_status.py`

**Interfaces:**
- Produces: `GET /api/price-history?variant_id=&platform=&from=&to=`
- Produces: `GET /api/platforms/status`
- History point: `{offer_id, platform, comparable_price_cents, subsidy_status, captured_at, source_type}`

- [ ] **Step 1: Write failing history and status tests**

```python
def test_history_returns_snapshots_in_time_order(client: TestClient, completed_search: int, variant_id: int) -> None:
    response = client.get("/api/price-history", params={"variant_id": variant_id})
    assert response.status_code == 200
    points = response.json()["points"]
    assert len(points) >= 3
    assert [point["captured_at"] for point in points] == sorted(point["captured_at"] for point in points)


def test_platform_status_distinguishes_fixture_from_live_validation(client: TestClient) -> None:
    response = client.get("/api/platforms/status")
    assert response.json()["items"] == [
        {"platform": "jd", "fixture_status": "passing", "live_status": "not_validated"},
        {"platform": "taobao", "fixture_status": "passing", "live_status": "not_validated"},
        {"platform": "pdd", "fixture_status": "passing", "live_status": "not_validated"},
    ]
```

Run: `.\.venv\Scripts\python.exe -m pytest tests\api\test_history.py tests\api\test_platform_status.py -v`

Expected: FAIL because history and platform status routes do not exist.

- [ ] **Step 2: Implement filtered snapshot queries**

```python
query = (
    select(PriceSnapshot, Offer, Platform)
    .join(Offer, PriceSnapshot.offer_id == Offer.id)
    .join(SearchSession, Offer.search_session_id == SearchSession.id)
    .join(Platform, Offer.platform_id == Platform.id)
    .where(SearchSession.variant_id == variant_id)
    .order_by(PriceSnapshot.captured_at, PriceSnapshot.id)
)
```

Add optional platform and inclusive UTC date filters. Never infer missing historical points.

- [ ] **Step 3: Derive explicit fixture and live status**

Fixture status comes from the latest automated adapter run record. Live status remains `not_validated` until the later live-adapter plan writes a manual acceptance record.

- [ ] **Step 4: Run history, status, and full backend tests**

Run: `.\.venv\Scripts\python.exe -m pytest -v`

Expected: all backend tests PASS.

- [ ] **Step 5: Commit history and status APIs**

```powershell
git add backend
git commit -m "feat: expose price history and platform status"
```

### Task 10: Vue Workbench Shell and Standard SKU Selection

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/pnpm-lock.yaml`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/types/catalog.ts`
- Create: `frontend/src/stores/catalog.ts`
- Create: `frontend/src/components/ModelSelector.vue`
- Create: `frontend/src/components/FilterPanel.vue`
- Create: `frontend/src/pages/WorkspacePage.vue`
- Create: `frontend/src/pages/HistoryPage.vue`
- Create: `frontend/src/pages/SettingsPage.vue`
- Create: `frontend/tests/setup.ts`
- Test: `frontend/tests/workspace-model-selection.test.ts`

**Interfaces:**
- Consumes: `GET /api/catalog/search` and standard variant fields
- Produces: `useCatalogStore().search(query)` and `useCatalogStore().confirmVariant(variant)`
- Produces: one-page workbench that cannot create a search before a variant is confirmed

- [ ] **Step 1: Add the exact frontend dependency manifest**

```json
{
  "name": "personal-subsidy-price-compare-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "vue-tsc --noEmit && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "element-plus": "2.14.5",
    "pinia": "4.0.3",
    "vue": "3.5.42",
    "vue-router": "5.3.0"
  },
  "devDependencies": {
    "@types/node": "26.4.1",
    "@vitejs/plugin-vue": "6.0.8",
    "@vue/compiler-sfc": "3.5.42",
    "@vue/test-utils": "2.5.0",
    "jsdom": "30.0.1",
    "typescript": "7.0.2",
    "vite": "8.2.2",
    "vitest": "4.1.11",
    "vue-tsc": "3.3.11"
  }
}
```

Run: `cd frontend; pnpm install --frozen-lockfile=false`

Expected: pnpm creates the lock file without changing global Node.js.

- [ ] **Step 2: Write the failing model-selection test**

```typescript
it('requires a standard variant before search creation', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ items: [
      { model_code: 'APPLE_IPHONE_17', model_name: 'iPhone 17', variants: [
        { id: 1, sku_code: 'APPLE_IPHONE_17_256_CN_NEW_ANY', storage: '256GB', color: '不限', region_version: '中国大陆国行', condition: '全新' }
      ] },
      { model_code: 'APPLE_IPHONE_17_PRO', model_name: 'iPhone 17 Pro', variants: [] },
      { model_code: 'APPLE_IPHONE_17_PRO_MAX', model_name: 'iPhone 17 Pro Max', variants: [] }
    ] }),
  }))

  const wrapper = mount(WorkspacePage, { global: { plugins: [createPinia()] } })
  await wrapper.get('[data-test="keyword"]').setValue('苹果17')
  await wrapper.get('[data-test="search-models"]').trigger('click')
  expect(wrapper.text()).toContain('iPhone 17 Pro Max')
  expect(wrapper.get('[data-test="create-search"]').attributes('disabled')).toBeDefined()
})
```

Run: `pnpm test -- workspace-model-selection.test.ts`

Expected: FAIL because workbench components and store do not exist.

- [ ] **Step 3: Implement the shell, API client, catalog store, and selected B layout**

```typescript
export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw await ApiError.fromResponse(response)
  return response.json() as Promise<T>
}

export const useCatalogStore = defineStore('catalog', {
  state: () => ({ models: [] as CatalogModel[], confirmedVariant: null as ProductVariant | null }),
  actions: {
    async search(query: string) {
      this.models = (await apiGet<CatalogSearchResponse>(`/api/catalog/search?q=${encodeURIComponent(query)}`)).items
      this.confirmedVariant = null
    },
    confirmVariant(variant: ProductVariant) {
      this.confirmedVariant = variant
    },
  },
})
```

Use a top search/region row, left filter panel, and right result area. Keep the result action disabled until `confirmedVariant` is set.

- [ ] **Step 4: Run frontend tests and type/build checks**

Run:

```powershell
pnpm test
pnpm build
```

Expected: model selection test PASS and production build completes.

- [ ] **Step 5: Commit the frontend workbench shell**

```powershell
git add frontend
git commit -m "feat: add sku-first comparison workbench"
```

### Task 11: Comparison Results, Error States, and History View

**Files:**
- Create: `frontend/src/types/offers.ts`
- Create: `frontend/src/stores/comparison.ts`
- Create: `frontend/src/components/OfferTable.vue`
- Create: `frontend/src/components/OfferDetails.vue`
- Create: `frontend/src/components/ErrorNotice.vue`
- Create: `frontend/src/components/PriceTrend.vue`
- Modify: `frontend/src/pages/WorkspacePage.vue`
- Modify: `frontend/src/pages/HistoryPage.vue`
- Test: `frontend/tests/comparison-results.test.ts`
- Test: `frontend/tests/error-states.test.ts`
- Test: `frontend/tests/history.test.ts`

**Interfaces:**
- Consumes: search-session, offers, and history APIs from Tasks 8–9
- Produces: `useComparisonStore().createAndFinalizeSearch()`
- Produces visible labels: `已确认国补`, `预计国补`, `不符合`, `无法确认`

- [ ] **Step 1: Write failing result-label and conditional-price tests**

```typescript
it('renders confirmed and estimated subsidies as different states', async () => {
  const wrapper = mount(OfferTable, { props: { offers: [
    offer({ id: 1, subsidy_status: 'confirmed', comparable_price_cents: 499900 }),
    offer({ id: 2, subsidy_status: 'estimated', comparable_price_cents: 509900, estimated_final_price_cents: 459900 }),
  ] } })
  expect(wrapper.text()).toContain('已确认国补')
  expect(wrapper.text()).toContain('预计国补')
  expect(wrapper.text()).toContain('¥5,099.00')
  expect(wrapper.text()).toContain('估算 ¥4,599.00')
})


it('does not mix conditional price into ordinary ranking by default', () => {
  const visible = selectVisibleOffers([
    offer({ id: 1, comparable_price_cents: 510000 }),
    offer({ id: 2, comparable_price_cents: 520000, conditional_price_cents: 480000 }),
  ], { includeConditional: false })
  expect(visible.map(item => item.id)).toEqual([1, 2])
})
```

Run: `pnpm test -- comparison-results.test.ts error-states.test.ts history.test.ts`

Expected: FAIL because result, error, and history components do not exist.

- [ ] **Step 2: Implement one comparison store that preserves backend order**

```typescript
export const useComparisonStore = defineStore('comparison', {
  state: () => ({ offers: [] as OfferView[], excludedCount: 0, loading: false, error: null as ApiErrorBody | null }),
  actions: {
    async createAndFinalizeSearch(command: CreateSearchCommand, fixtureBatches: PlatformOfferBatch[]) {
      this.loading = true
      this.error = null
      try {
        const session = await apiPost<SearchSessionView>('/api/search-sessions', command)
        for (const batch of fixtureBatches) await apiPost(`/api/search-sessions/${session.id}/offers`, batch)
        const result = await apiPost<ComparisonResult>(`/api/search-sessions/${session.id}/finalize`, {})
        this.offers = result.offers
        this.excludedCount = result.excluded_count
      } catch (error) {
        this.error = normalizeApiError(error)
      } finally {
        this.loading = false
      }
    },
  },
})
```

Do not re-sort default results in the browser. Only the explicit conditional-price view derives an alternate order and keeps its label visible.

- [ ] **Step 3: Implement accessible offer details, errors, and an SVG trend**

`OfferDetails.vue` shows price components and match reasons in a semantic description list. `ErrorNotice.vue` renders the four required fields. `PriceTrend.vue` accepts sorted history points and maps integer cents to an SVG polyline with labeled first, latest, and minimum values; an empty array renders “暂无历史价格”。

```typescript
const subsidyLabels: Record<SubsidyStatus, string> = {
  confirmed: '已确认国补',
  estimated: '预计国补',
  not_eligible: '不符合',
  unknown: '无法确认',
}
```

- [ ] **Step 4: Run frontend tests and production build**

Run: `pnpm test; pnpm build`

Expected: all frontend tests PASS, the build type-checks, and no result implies that estimated subsidy is confirmed.

- [ ] **Step 5: Commit comparison and history UI**

```powershell
git add frontend
git commit -m "feat: render comparable offers and history"
```

### Task 12: Local Extension Pairing Contract

**Files:**
- Create: `backend/app/services/extension_pairing.py`
- Create: `backend/app/api/extension.py`
- Modify: `backend/app/main.py`
- Create: `extension/package.json`
- Create: `extension/pnpm-lock.yaml`
- Create: `extension/tsconfig.json`
- Create: `extension/vite.config.ts`
- Create: `extension/public/manifest.json`
- Create: `extension/src/shared/types.ts`
- Create: `extension/src/shared/api.ts`
- Create: `extension/src/background/index.ts`
- Create: `extension/src/popup/index.html`
- Create: `extension/src/popup/main.ts`
- Test: `backend/tests/api/test_extension_pairing.py`
- Test: `extension/tests/pairing.test.ts`

**Interfaces:**
- Produces: `POST /api/extension/pair` and authenticated `POST /api/extension/offers`
- Produces extension storage keys: `backendUrl`, `extensionToken`
- Pairing shell requires `activeTab`, `storage`, and loopback host permission; Task 13 adds `scripting` for the explicit user-triggered capture action

- [ ] **Step 1: Write failing pairing and authorization tests**

Create the extension dependency manifest before running its first test:

```json
{
  "name": "personal-subsidy-price-compare-extension",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "build": "tsc --noEmit && vite build",
    "test": "vitest run"
  },
  "devDependencies": {
    "@types/chrome": "0.2.8",
    "@types/node": "26.4.1",
    "jsdom": "30.0.1",
    "typescript": "7.0.2",
    "vite": "8.2.2",
    "vitest": "4.1.11"
  }
}
```

```python
def test_pairing_exchanges_one_time_code_for_token(client: TestClient, pairing_code: str) -> None:
    response = client.post("/api/extension/pair", json={"code": pairing_code})
    assert response.status_code == 200
    assert len(response.json()["token"]) >= 32
    assert client.post("/api/extension/pair", json={"code": pairing_code}).status_code == 409


def test_offer_submission_requires_extension_token(client: TestClient) -> None:
    response = client.post("/api/extension/offers", json={"search_session_id": 1, "platform": "jd", "items": []})
    assert response.status_code == 401
```

```typescript
it('stores only the returned local token after pairing', async () => {
  const storage = createMemoryStorage()
  await pairExtension('123456', storage, fakeApi({ token: 'local-token-value' }))
  expect(await storage.get('extensionToken')).toBe('local-token-value')
  expect(await storage.get('pairingCode')).toBeUndefined()
})
```

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\api\test_extension_pairing.py -v
pnpm --dir extension install --frozen-lockfile=false
pnpm --dir extension test -- pairing.test.ts
```

Expected: FAIL because pairing services and extension package do not exist.

- [ ] **Step 2: Implement one-time code exchange with hashed token storage**

```python
def issue_extension_token(settings: SettingsRepository, code: str) -> str:
    record = settings.require_unused_pairing_code(hash_secret(code))
    token = secrets.token_urlsafe(32)
    settings.consume_pairing_code(record.id)
    settings.set("extension_token_hash", hash_secret(token))
    return token
```

Use `hmac.compare_digest` for token verification. Never log the code or token. Expose the current pairing code only on the local settings page endpoint.

- [ ] **Step 3: Create the minimal MV3 popup and background message path**

```json
{
  "manifest_version": 3,
  "name": "个人国补比价助手",
  "version": "0.1.0",
  "permissions": ["activeTab", "storage"],
  "host_permissions": ["http://127.0.0.1/*"],
  "background": {"service_worker": "background.js", "type": "module"},
  "action": {"default_popup": "popup/index.html"}
}
```

The popup has visible backend status, pairing-code input, and disabled capture action until paired. It does not request cookies or browsing history.

- [ ] **Step 4: Run pairing tests and build the extension**

Run:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\api\test_extension_pairing.py -v
Set-Location extension
pnpm install --frozen-lockfile=false
pnpm test
pnpm build
```

Expected: tests PASS and `extension/dist/manifest.json` is loadable as an unpacked Edge extension.

- [ ] **Step 5: Commit pairing and extension shell**

```powershell
git add backend extension
git commit -m "feat: pair local browser extension"
```

### Task 13: Fixture Parsers and Explicit Current-Page Capture

**Files:**
- Create: `fixtures/jd/search-page.html`
- Create: `fixtures/jd/search-page-missing-price.html`
- Create: `fixtures/taobao/search-page.html`
- Create: `fixtures/pdd/search-page.html`
- Create: `extension/src/parsers/base.ts`
- Create: `extension/src/parsers/jd.ts`
- Create: `extension/src/parsers/taobao.ts`
- Create: `extension/src/parsers/pdd.ts`
- Create: `extension/src/parsers/index.ts`
- Create: `extension/src/content/capture.ts`
- Modify: `extension/src/background/index.ts`
- Modify: `extension/src/popup/main.ts`
- Test: `extension/tests/url-routing.test.ts`
- Test: `extension/tests/parsers.test.ts`
- Test: `extension/tests/privacy-boundary.test.ts`

**Interfaces:**
- Produces: `PlatformParser.canHandle(url: URL) -> boolean`
- Produces: `PlatformParser.parse(document: Document, url: URL) -> ParseResult`
- `ParseResult` is `{status: 'ok', items: RawOfferCandidate[]} | {status: 'login_required' | 'captcha' | 'unsupported' | 'missing_price', message: string}`

- [ ] **Step 1: Write failing parser and privacy tests**

```typescript
it.each([
  ['https://search.jd.com/Search?keyword=iphone17', 'jd'],
  ['https://s.taobao.com/search?q=iphone17', 'taobao'],
  ['https://mobile.yangkeduo.com/search_result.html?search_key=iphone17', 'pdd'],
])('routes %s to %s', (value, platform) => {
  expect(selectParser(new URL(value))?.platform).toBe(platform)
})

it('never reads password inputs or cookies', () => {
  document.body.innerHTML = '<input type="password" value="secret"><div data-title="iPhone 17 256GB"></div>'
  const cookieSpy = vi.spyOn(document, 'cookie', 'get')
  captureCurrentDocument(document, new URL('https://search.jd.com/Search?keyword=iphone17'))
  expect(cookieSpy).not.toHaveBeenCalled()
})

it('returns missing_price instead of guessing', () => {
  const document = fixtureDocument('jd/search-page-missing-price.html')
  expect(jdParser.parse(document, new URL('https://search.jd.com/Search')).status).toBe('missing_price')
})
```

Run: `pnpm test -- url-routing.test.ts parsers.test.ts privacy-boundary.test.ts`

Expected: FAIL because parser selection and capture code do not exist.

- [ ] **Step 2: Implement isolated parsers against only the supplied fixtures**

Use these exact fixture contracts so parser tests do not depend on live markup:

```html
<!-- fixtures/jd/search-page.html -->
<ul id="J_goodsList"><li class="gl-item" data-sku="jd-sku-256-black" data-product-id="jd-phone-1"><div class="p-name"><em>Apple iPhone 17 256GB 黑色 全新国行</em></div><div class="p-price"><i>¥5,499.00</i></div><div class="p-shop">京东自营演示店</div><a class="p-link" href="https://example.invalid/jd/phone-1">商品</a></li></ul>
```

```html
<!-- fixtures/taobao/search-page.html -->
<div id="mainsrp-itemlist"><div class="item" data-nid="tb-phone-1" data-sku="tb-sku-256-white"><a class="pic-link" href="https://example.invalid/taobao/phone-1">Apple iPhone 17 256GB 白色 全新国行</a><div class="price">¥5,049.00</div><div class="shop">Apple 官方旗舰演示店</div></div></div>
```

```html
<!-- fixtures/pdd/search-page.html -->
<main><article data-testid="goods-card" data-goods-id="pdd-phone-1" data-sku-id="pdd-sku-256-blue"><a href="https://example.invalid/pdd/phone-1"><h2>iPhone 17 256GB 蓝色 全新国行</h2></a><span data-testid="price">¥5,099.00</span><span data-testid="shop">拼多多授权演示店</span></article></main>
```

`fixtures/jd/search-page-missing-price.html` repeats the JD item without `.p-price`. Parser selectors are confined to their platform module and return `missing_price` for that fixture.

```typescript
export interface PlatformParser {
  readonly platform: 'jd' | 'taobao' | 'pdd'
  canHandle(url: URL): boolean
  parse(document: Document, url: URL): ParseResult
}

export function parseCents(text: string): number | null {
  const match = text.replace(/,/g, '').match(/(?:¥|￥)\s*(\d+(?:\.\d{1,2})?)/)
  if (!match) return null
  const [yuan, fraction = ''] = match[1].split('.')
  return Number(yuan) * 100 + Number(fraction.padEnd(2, '0'))
}
```

Each parser owns its selectors and adapter version. Return structured failures for login, captcha, unsupported pages, and missing total prices.

- [ ] **Step 3: Add explicit active-tab injection and authenticated submission**

On popup click, the background worker injects `capture.ts` into the active tab, receives `ParseResult`, and submits only `RawOfferCandidate` fields plus the active search-session ID. It never runs on a timer or traverses tabs.

```typescript
const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
if (!tab.id || !tab.url) return { status: 'unsupported', message: '当前标签页无法采集' }
const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: capturePage })
return result as ParseResult
```

Add `scripting` only when this implementation step uses `chrome.scripting`; keep platform domains out of persistent host permissions and rely on `activeTab` user activation.

- [ ] **Step 4: Run extension tests and inspect the built manifest**

Run:

```powershell
pnpm test
pnpm build
Get-Content -LiteralPath dist\manifest.json -Raw
```

Expected: tests PASS; the manifest contains no `cookies`, `history`, or wildcard host permission.

- [ ] **Step 5: Commit fixture parsers**

```powershell
git add extension fixtures
git commit -m "feat: parse explicitly captured fixture pages"
```

### Task 14: Unified Scripts, Offline End-to-End Acceptance, and Handoff Docs

**Files:**
- Create: `scripts/bootstrap.ps1`
- Create: `scripts/dev.ps1`
- Create: `scripts/test.ps1`
- Create: `scripts/build.ps1`
- Create: `scripts/demo.ps1`
- Create: `e2e/package.json`
- Create: `e2e/pnpm-lock.yaml`
- Create: `e2e/playwright.config.ts`
- Create: `e2e/tests/offline-comparison.spec.ts`
- Create: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/data-source-policy.md`
- Create: `docs/platform-adapters.md`
- Create: `docs/subsidy-rules.md`
- Create: `docs/testing.md`
- Modify: `backend/app/main.py`
- Test: all backend, frontend, extension, and E2E suites

**Interfaces:**
- Produces: `scripts\bootstrap.ps1`, `scripts\dev.ps1`, `scripts\test.ps1`, `scripts\build.ps1`, `scripts\demo.ps1`
- Produces: production backend serving `frontend/dist`
- Produces: one offline acceptance command with no live platform dependency

- [ ] **Step 1: Write the failing Playwright acceptance**

Create the E2E package and production-server contract:

```json
{
  "name": "personal-subsidy-price-compare-e2e",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {"test": "playwright test"},
  "devDependencies": {"@playwright/test": "1.62.1", "typescript": "7.0.2"}
}
```

```typescript
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  use: { baseURL: 'http://127.0.0.1:8765', channel: 'msedge' },
  webServer: {
    command: 'powershell -NoProfile -ExecutionPolicy Bypass -File ..\\scripts\\demo.ps1 -NoOpen',
    url: 'http://127.0.0.1:8765/api/health',
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
```

```typescript
test('compares one exact iPhone 17 SKU across three fixture platforms', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('keyword').fill('苹果17')
  await page.getByTestId('search-models').click()
  await page.getByText('iPhone 17', { exact: true }).click()
  await page.getByText('256GB', { exact: true }).click()
  await page.getByText('中国大陆国行', { exact: true }).click()
  await page.getByText('全新', { exact: true }).click()
  await page.getByTestId('confirm-variant').click()
  await page.getByTestId('run-fixture-comparison').click()

  await expect(page.getByTestId('offer-row')).toHaveCount(3)
  await expect(page.getByText(/已排除 [5-9]\d* 条干扰项/)).toBeVisible()
  await expect(page.getByText('预计国补').first()).toBeVisible()
  const prices = await page.getByTestId('comparable-price').allTextContents()
  expect(prices).toEqual([...prices].sort((left, right) => Number(left.replace(/\D/g, '')) - Number(right.replace(/\D/g, ''))))

  await page.reload()
  await page.getByRole('link', { name: '历史价格' }).click()
  await expect(page.getByText('历史最低价')).toBeVisible()
})
```

Run:

```powershell
pnpm --dir e2e install --frozen-lockfile=false
pnpm --dir e2e test
```

Expected: FAIL until production static serving, scripts, and the demo fixture action are wired.

- [ ] **Step 2: Implement idempotent PowerShell commands**

`bootstrap.ps1` creates only project-local environments, installs locked dependencies, runs Alembic, and seeds the catalog. `dev.ps1` starts backend and frontend development servers. `test.ps1` runs backend, frontend, extension, and E2E suites and returns the first non-zero exit. `build.ps1` builds frontend and extension. `demo.ps1` upgrades the local database, seeds fixtures, starts the production backend on `127.0.0.1`, and opens the local page.

```powershell
$ErrorActionPreference = 'Stop'
& "$PSScriptRoot\..\backend\.venv\Scripts\python.exe" -m pytest "$PSScriptRoot\..\backend\tests"
pnpm --dir "$PSScriptRoot\..\frontend" test
pnpm --dir "$PSScriptRoot\..\extension" test
pnpm --dir "$PSScriptRoot\..\e2e" test
```

- [ ] **Step 3: Serve the compiled frontend and write exact operating documentation**

Mount `frontend/dist` only when it exists; API routes must be registered first. Use these document headings so each operational boundary is reviewable:

- `README.md`: Prerequisites; Bootstrap; Development; Offline Demo; Load the Edge Extension; Pair the Extension; Run Tests; Build Outputs; Local Data; Uninstall.
- `docs/architecture.md`: Components; Loopback Trust Boundary; Data Flow; Database; Extension Communication.
- `docs/data-source-policy.md`: User-Initiated Capture; Prohibited Data; Login and CAPTCHA; No Automated Ordering; Fixture Versus Live Status.
- `docs/platform-adapters.md`: Adapter Contract; JD Fixture; Taobao/Tmall Fixture; PDD Fixture; Structured Failures; Live Validation Not Completed.
- `docs/subsidy-rules.md`: Region Selection; Rule Fields; Precedence; Confirmed Versus Estimated; Settlement Disclaimer.
- `docs/testing.md`: Backend; Frontend; Extension; Offline E2E; Manual Live Acceptance.

`demo.ps1` accepts a `[switch]$NoOpen` parameter for Playwright and opens the browser only when that switch is absent.

- [ ] **Step 4: Run the complete verification matrix**

Run:

```powershell
.\scripts\bootstrap.ps1
.\scripts\test.ps1
.\scripts\build.ps1
git status --short
```

Expected:

- Backend pytest: PASS.
- Frontend Vitest and type/build: PASS.
- Extension Vitest and build: PASS.
- Playwright offline comparison: PASS using local fixtures.
- `git status --short` shows only the intended plan-execution changes before commit.
- No command requires a live platform account, Cookie, API key, or global tool upgrade.

- [ ] **Step 5: Commit the offline MVP handoff**

```powershell
git add scripts e2e README.md docs backend frontend extension fixtures
git commit -m "feat: complete offline price comparison mvp"
```

## Completion Gate

Before claiming this plan complete, verify all of the following with fresh command output:

- `scripts\test.ps1` exits with code 0.
- `scripts\build.ps1` exits with code 0.
- `/api/health` reports version `0.1.0` and database `ok`.
- “苹果17” returns three standard model choices before any offers are shown.
- The fixed flow accepts exactly one comparable offer per platform and excludes at least five interference records.
- Estimated subsidy never changes default comparable-price order.
- Price history survives backend restart.
- The built extension is loadable in Edge and has no cookie, history, or wildcard host permission.
- Platform status says fixture parsing passes and live validation is not completed.
- The README can start the offline demo without Codex.

## Self-Review Result

- Spec coverage: catalog, unified offers, deterministic matching, price normalization, subsidy states, persistence, history, single-page workbench, extension privacy, three fixture adapters, API errors, tests, and offline delivery are mapped to Tasks 1–14.
- Deliberately deferred to the live-adapter plan: real JD/Taobao/Tmall/PDD selectors, signed-in manual capture, CAPTCHA observations, and per-platform acceptance records.
- Deliberately deferred to the Windows-completion plan: complete catalog/rule CRUD screens, manual-offer and pasted-link workflows, backup/restore execution, data cleanup UI, desktop shortcut packaging, and Tauri reassessment.
- Completeness scan: no unfinished markers, vague validation/error-handling instructions, or undefined repeat-by-reference steps remain.
- Type consistency: the shared names `MatchResult`, `PriceBreakdown`, `SubsidyDecision`, `EvaluatedOffer`, `OfferView`, and `PlatformOfferBatch` are introduced before their consumers and remain unchanged across tasks.
- Scope check: every deferred item belongs to one of the two named follow-on plans; no approved offline-MVP requirement is unassigned.
