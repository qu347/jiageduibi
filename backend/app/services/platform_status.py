from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.offers import AdapterRun, Platform
from app.schemas.history import PlatformStatus


PLATFORM_ORDER = ("jd", "taobao", "pdd")


def get_platform_status(db: Session) -> list[PlatformStatus]:
    rows = db.execute(
        select(AdapterRun, Platform)
        .join(Platform, AdapterRun.platform_id == Platform.id)
        .where(AdapterRun.source_type == "fixture")
        .order_by(AdapterRun.finished_at.desc(), AdapterRun.id.desc())
    ).all()
    latest_by_platform: dict[str, AdapterRun] = {}
    for run, platform in rows:
        latest_by_platform.setdefault(platform.code, run)

    return [
        PlatformStatus(
            platform=platform,
            fixture_status=(
                "not_run" if platform not in latest_by_platform else
                "passing" if latest_by_platform[platform].status == "passing" else "failing"
            ),
            live_status="not_validated",
        )
        for platform in PLATFORM_ORDER
    ]
