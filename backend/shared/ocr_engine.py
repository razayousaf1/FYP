# -*- coding: utf-8 -*-
"""
Contract.AI - OCR Engine
=========================
Single entry point for extracting text from any supported upload
(PDF, PNG, JPG, JPEG, DOCX - per FR-01).

Design:
    extract_text() is the ONLY function the rest of the backend should ever
    call. Everything downstream (preprocessing, transliteration, risk
    detection) works with the OCRResult dataclass and never touches
    Vision API, PyMuPDF, or python-docx directly.

    This means the underlying OCR engine (currently Google Cloud Vision)
    can be swapped later by editing only the _vision_ocr_image_bytes()
    function - nothing else in the codebase changes. This directly
    supports NFR-10 (independently replaceable backend modules).

Routing logic:
    .docx           -> python-docx (no OCR needed, it's already digital text)
    .pdf w/ text     -> pdfplumber extracts directly (no OCR needed, fast & free)
    .pdf scanned     -> rasterized page-by-page with PyMuPDF, each page sent to Vision
    .png/.jpg/.jpeg  -> sent to Vision directly
"""
import io
import os
from typing import List, Optional, Tuple

from shared.models import OCRResult, PageResult, OCRError, UnsupportedFileTypeError
from shared.gcp_credentials import get_credentials_path

# Vision client is created lazily (only when actually needed) so that
# importing this module doesn't require GCP credentials to be present -
# useful for unit-testing the DOCX/PDF-text-layer paths in isolation.
_vision_client = None

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".docx"}

# Below this, a PDF page is treated as "scanned" (no usable text layer)
# and gets routed to Vision instead of pdfplumber.
MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER = 20

# Vision word-confidence below this triggers a warning surfaced to the caller
# (useful for the frontend to show "low quality scan" hints later).
LOW_CONFIDENCE_THRESHOLD = 0.70

# Vision page rasterization resolution. 300 DPI is the standard sweet spot
# for OCR accuracy on printed legal documents without producing huge images.
RASTER_DPI = 300

# Which engine actually does the OCR work for images / scanned PDFs.
# "vision"  -> Google Cloud Vision API (real OCR, best accuracy, needs billing - now available)
# "qwen2vl" -> runs Qwen2-VL locally on your GPU (real OCR, no cloud cost, needs GPU)
# "mock"    -> returns fixed sample text, no GPU/credentials needed (for quick testing)
# Override with: export OCR_ENGINE=vision
OCR_ENGINE = os.environ.get("OCR_ENGINE", "vision")

# Qwen2-VL model size. 2B fits comfortably on a free Colab T4 (16GB VRAM) or
# any local GPU with >=6GB VRAM. Only bump to 7B if you have >=16GB VRAM free -
# it's meaningfully more accurate but much slower and heavier.
QWEN2VL_MODEL_NAME = os.environ.get("QWEN2VL_MODEL_NAME", "Qwen/Qwen2-VL-2B-Instruct")

_qwen2vl_model = None
_qwen2vl_processor = None


def _get_vision_client():
    """Lazily creates the Vision API client. Raises a clear error if credentials are missing.

    Locally, GOOGLE_APPLICATION_CREDENTIALS (from .env) must point at a real key file.
    On Cloud Run it is not set, and the client uses the service account automatically."""
    global _vision_client
    if _vision_client is None:
        try:
            from google.cloud import vision
        except ImportError as e:
            raise OCRError(
                "google-cloud-vision is not installed. Run: pip install google-cloud-vision"
            ) from e

        # Only fails if the variable is set but points at a missing file
        try:
            get_credentials_path()
        except RuntimeError as e:
            raise OCRError(str(e)) from e

        try:
            _vision_client = vision.ImageAnnotatorClient()
        except Exception as e:
            raise OCRError(
                f"Failed to create Vision API client - credentials may be missing or invalid. "
                f"Locally, set GOOGLE_APPLICATION_CREDENTIALS in .env, e.g.:\n"
                f"  GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/gcp-credentials.json\n"
                f"On Cloud Run, check that the service account can use the Vision API. "
                f"Details: {e}"
            ) from e
    return _vision_client


