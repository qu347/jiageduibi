from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.catalog import get_db
from app.schemas.history import PlatformStatusResponse
from app.services.platform_status import get_platform_status


router = APIRouter(prefix="/api/platforms", tags=["platforms"])


@router.get("/status", response_model=PlatformStatusResponse)
def status(db: Session = Depends(get_db)) -> PlatformStatusResponse:
    return PlatformStatusResponse(items=get_platform_status(db))
