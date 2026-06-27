"""Documents router — exposes PDF/image OCR via the Mistral OCR service.

Mount at: /api/documents

Endpoints:
    POST /ocr   – accept a multipart file upload, run OCR, return text.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.services.pdf_ocr import ocr_document

router = APIRouter()

# Maximum accepted upload size: 50 MB
_MAX_BYTES = 50 * 1024 * 1024

# Allowed MIME types / extensions
_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}


@router.post("/ocr")
async def ocr_endpoint(file: UploadFile) -> JSONResponse:
    """Run Mistral OCR on an uploaded PDF or image.

    Returns:
        200  {filename, text, page_count}
        400  Bad or empty upload
        503  MISTRAL_API_KEY not configured
    """
    # --- 400: missing / empty filename ----------------------------------------
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # --- 400: unsupported content type ----------------------------------------
    ct = (file.content_type or "").lower().split(";")[0].strip()
    ext = file.filename.lower().rsplit(".", 1)[-1]
    allowed_ext = {"pdf", "png", "jpg", "jpeg", "webp"}

    if ct not in _ALLOWED_CONTENT_TYPES and ext not in allowed_ext:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ct}'. "
                "Accepted types: PDF, PNG, JPG, WEBP."
            ),
        )

    # --- Read upload ----------------------------------------------------------
    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if len(file_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(file_bytes):,} bytes). Maximum is 50 MB.",
        )

    # --- Call OCR service -----------------------------------------------------
    try:
        result = ocr_document(file_bytes=file_bytes, filename=file.filename)
    except RuntimeError as exc:
        # MISTRAL_API_KEY not configured
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(
        content={
            "filename": file.filename,
            "text": result["text"],
            "page_count": len(result["pages"]),
        }
    )
