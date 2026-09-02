from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.catalog import get_db
from app.schemas.extension import (
    ExtensionOfferSubmission,
    PairingCodeInput,
    PairingCodeResponse,
    PairingTokenResponse,
)
from app.schemas.search_sessions import IngestionSummary, PlatformOfferBatch
from app.services.extension_pairing import (
    PairingCodeConsumed,
    PairingError,
    create_pairing_code,
    issue_extension_token,
    verify_extension_token,
)
from app.services.offer_ingestion import ingest_candidates


router = APIRouter(prefix="/api/extension", tags=["extension"])
PLATFORM_NAMES = {"jd": "京东", "taobao": "淘宝", "pdd": "拼多多"}


def require_extension_token(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> None:
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="需要扩展令牌")
    if not verify_extension_token(db, authorization[len(prefix):]):
        raise HTTPException(status_code=401, detail="扩展令牌无效")


@router.post("/pairing-code", response_model=PairingCodeResponse)
def pairing_code(db: Session = Depends(get_db)) -> PairingCodeResponse:
    return PairingCodeResponse(code=create_pairing_code(db))


@router.post("/pair", response_model=PairingTokenResponse)
def pair(value: PairingCodeInput, db: Session = Depends(get_db)) -> PairingTokenResponse:
    try:
        return PairingTokenResponse(token=issue_extension_token(db, value.code))
    except PairingCodeConsumed as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PairingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/offers", response_model=IngestionSummary)
def submit_offers(
    value: ExtensionOfferSubmission,
    _authorized: None = Depends(require_extension_token),
    db: Session = Depends(get_db),
) -> IngestionSummary:
    try:
        return ingest_candidates(
            db,
            value.search_session_id,
            PlatformOfferBatch(
                platform=value.platform,
                platform_name=value.platform_name or PLATFORM_NAMES.get(value.platform, value.platform),
                adapter_version=value.adapter_version,
                source_type="extension",
                items=value.items,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
