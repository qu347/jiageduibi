from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SubsidyRule(Base):
    __tablename__ = "subsidy_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    region_code: Mapped[str] = mapped_column(String(12), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    max_unit_price_cents: Mapped[int | None] = mapped_column(Integer)
    subsidy_rate_basis_points: Mapped[int] = mapped_column(Integer)
    subsidy_cap_cents: Mapped[int | None] = mapped_column(Integer)
    participating_platforms_json: Mapped[str] = mapped_column(Text)
    participating_shop_types_json: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
