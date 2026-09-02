from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.catalog import get_db
from app.schemas.search_sessions import (
    CreateSearchSession,
    IngestionSummary,
    PlatformOfferBatch,
    SearchResult,
    SearchSessionView,
)
from app.services.offer_ingestion import ingest_candidates
from app.services.search_sessions import (
    build_search_result,
    create_search_session,
    finalize_search_session,
    get_search_session,
)


router = APIRouter(prefix="/api/search-sessions", tags=["search-sessions"])


def api_error(message: str, cause: str) -> dict[str, object]:
    return {
        "what_happened": message,
        "possible_cause": cause,
        "partial_saved": False,
        "next_action": "检查目标 SKU、会话状态或报价数据后重试",
    }


@router.post("", response_model=SearchSessionView, status_code=status.HTTP_201_CREATED)
def post_session(value: CreateSearchSession, db: Session = Depends(get_db)) -> SearchSessionView:
    try:
        result = create_search_session(db, value)
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=api_error("创建搜索会话失败", str(exc))) from exc


@router.get("/{session_id}", response_model=SearchSessionView)
def get_session(session_id: int, db: Session = Depends(get_db)) -> SearchSessionView:
    try:
        return get_search_session(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=api_error("读取搜索会话失败", str(exc))) from exc


@router.get("/{session_id}/result", response_model=SearchResult)
def get_result(session_id: int, db: Session = Depends(get_db)) -> SearchResult:
    try:
        return build_search_result(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=api_error("预览搜索结果失败", str(exc))) from exc


@router.post("/{session_id}/offers", response_model=IngestionSummary)
def post_offers(
    session_id: int,
    value: PlatformOfferBatch,
    db: Session = Depends(get_db),
) -> IngestionSummary:
    try:
        return ingest_candidates(db, session_id, value)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=api_error("导入平台报价失败", str(exc))) from exc


@router.post("/{session_id}/finalize", response_model=SearchResult)
def finalize(session_id: int, db: Session = Depends(get_db)) -> SearchResult:
    try:
        return finalize_search_session(db, session_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=api_error("完成搜索会话失败", str(exc))) from exc
