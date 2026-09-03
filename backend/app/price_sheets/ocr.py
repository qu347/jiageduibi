from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol

from PIL import Image, UnidentifiedImageError

from app.price_sheets.contracts import OcrLine


MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
_CONTENT_TYPES = {
    "image/jpeg": ("JPEG", ".jpg"),
    "image/png": ("PNG", ".png"),
    "image/webp": ("WEBP", ".webp"),
}


class ImageValidationError(ValueError):
    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


class OcrUnavailableError(RuntimeError):
    pass


class OcrEngine(Protocol):
    def recognize(self, image_path: Path) -> list[OcrLine]: ...


def _validate_image(data: bytes, content_type: str) -> str:
    expected = _CONTENT_TYPES.get(content_type.lower())
    if expected is None:
        raise ImageValidationError("unsupported_type", "只支持 JPG、PNG 或 WebP 图片")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageValidationError("file_too_large", "图片不能超过 10 MiB")
    try:
        with Image.open(BytesIO(data)) as image:
            actual_format = image.format
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ImageValidationError("invalid_image", "图片内容无法识别") from exc
    if actual_format != expected[0]:
        raise ImageValidationError("type_mismatch", "图片内容与声明的文件类型不一致")
    if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
        raise ImageValidationError("too_many_pixels", "图片像素不能超过 2000 万")
    return expected[1]


def recognize_image(data: bytes, content_type: str, engine: OcrEngine) -> list[OcrLine]:
    suffix = _validate_image(data, content_type)
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(prefix="price-sheet-", suffix=suffix, delete=False) as temporary:
            temporary.write(data)
            temporary_path = Path(temporary.name)
        return engine.recognize(temporary_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


class PaddleOcrEngine:
    def __init__(self) -> None:
        self._engine: object | None = None

    def _get_engine(self) -> object:
        if self._engine is not None:
            return self._engine
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise OcrUnavailableError("本机尚未安装 PaddleOCR") from exc
        self._engine = PaddleOCR(
            lang="ch",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        return self._engine

    def recognize(self, image_path: Path) -> list[OcrLine]:
        engine = self._get_engine()
        rows: list[OcrLine] = []
        for result in engine.predict(str(image_path)):  # type: ignore[attr-defined]
            payload = getattr(result, "json", result)
            if callable(payload):
                payload = payload()
            if not isinstance(payload, dict):
                continue
            recognized = payload.get("res", payload)
            if not isinstance(recognized, dict):
                continue
            texts = recognized.get("rec_texts", [])
            scores = recognized.get("rec_scores", [])
            polygons = recognized.get("rec_polys", [])
            for text, score, polygon in zip(texts, scores, polygons, strict=False):
                points = tuple((float(point[0]), float(point[1])) for point in polygon)
                rows.append(OcrLine(str(text), float(score), points))
        return rows
