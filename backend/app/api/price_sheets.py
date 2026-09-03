from __future__ import annotations

from collections.abc import Callable
from pathlib import PurePath
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.catalog import get_db
from app.price_sheets.ocr import (
    MAX_IMAGE_BYTES,
    ImageValidationError,
    OcrUnavailableError,
    recognize_image,
)
from app.price_sheets.parser import parse_price_sheet
from app.price_sheets.service import (
    create_batch,
    get_batch_detail,
    get_results,
    replace_items,
    request_pause,
    request_stop,
    resume_batch,
    retry_failed,
    start_batch,
)
from app.schemas.price_sheets import PriceSheetBatchDetail, PriceSheetItemsUpdate, PriceSheetResultsView


router = APIRouter(prefix="/api/price-sheet-batches", tags=["price-sheets"])


def api_error(message: str, cause: str, *, partial_saved: bool = False, next_action: str) -> dict[str, object]:
    return {
        "what_happened": message,
        "possible_cause": cause,
        "partial_saved": partial_saved,
        "next_action": next_action,
    }


@router.post("/recognize", response_model=PriceSheetBatchDetail, status_code=status.HTTP_201_CREATED)
async def recognize_price_sheet(
    request: Request,
    x_file_name: str = Header(default="price-sheet"),
    db: Session = Depends(get_db),
) -> PriceSheetBatchDetail:
    try:
        data = await _read_limited_body(request)
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        lines = recognize_image(data, content_type, request.app.state.ocr_engine_factory())
        parsed = parse_price_sheet(lines, request.app.state.clock())
        detail = create_batch(db, _safe_file_name(x_file_name), parsed)
        db.commit()
        return detail
    except ImageValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=api_error("识别价目表失败", exc.safe_message, next_action="选择符合限制的图片后重试"),
        ) from exc
    except OcrUnavailableError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail=api_error("本机 OCR 当前不可用", str(exc), next_action="运行安装脚本或联网初始化模型后重试"),
        ) from exc


@router.get("/{batch_id}", response_model=PriceSheetBatchDetail)
def get_price_sheet_batch(batch_id: int, db: Session = Depends(get_db)) -> PriceSheetBatchDetail:
    return _call(db, lambda: get_batch_detail(db, batch_id), "读取价目表批次失败")


@router.get("/{batch_id}/results", response_model=PriceSheetResultsView)
def get_price_sheet_results(batch_id: int, db: Session = Depends(get_db)) -> PriceSheetResultsView:
    try:
        return get_results(db, batch_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=api_error("读取价目表结果失败", str(exc), next_action="检查批次编号后重试"),
        ) from exc


@router.put("/{batch_id}/items", response_model=PriceSheetBatchDetail)
def put_price_sheet_items(
    batch_id: int,
    payload: PriceSheetItemsUpdate,
    db: Session = Depends(get_db),
) -> PriceSheetBatchDetail:
    return _call(
        db,
        lambda: replace_items(db, batch_id, payload.price_date, payload.items),
        "保存价目表校对结果失败",
    )


@router.post("/{batch_id}/start", response_model=PriceSheetBatchDetail)
def post_start_price_sheet(batch_id: int, request: Request, db: Session = Depends(get_db)) -> PriceSheetBatchDetail:
    detail = _call(db, lambda: start_batch(db, batch_id), "启动价目表比价失败")
    _submit_if_available(request, batch_id)
    return detail


@router.post("/{batch_id}/pause", response_model=PriceSheetBatchDetail)
def post_pause_price_sheet(batch_id: int, db: Session = Depends(get_db)) -> PriceSheetBatchDetail:
    return _call(db, lambda: request_pause(db, batch_id), "暂停价目表比价失败")


@router.post("/{batch_id}/resume", response_model=PriceSheetBatchDetail)
def post_resume_price_sheet(batch_id: int, request: Request, db: Session = Depends(get_db)) -> PriceSheetBatchDetail:
    detail = _call(db, lambda: resume_batch(db, batch_id), "继续价目表比价失败")
    _submit_if_available(request, batch_id)
    return detail


@router.post("/{batch_id}/stop", response_model=PriceSheetBatchDetail)
def post_stop_price_sheet(batch_id: int, db: Session = Depends(get_db)) -> PriceSheetBatchDetail:
    return _call(db, lambda: request_stop(db, batch_id), "停止价目表比价失败")


@router.post("/{batch_id}/retry-failed", response_model=PriceSheetBatchDetail)
def post_retry_price_sheet(batch_id: int, request: Request, db: Session = Depends(get_db)) -> PriceSheetBatchDetail:
    detail = _call(db, lambda: retry_failed(db, batch_id), "重试失败地区失败")
    _submit_if_available(request, batch_id)
    return detail


async def _read_limited_body(request: Request) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_IMAGE_BYTES:
            raise ImageValidationError("file_too_large", "图片不能超过 10 MiB")
        chunks.append(chunk)
    return b"".join(chunks)


def _safe_file_name(value: str) -> str:
    decoded = unquote(value).replace("\\", "/")
    name = PurePath(decoded.split("/")[-1]).name.strip()
    return (name or "price-sheet")[:255]


def _call(
    db: Session,
    operation: Callable[[], PriceSheetBatchDetail],
    message: str,
) -> PriceSheetBatchDetail:
    try:
        detail = operation()
        db.commit()
        return detail
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=api_error(message, str(exc), partial_saved=False, next_action="检查校对内容和批次状态后重试"),
        ) from exc


def _submit_if_available(request: Request, batch_id: int) -> None:
    coordinator = getattr(request.app.state, "price_sheet_coordinator", None)
    if coordinator is not None:
        coordinator.submit(batch_id)
