from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.catalog import get_db
from app.schemas.history import HistoryResponse
from app.services.history import get_price_history


router = APIRouter(prefix="/api/price-history", tags=["history"])


@router.get("", response_model=HistoryResponse)
def history(
    variant_id: int = Query(gt=0),
    platform: str | None = None,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
) -> HistoryResponse:
    return HistoryResponse(
        points=get_price_history(db, variant_id, platform, from_date, to_date),
    )
