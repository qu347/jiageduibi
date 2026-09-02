from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.schemas.catalog import CatalogExport, CatalogImport, CatalogSearchResponse, CatalogVariantView
from app.services.catalog import CatalogImportError, export_catalog, get_catalog_variant, import_catalog, search_catalog


router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def get_db(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session


@router.get("/search", response_model=CatalogSearchResponse)
def search(q: str = Query(min_length=1), db: Session = Depends(get_db)) -> CatalogSearchResponse:
    return CatalogSearchResponse(items=search_catalog(db, q))


@router.get("/variants/{variant_id}", response_model=CatalogVariantView)
def get_variant(variant_id: int, db: Session = Depends(get_db)) -> CatalogVariantView:
    try:
        return get_catalog_variant(db, variant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "what_happened": "恢复标准 SKU 失败",
                "possible_cause": str(exc),
                "partial_saved": False,
                "next_action": "重新检索并确认标准 SKU",
            },
        ) from exc


@router.post("/import")
def import_data(payload: CatalogImport, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        counts = import_catalog(db, payload)
    except CatalogImportError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail={
                "what_happened": "型号词典导入失败",
                "possible_cause": exc.message,
                "partial_saved": False,
                "next_action": "检查品牌、系列、型号和 SKU 引用后重新导入",
            },
        ) from exc
    return {"status": "ok", "counts": counts}


@router.get("/export", response_model=CatalogExport)
def export_data(db: Session = Depends(get_db)) -> CatalogExport:
    return export_catalog(db)
