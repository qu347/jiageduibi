from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductSeries(Base):
    __tablename__ = "product_series"
    __table_args__ = (UniqueConstraint("brand_id", "name", name="uq_product_series_brand_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductModel(Base):
    __tablename__ = "product_models"
    __table_args__ = (UniqueConstraint("series_id", "model_name", name="uq_product_models_series_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("product_series.id"), index=True)
    model_name: Mapped[str] = mapped_column(String(160))
    model_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint(
            "model_id",
            "storage",
            "memory",
            "color",
            "region_version",
            "condition",
            name="uq_product_variants_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("product_models.id"), index=True)
    sku_code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    storage: Mapped[str] = mapped_column(String(32))
    memory: Mapped[str | None] = mapped_column(String(32))
    color: Mapped[str] = mapped_column(String(80))
    region_version: Mapped[str] = mapped_column(String(80))
    condition: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductAlias(Base):
    __tablename__ = "product_aliases"
    __table_args__ = (
        UniqueConstraint("model_id", "normalized_alias", name="uq_product_aliases_model_alias"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("product_models.id"), index=True)
    alias: Mapped[str] = mapped_column(String(180))
    normalized_alias: Mapped[str] = mapped_column(String(180), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
