"""Mistral OCR service — wraps the Mistral document OCR API.

Workflow:
1. Upload the PDF/image bytes to Mistral Files API with purpose="ocr".
2. Obtain a signed URL for the uploaded file.
3. Call ocr.process() with a DocumentURLChunk pointing at that URL.
4. Delete the remote file to avoid storage accumulation.
5. Return {text, pages, raw} to the caller.

Environment variables required:
    MISTRAL_API_KEY       – Mistral API key (raises RuntimeError if absent)
    MISTRAL_OCR_MODEL     – model name (default: mistral-ocr-latest)
"""

from __future__ import annotations

import io
import os
from typing import Any

import mistralai
from mistralai.models.files_api_routes_upload_fileop import File as MistralFile


def _get_client() -> mistralai.Mistral:
    api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY not configured")
    return mistralai.Mistral(api_key=api_key)


def ocr_document(file_bytes: bytes, filename: str) -> dict[str, Any]:
    """Run Mistral OCR on *file_bytes* (PDF or image).

    Args:
        file_bytes: Raw bytes of the uploaded file.
        filename:   Original filename (used as the remote file name and for
                    content-type sniffing).

    Returns:
        A dict with keys:
            text       – full extracted text (all pages concatenated)
            pages      – list of per-page dicts: {index, markdown}
            raw        – the raw OCRResponse object for advanced callers

    Raises:
        RuntimeError: if MISTRAL_API_KEY is not set.
        ValueError:   if file_bytes is empty.
    """
    if not file_bytes:
        raise ValueError("file_bytes must not be empty")

    model = os.environ.get("MISTRAL_OCR_MODEL", "mistral-ocr-latest")

    client = _get_client()  # raises RuntimeError if key absent

    # Determine a basic content-type so Mistral knows what it's receiving
    lower = filename.lower()
    if lower.endswith(".pdf"):
        content_type = "application/pdf"
    elif lower.endswith(".png"):
        content_type = "image/png"
    elif lower.endswith(".jpg") or lower.endswith(".jpeg"):
        content_type = "image/jpeg"
    elif lower.endswith(".webp"):
        content_type = "image/webp"
    else:
        content_type = "application/octet-stream"

    # 1. Upload file to Mistral Files API
    uploaded = client.files.upload(
        file=MistralFile(
            file_name=filename,
            content=io.BytesIO(file_bytes),
            content_type=content_type,
        ),
        purpose="ocr",
    )
    file_id: str = uploaded.id

    try:
        # 2. Get a signed URL
        signed = client.files.get_signed_url(file_id=file_id)
        document_url: str = signed.url

        # 3. Call OCR
        response = client.ocr.process(
            model=model,
            document=mistralai.DocumentURLChunk(document_url=document_url),
        )
    finally:
        # 4. Clean up the remote file regardless of OCR success/failure
        try:
            client.files.delete(file_id=file_id)
        except Exception:
            pass  # best-effort cleanup

    # 5. Shape the result
    pages_out = [
        {"index": page.index, "markdown": page.markdown}
        for page in response.pages
    ]
    full_text = "\n\n".join(page.markdown for page in response.pages)

    return {
        "text": full_text,
        "pages": pages_out,
        "raw": response,
    }
