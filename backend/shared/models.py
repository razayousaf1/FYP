# -*- coding: utf-8 -*-
"""
Shared data models for Contract.AI backend modules.
Every OCR-producing function (Vision API, PDF text-layer, DOCX) returns
this SAME shape, so downstream modules (preprocessing, transliteration,
risk detection) never need to know which extraction method was used.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PageResult:
    """OCR/extraction result for a single page (images and DOCX are always 1 page)."""
    page_number: int
    text: str
    confidence: Optional[float] = None  # 0.0-1.0, None if not applicable (e.g. DOCX)


@dataclass
class OCRResult:
    """
    Unified result returned by extract_text(), regardless of source.

    Attributes:
        full_text: complete extracted text, all pages joined with newlines
        pages: per-page breakdown (useful for multi-page PDFs)
        source: how the text was obtained - "vision_api" | "pdf_text_layer" | "docx"
        average_confidence: mean OCR confidence across all pages (None for
            pdf_text_layer / docx since there's no OCR confidence - it's exact text)
        warnings: non-fatal issues encountered during extraction, e.g.
            "Page 3 had low confidence (0.61)"
    """
    full_text: str
    pages: List[PageResult] = field(default_factory=list)
    source: str = ""
    average_confidence: Optional[float] = None
    warnings: List[str] = field(default_factory=list)
    page_count: int = 0

    def __post_init__(self):
        if self.page_count == 0:
            self.page_count = len(self.pages) or 1


class OCRError(Exception):
    """Raised when text extraction fails outright (corrupt file, unsupported format, API error)."""
    pass


class UnsupportedFileTypeError(OCRError):
    """Raised when the uploaded file's mime type isn't PDF, PNG, JPG, JPEG, or DOCX (per FR-01)."""
    pass