def extract_text(file_bytes: bytes, filename: str) -> OCRResult:
    """
    Main entry point. Detects file type from filename extension and routes
    to the appropriate extraction path.

    Args:
        file_bytes: raw file content
        filename: original filename, used only to determine the extension
                   (e.g. "kiraya_naama.pdf")

    Returns:
        OCRResult with full_text, per-page breakdown, source, and confidence.

    Raises:
        UnsupportedFileTypeError: extension isn't one FR-01 allows
        OCRError: extraction failed (corrupt file, Vision API error, etc.)
    """
    ext = os.path.splitext(filename.lower())[1]

    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"'{ext}' is not supported. Allowed formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if not file_bytes:
        raise OCRError("Uploaded file is empty.")

    if ext == ".docx":
        return _extract_docx(file_bytes)
    elif ext == ".pdf":
        return _extract_pdf(file_bytes)
    else:  # .png, .jpg, .jpeg
        return _extract_image(file_bytes)


# ----------------------------------------------------------------------
# DOCX path - no OCR needed, it's already digital text
# ----------------------------------------------------------------------
def _extract_docx(file_bytes: bytes) -> OCRResult:
    try:
        import docx
    except ImportError as e:
        raise OCRError("python-docx is not installed. Run: pip install python-docx") from e

    try:
        document = docx.Document(io.BytesIO(file_bytes))
    except Exception as e:
        raise OCRError(f"Could not read DOCX file - it may be corrupt: {e}") from e

    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs)

    if not full_text.strip():
        raise OCRError("DOCX file contains no extractable text.")

    return OCRResult(
        full_text=full_text,
        pages=[PageResult(page_number=1, text=full_text, confidence=None)],
        source="docx",
        average_confidence=None,
    )


# ----------------------------------------------------------------------
# PDF path - text layer first (fast/free), fall back to Vision per page
# ----------------------------------------------------------------------
def _extract_pdf(file_bytes: bytes) -> OCRResult:
    try:
        import pdfplumber
    except ImportError as e:
        raise OCRError("pdfplumber is not installed. Run: pip install pdfplumber") from e

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_texts = [_normalize_urdu_text((p.extract_text() or "").strip()) for p in pdf.pages]
    except Exception as e:
        raise OCRError(f"Could not read PDF file - it may be corrupt or password-protected: {e}") from e

    if not page_texts:
        raise OCRError("PDF has no pages.")

    has_text_layer = all(len(t) >= MIN_CHARS_PER_PAGE_FOR_TEXT_LAYER for t in page_texts)

    if has_text_layer:
        pages = [
            PageResult(page_number=i + 1, text=t, confidence=None)
            for i, t in enumerate(page_texts)
        ]
        return OCRResult(
            full_text="\n".join(page_texts),
            pages=pages,
            source="pdf_text_layer",
            average_confidence=None,
        )

    # No usable text layer (scanned PDF) -> rasterize each page and OCR with Vision
    return _extract_pdf_via_vision(file_bytes)


def _extract_pdf_via_vision(file_bytes: bytes) -> OCRResult:
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise OCRError("pymupdf is not installed. Run: pip install pymupdf") from e

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise OCRError(f"Could not open scanned PDF for rasterization: {e}") from e

    zoom = RASTER_DPI / 72  # PyMuPDF's base resolution is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)

    pages: List[PageResult] = []
    warnings: List[str] = []
    confidences: List[float] = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        pix = page.get_pixmap(matrix=matrix)
        image_bytes = pix.tobytes("png")

        text, confidence = _vision_ocr_image_bytes(image_bytes)
        page_number = page_index + 1

        if not text.strip():
            warnings.append(f"Page {page_number}: no text detected.")
        elif confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
            warnings.append(f"Page {page_number}: low OCR confidence ({confidence:.2f}).")

        pages.append(PageResult(page_number=page_number, text=text, confidence=confidence))
        if confidence is not None:
            confidences.append(confidence)

    doc.close()

    full_text = "\n".join(p.text for p in pages)
    if not full_text.strip():
        raise OCRError("No text could be extracted from any page of the scanned PDF.")

    avg_confidence = sum(confidences) / len(confidences) if confidences else None

    return OCRResult(
        full_text=full_text,
        pages=pages,
        source=OCR_ENGINE,
        average_confidence=avg_confidence,
        warnings=warnings,
    )


