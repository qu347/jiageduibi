from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.catalog import get_db
from app.schemas.search_sessions import OfferView
from app.services.search_sessions import list_offer_views


router = APIRouter(prefix="/api/offers", tags=["offers"])


@router.get("")
def get_offers(
    search_session_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
) -> dict[str, list[OfferView]]:
    return {"items": list_offer_views(db, search_session_id)}
