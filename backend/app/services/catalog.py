from dataclasses import dataclass

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.catalog import Brand, ProductAlias, ProductModel, ProductSeries, ProductVariant
from app.schemas.catalog import (
    CatalogExport,
    CatalogImport,
    CatalogModelSummary,
    CatalogVariantView,
)


@dataclass(frozen=True)
class CatalogImportError(Exception):
    message: str


def normalize_keyword(value: str) -> str:
    return "".join(value.casefold().split()).replace("苹果", "iphone")


def model_rank(query: str, aliases: list[str]) -> int:
    normalized = normalize_keyword(query)
    scores = [
        100 if normalize_keyword(alias) == normalized else round(fuzz.ratio(normalized, normalize_keyword(alias)))
        for alias in aliases
    ]
    return max(scores, default=0)


def import_catalog(db: Session, payload: CatalogImport) -> dict[str, int]:
    existing_brands = set(db.scalars(select(Brand.name).where(Brand.deleted_at.is_(None))))
    incoming_brands = {item.name for item in payload.brands}
    available_brands = existing_brands | incoming_brands
    for item in payload.series:
        if item.brand not in available_brands:
            raise CatalogImportError(f"系列 {item.name} 引用了不存在的品牌 {item.brand}")

    existing_series = set(db.scalars(select(ProductSeries.name).where(ProductSeries.deleted_at.is_(None))))
    incoming_series = {item.name for item in payload.series}
    available_series = existing_series | incoming_series
    for item in payload.models:
        if item.series not in available_series:
            raise CatalogImportError(f"型号 {item.code} 引用了不存在的系列 {item.series}")

    existing_models = set(db.scalars(select(ProductModel.model_code).where(ProductModel.deleted_at.is_(None))))
    incoming_models = {item.code for item in payload.models}
    available_models = existing_models | incoming_models
    for item in payload.variants:
        if item.model_code not in available_models:
            raise CatalogImportError(f"SKU {item.sku_code} 引用了不存在的型号 {item.model_code}")

    try:
        brand_by_name = {
            brand.name: brand for brand in db.scalars(select(Brand).where(Brand.name.in_(available_brands)))
        }
        for item in payload.brands:
            brand = brand_by_name.get(item.name)
            if brand is None:
                brand = Brand(name=item.name)
                db.add(brand)
                db.flush()
                brand_by_name[item.name] = brand
            brand.deleted_at = None

        series_by_name = {
            series.name: series
            for series in db.scalars(select(ProductSeries).where(ProductSeries.name.in_(available_series)))
        }
        for item in payload.series:
            series = series_by_name.get(item.name)
            brand = brand_by_name[item.brand]
            if series is None:
                series = ProductSeries(brand_id=brand.id, name=item.name)
                db.add(series)
                db.flush()
                series_by_name[item.name] = series
            series.brand_id = brand.id
            series.active = True
            series.deleted_at = None

        model_by_code = {
            model.model_code: model
            for model in db.scalars(select(ProductModel).where(ProductModel.model_code.in_(available_models)))
        }
        for item in payload.models:
            model = model_by_code.get(item.code)
            series = series_by_name[item.series]
            if model is None:
                model = ProductModel(
                    series_id=series.id,
                    model_name=item.name,
                    model_code=item.code,
                    category=item.category,
                )
                db.add(model)
                db.flush()
                model_by_code[item.code] = model
            else:
                model.series_id = series.id
                model.model_name = item.name
                model.category = item.category
            model.active = True
            model.deleted_at = None

            aliases_by_normalized: dict[str, str] = {}
            for alias_value in item.aliases:
                aliases_by_normalized.setdefault(normalize_keyword(alias_value), alias_value)

            for normalized, alias_value in aliases_by_normalized.items():
                alias = db.scalar(
                    select(ProductAlias).where(
                        ProductAlias.model_id == model.id,
                        ProductAlias.normalized_alias == normalized,
                    )
                )
                if alias is None:
                    db.add(ProductAlias(model_id=model.id, alias=alias_value, normalized_alias=normalized))
                else:
                    alias.alias = alias_value
                    alias.active = True
                    alias.deleted_at = None

        for item in payload.variants:
            variant = db.scalar(select(ProductVariant).where(ProductVariant.sku_code == item.sku_code))
            model = model_by_code[item.model_code]
            if variant is None:
                variant = ProductVariant(model_id=model.id, sku_code=item.sku_code)
                db.add(variant)
            variant.model_id = model.id
            variant.storage = item.storage
            variant.memory = item.memory
            variant.color = item.color
            variant.region_version = item.region_version
            variant.condition = item.condition
            variant.active = True
            variant.deleted_at = None

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "brands": len(payload.brands),
        "series": len(payload.series),
        "models": len(payload.models),
        "variants": len(payload.variants),
    }