# ----------------------------------------------------------------------
# Urdu text normalization for the PDF text-layer path
# ----------------------------------------------------------------------
def _normalize_urdu_text(text: str) -> str:
    """
    Some PDF generators (particularly older Urdu desktop-publishing tools)
    embed Arabic Presentation Forms glyphs instead of base Unicode characters.
    NFKC normalization reliably converts these back to standard Urdu/Arabic
    characters and is always safe to apply.

    KNOWN LIMITATION (not fixed here): a small number of PDF generators also
    store RTL text in reversed character order. Whether this happens is
    generator-specific (e.g. behaves differently across InPage, MS Word,
    LibreOffice exports) and there is no safe universal detection - blindly
    reversing every PDF would corrupt text from generators that already
    store it correctly. If you hit reversed text with a real collected
    document, flag it and we'll add generator-specific handling rather
    than a blanket fix.
    """
    import unicodedata
    return unicodedata.normalize("NFKC", text)


# ----------------------------------------------------------------------
# Image path (PNG / JPG / JPEG) - straight to Vision
# ----------------------------------------------------------------------
def _extract_image(file_bytes: bytes) -> OCRResult:
    text, confidence = _vision_ocr_image_bytes(file_bytes)

    if not text.strip():
        raise OCRError("No text could be detected in the uploaded image.")

    warnings = []
    if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
        warnings.append(f"Low OCR confidence ({confidence:.2f}) - image quality may be poor.")

    return OCRResult(
        full_text=text,
        pages=[PageResult(page_number=1, text=text, confidence=confidence)],
        source=OCR_ENGINE,
        average_confidence=confidence,
        warnings=warnings,
    )


# ----------------------------------------------------------------------
# OCR dispatcher - routes to Qwen2-VL (real) or the mock, based on OCR_ENGINE
# ----------------------------------------------------------------------
_MOCK_OCR_SAMPLE_TEXT = (
    "کرایہ دار مبلغ 25,000 روپے ماہانہ کرایہ کی مد میں مالک مکان کو ہر ماہ کی پہلی تاریخ کو "
    "ادا کرنے کا پابند ہوگا اور معاہدہ کے آغاز پر ایک ماہ کا ایڈوانس کرایہ پیشگی ادا کرے گا۔ "
    "کرایہ دار معاہدہ کے آغاز پر مبلغ 50,000 روپے بطور سیکورٹی ڈپازٹ مالک مکان کے پاس جمع کروائے گا۔ "
    "کوئی بھی فریق معاہدہ ختم کرنا چاہے تو 30 دن پہلے تحریری نوٹس دینے کا پابند ہوگا۔"
)


def _vision_ocr_image_bytes(image_bytes: bytes) -> Tuple[str, Optional[float]]:
    """
    Runs OCR on a single image and returns (extracted_text, confidence).

    Dispatches to Google Vision API, Qwen2-VL (local GPU), or the mock,
    controlled by the OCR_ENGINE env var. Everything downstream
    (preprocessing, transliteration, risk detection) only ever sees the
    return value of this function - it doesn't know or care which engine ran.
    """
    if OCR_ENGINE == "mock":
        return _MOCK_OCR_SAMPLE_TEXT, 0.93
    elif OCR_ENGINE == "vision":
        return _google_vision_ocr_image_bytes(image_bytes)
    elif OCR_ENGINE == "qwen2vl":
        return _qwen2vl_ocr_image_bytes(image_bytes)
    else:
        raise OCRError(f"Unknown OCR_ENGINE '{OCR_ENGINE}'. Use 'vision', 'qwen2vl', or 'mock'.")


