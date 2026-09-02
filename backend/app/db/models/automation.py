from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    __table_args__ = (
        UniqueConstraint(
            "search_session_id",
            "platform",
            name="uq_collection_run_session_platform",
        ),
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
        UniqueConstraint(
            "collection_run_id",
            "platform_sku_id",
            name="uq_collection_candidate_sku",
        ),
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
        UniqueConstraint(
            "collection_run_id",
            "region_code",
            name="uq_collection_task_region",
        ),
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