def search_catalog(db: Session, query: str) -> list[CatalogModelSummary]:
    rows = db.execute(
        select(ProductModel, ProductSeries, Brand)
        .join(ProductSeries, ProductModel.series_id == ProductSeries.id)
        .join(Brand, ProductSeries.brand_id == Brand.id)
        .where(
            ProductModel.active.is_(True),
            ProductModel.deleted_at.is_(None),
            ProductSeries.active.is_(True),
            ProductSeries.deleted_at.is_(None),
            Brand.deleted_at.is_(None),
        )
    ).all()

    ranked: list[tuple[int, int, CatalogModelSummary]] = []
    for model, series, brand in rows:
        aliases = list(
            db.scalars(
                select(ProductAlias.alias).where(
                    ProductAlias.model_id == model.id,
                    ProductAlias.active.is_(True),
                    ProductAlias.deleted_at.is_(None),
                )
            )
        )
        score = model_rank(query, [model.model_name, *aliases])
        if score < 60:
            continue
        variants = list(
            db.scalars(
                select(ProductVariant)
                .where(
                    ProductVariant.model_id == model.id,
                    ProductVariant.active.is_(True),
                    ProductVariant.deleted_at.is_(None),
                )
                .order_by(ProductVariant.sku_code)
            )
        )
        summary = CatalogModelSummary(
            id=model.id,
            model_code=model.model_code,
            model_name=model.model_name,
            series_name=series.name,
            brand=brand.name,
            category=model.category,
            score=score,
            variants=[
                CatalogVariantView(
                    id=variant.id,
                    sku_code=variant.sku_code,
                    storage=variant.storage,
                    memory=variant.memory,
                    color=variant.color,
                    region_version=variant.region_version,
                    condition=variant.condition,
                )
                for variant in variants
            ],
        )
        ranked.append((score, len(normalize_keyword(model.model_name)), summary))

    ranked.sort(key=lambda item: (-item[0], -item[1], item[2].model_code))
    return [item[2] for item in ranked]


def get_catalog_variant(db: Session, variant_id: int) -> CatalogVariantView:
    variant = db.scalar(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.active.is_(True),
            ProductVariant.deleted_at.is_(None),
        )
    )
    if variant is None:
        raise ValueError("标准 SKU 不存在或已停用")
    return CatalogVariantView.model_validate(variant, from_attributes=True)


def export_catalog(db: Session) -> CatalogExport:
    brands = list(db.scalars(select(Brand).where(Brand.deleted_at.is_(None)).order_by(Brand.name)))
    series_rows = db.execute(
        select(ProductSeries, Brand)
        .join(Brand, ProductSeries.brand_id == Brand.id)
        .where(ProductSeries.deleted_at.is_(None), Brand.deleted_at.is_(None))
        .order_by(ProductSeries.name)
    ).all()
    model_rows = db.execute(
        select(ProductModel, ProductSeries)
        .join(ProductSeries, ProductModel.series_id == ProductSeries.id)
        .where(ProductModel.deleted_at.is_(None), ProductSeries.deleted_at.is_(None))
        .order_by(ProductModel.model_code)
    ).all()
    variants = list(
        db.scalars(select(ProductVariant).where(ProductVariant.deleted_at.is_(None)).order_by(ProductVariant.sku_code))
    )

    models: list[dict[str, object]] = []
    for model, series in model_rows:
        aliases = list(
            db.scalars(
                select(ProductAlias.alias)
                .where(ProductAlias.model_id == model.id, ProductAlias.deleted_at.is_(None))
                .order_by(ProductAlias.normalized_alias)
            )
        )
        models.append(
            {
                "series": series.name,
                "name": model.model_name,
                "code": model.model_code,
                "category": model.category,
                "aliases": aliases,
            }
        )

    model_codes = dict(db.execute(select(ProductModel.id, ProductModel.model_code)).all())
    return CatalogExport(
        brands=[{"name": brand.name} for brand in brands],
        series=[{"brand": brand.name, "name": series.name} for series, brand in series_rows],
        models=models,
        variants=[
            {
                "model_code": model_codes[variant.model_id],
                "sku_code": variant.sku_code,
                "storage": variant.storage,
                "memory": variant.memory,
                "color": variant.color,
                "region_version": variant.region_version,
                "condition": variant.condition,
            }
            for variant in variants
        ],
    )