def _google_vision_ocr_image_bytes(image_bytes: bytes) -> Tuple[str, Optional[float]]:
    """
    Runs Vision API's DOCUMENT_TEXT_DETECTION (best for dense printed text,
    per your NFR-03 accuracy requirement) on a single image and returns
    (extracted_text, average_word_confidence).
    """
    from google.cloud import vision

    client = _get_vision_client()
    image = vision.Image(content=image_bytes)

    # language_hints improves Urdu accuracy specifically - Vision auto-detects
    # language but hinting removes ambiguity with Arabic/Farsi script, which
    # share characters with Urdu.
    image_context = vision.ImageContext(language_hints=["ur"])

    try:
        response = client.document_text_detection(image=image, image_context=image_context)
    except Exception as e:
        raise OCRError(f"Vision API request failed: {e}") from e

    if response.error.message:
        raise OCRError(f"Vision API returned an error: {response.error.message}")

    annotation = response.full_text_annotation
    text = annotation.text if annotation else ""
    confidence = _average_word_confidence(annotation) if annotation else None
    return text, confidence


def _average_word_confidence(annotation) -> Optional[float]:
    """Vision doesn't return one overall confidence number - it's per word.
    Average across all words to get a single figure useful for the
    LOW_CONFIDENCE_THRESHOLD check and for surfacing to the frontend."""
    confidences = []
    for page in annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    if word.confidence:
                        confidences.append(word.confidence)
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


def _load_qwen2vl():
    """Lazily loads the Qwen2-VL model + processor once per process (expensive, ~10-30s)."""
    global _qwen2vl_model, _qwen2vl_processor
    if _qwen2vl_model is None:
        try:
            import torch
            from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
        except ImportError as e:
            raise OCRError(
                "Qwen2-VL dependencies missing. Run:\n"
                "  pip install -r requirements-qwen.txt"
            ) from e

        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        _qwen2vl_model = Qwen2VLForConditionalGeneration.from_pretrained(
            QWEN2VL_MODEL_NAME, torch_dtype=dtype, device_map="auto"
        )
        _qwen2vl_processor = AutoProcessor.from_pretrained(QWEN2VL_MODEL_NAME)

    return _qwen2vl_model, _qwen2vl_processor


# Prompt is deliberately strict: Qwen2-VL is a general vision-language model,
# not an OCR-only tool, so without constraints it tends to summarize or
# describe the document instead of transcribing it verbatim.
_QWEN2VL_OCR_PROMPT = (
    "This image contains a page from a Pakistani legal document written in Urdu. "
    "Transcribe ALL the Urdu text visible in the image exactly as written, "
    "in the original Urdu script. Do not translate it. Do not summarize it. "
    "Do not add commentary. Output ONLY the transcribed Urdu text, preserving "
    "line breaks where they appear in the image."
)


def _qwen2vl_ocr_image_bytes(image_bytes: bytes) -> Tuple[str, Optional[float]]:
    """
    Real OCR via Qwen2-VL running locally. Requires a GPU with the model
    dependencies installed (see requirements-qwen.txt). Confidence is returned
    as None since VLMs don't expose a single OCR-confidence score the way
    Vision API / Tesseract do.
    """
    import io as _io
    from PIL import Image

    model, processor = _load_qwen2vl()

    try:
        image = Image.open(_io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise OCRError(f"Could not open image for Qwen2-VL: {e}") from e

    conversation = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": _QWEN2VL_OCR_PROMPT},
            ],
        }
    ]
    text_prompt = processor.apply_chat_template(conversation, add_generation_prompt=True)
    inputs = processor(text=[text_prompt], images=[image], padding=True, return_tensors="pt")
    inputs = inputs.to(model.device)

    try:
        generated_ids = model.generate(**inputs, max_new_tokens=1024)
    except Exception as e:
        raise OCRError(f"Qwen2-VL generation failed: {e}") from e

    # Strip the input prompt tokens from the output, keeping only the new generation
    trimmed_ids = [
        out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        trimmed_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0]

    return output_text.strip(), None