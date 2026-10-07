# -*- coding: utf-8 -*-
"""
Contract.AI - Local Dev Server
=================================
Run this locally so your frontend (localhost:3000) can talk to the backend.

Start it with:
    uvicorn main:app --reload --port 8000

Then open http://localhost:8000/docs to test endpoints interactively.
"""
import os
import time
import asyncio

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import logging

from dotenv import load_dotenv
load_dotenv()  # must run BEFORE importing shared modules, since ocr_engine.py
                # reads OCR_ENGINE from os.environ at import time

from shared.ocr_engine import extract_text
from shared.models import OCRError, UnsupportedFileTypeError
from shared.preprocessing import preprocess
from shared.risk_detection import analyze_clause
from shared.explanation import build_clause_analysis
from shared.history_store import save_analysis_record, get_session_history

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("contract_ai")

# Set DEBUG=false in .env before a real demo/defense or any deployment.
# NFR-09 requires generic error messages with no internal details exposed
# to the client - but during development, seeing the real error (file
# paths, SDK exception text) is genuinely useful for debugging. DEBUG=true
# (the .env.example default) keeps that visible; DEBUG=false switches to
# clean, generic, NFR-09-compliant messages only.
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"

GENERIC_OCR_ERROR_MESSAGE = (
    "There was a problem processing your document. Please check the file "
    "and try again, or try a different file."
)

# FR-02: validate file size before processing. NFR-01 caps documents at
# 5 pages / 15 seconds - a typical scanned legal document page runs
# 1-2MB at reasonable quality, so 10MB gives comfortable headroom for a
# genuine 5-page scan without allowing arbitrarily large uploads that
# would blow past the NFR-01 time budget or just be abuse.
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "10"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# NFR-01: target ceiling for a <=5 page document under normal load. Not
# enforced (we don't abort a slow request) - logged as a warning so you
# have real evidence of whether this target is met, instead of guessing.
# Measured with real documents via scripts/benchmark_performance.py.
NFR01_TARGET_SECONDS = 15

# NFR-06: uploaded files must not be permanently stored, and must be
# deleted within 1 hour of processing completion. See
# shared/cloud_storage.py for the full implementation - it supports both
# a local-temp-folder backend (default, no cloud setup needed) and a real
# Firebase Storage backend (for deployment, matching your documented
# architecture). Both guarantee delete-after-processing, even on error.
from shared.cloud_storage import temporary_upload as _temporary_upload


def _user_facing_ocr_message(exc: Exception) -> str:
    """Returns the message shown to the client for an OCRError. Full
    technical detail always goes to the server log (see the OCRError
    except block below) regardless of this setting - this only controls
    what the HTTP response itself contains."""
    if DEBUG:
        return str(exc)
    return GENERIC_OCR_ERROR_MESSAGE


def _validate_file_size(file_bytes: bytes, filename: str):
    """FR-02: validate file size BEFORE initiating processing. Raises a
    clean 400 error immediately for empty or oversized files, rather than
    letting them flow into OCR/processing first."""
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail=f"'{filename}' is empty. Please upload a valid document.")
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{filename}' is {size_mb:.1f}MB, which exceeds the "
                f"{MAX_FILE_SIZE_MB}MB limit. Please upload a smaller file."
            ),
        )


async def _extract_text_async(file_bytes: bytes, filename: str):
    """
    NFR-02: extract_text() makes a BLOCKING synchronous network call to
    Vision API (or reads a scanned PDF page-by-page, or does CPU-bound
    char-n-gram TF-IDF work) - if called directly inside an `async def`
    route, it freezes that entire worker process for the whole call,
    capping true concurrency at your worker count regardless of how many
    requests arrive. Running it in a thread pool via run_in_executor lets
    one worker process juggle SEVERAL in-flight OCR calls at once, since
    while one thread is blocked waiting on Google's network response,
    other threads/requests in the same process can still proceed.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, extract_text, file_bytes, filename)


app = FastAPI(title="Contract.AI Backend (local dev)")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catches anything NOT already handled by a specific except block below.
    Matches NFR-09: log the real error server-side (visible in your uvicorn
    terminal) but never expose internal error details/stack traces to the
    client - just a clean, generic message.
    """
    logger.exception(f"Unhandled error on {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong processing your request. Please try again."},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ocr")
async def run_ocr(file: UploadFile = File(...)):
    """Extracts text from an uploaded document. Matches FR-01/FR-02/FR-03."""
    file_bytes = await file.read()
    _validate_file_size(file_bytes, file.filename)  # FR-02

    with _temporary_upload(file_bytes, file.filename):  # NFR-06
        try:
            result = await _extract_text_async(file_bytes, file.filename)
        except UnsupportedFileTypeError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except OCRError as e:
            logger.warning(f"OCR error during /ocr: {e}")
            raise HTTPException(status_code=422, detail=_user_facing_ocr_message(e))

    return {
        "full_text": result.full_text,
        "source": result.source,
        "page_count": result.page_count,
        "average_confidence": result.average_confidence,
        "warnings": result.warnings,
    }


class TermOut(BaseModel):
    text: str
    category: str    # financial_amount | penalty | termination | jurisdiction | date
    start: int
    end: int
    risk_level: str  # High Risk | Verify | Note - FR-06
    explanation: str  # plain-language Roman Urdu explanation - FR-07
    color: str        # red | yellow | blue - FR-08


class ClauseOut(BaseModel):
    urdu: str
    roman: str
    level: str
    category: Optional[str]
    explanation: str
    confidence_note: Optional[str]
    terms: List[TermOut] = []  # FR-05/FR-08 term-level highlights within this clause


class AnalyzeResponse(BaseModel):
    ocr_source: str
    ocr_warnings: List[str]
    clause_count: int
    risk_summary: dict          # clause-level counts: {high, verify, note}
    term_summary: dict          # FR-10 - risk TERM counts: {total, by_category}
    clauses: List[ClauseOut]
    disclaimer: str
    processing_time_seconds: float      # NFR-01 - total end-to-end time
    ocr_time_seconds: float             # NFR-01 - OCR stage only, usually the bottleneck
    risk_detection_time_seconds: float  # NFR-01 - risk detection + explanation stage only


DISCLAIMER = (
    "Ye tool sirf maloomati maqasid ke liye hai aur qanooni mashware ka "
    "mutabadil nahi hai. Kisi bhi ahem faislay se pehle qualified legal advisor "
    "se mashwara zaroor karein."
)  # matches FR-12. NFR-08: must be English/Roman Urdu only, no Urdu script.


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(file: UploadFile = File(...), session_id: str = Form(None)):
    """
    Full pipeline: OCR -> preprocess/segment -> per-clause risk detection
    -> explanation. Matches FR-09 (three-view result), FR-10 (summary
    counts), FR-12 (disclaimer). Timed throughout for NFR-01 visibility -
    see processing_time_seconds etc. in the response, and the NFR-01
    warning logged server-side if the 15s target is exceeded.

    session_id is optional - a random ID generated by the frontend
    (localStorage, no login/auth involved - see history_store.py's
    docstring for why this isn't the same thing as authentication). When
    provided, a SUMMARY of this analysis (not the file, not the full
    extracted text) is saved so /history can show it back for up to 1 hour.
    """
    request_start = time.monotonic()

    file_bytes = await file.read()
    _validate_file_size(file_bytes, file.filename)  # FR-02

    ocr_start = time.monotonic()
    with _temporary_upload(file_bytes, file.filename):  # NFR-06
        try:
            ocr_result = await _extract_text_async(file_bytes, file.filename)
        except UnsupportedFileTypeError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except OCRError as e:
            logger.warning(f"OCR error during /analyze: {e}")
            raise HTTPException(status_code=422, detail=_user_facing_ocr_message(e))
    ocr_time = time.monotonic() - ocr_start

    clauses = preprocess(ocr_result.full_text)
    if not clauses:
        raise HTTPException(status_code=422, detail="No usable clauses found in document.")

    analyzed = []
    summary = {"high": 0, "verify": 0, "note": 0}  # clause-level, matches FR-06 vocabulary exactly
    term_category_counts = {}  # FR-10 - counts by category, built up below

    risk_start = time.monotonic()
    for clause_text in clauses:
        risk_result = analyze_clause(clause_text)
        clause_analysis = build_clause_analysis(risk_result)
        summary[clause_analysis.risk_level] = summary.get(clause_analysis.risk_level, 0) + 1

        for t in clause_analysis.terms:
            term_category_counts[t.category] = term_category_counts.get(t.category, 0) + 1

        analyzed.append(ClauseOut(
            urdu=clause_analysis.urdu,
            roman=clause_analysis.roman,
            level=clause_analysis.risk_level,
            category=clause_analysis.risk_category,
            explanation=clause_analysis.explanation,
            confidence_note=clause_analysis.confidence_note,
            terms=[
                TermOut(text=t.text, category=t.category, start=t.start, end=t.end,
                        risk_level=t.risk_level, color=t.color, explanation=t.explanation)
                for t in clause_analysis.terms
            ],
        ))
    risk_time = time.monotonic() - risk_start

    total_terms = sum(term_category_counts.values())
    total_time = time.monotonic() - request_start

    if total_time > NFR01_TARGET_SECONDS:
        logger.warning(
            f"NFR-01 exceeded: '{file.filename}' took {total_time:.2f}s "
            f"(target: {NFR01_TARGET_SECONDS}s) - ocr={ocr_time:.2f}s, risk_detection={risk_time:.2f}s"
        )

    term_summary = {"total": total_terms, "by_category": term_category_counts}  # FR-10

    if session_id:
        try:
            save_analysis_record(session_id, len(analyzed), summary, term_summary)
        except Exception as e:
            # A history-saving failure must never break the actual analysis
            # the user is waiting on - log it and move on.
            logger.warning(f"Failed to save analysis history for session {session_id}: {e}")

    return AnalyzeResponse(
        ocr_source=ocr_result.source,
        ocr_warnings=ocr_result.warnings,
        clause_count=len(analyzed),
        risk_summary=summary,
        term_summary=term_summary,
        clauses=analyzed,
        disclaimer=DISCLAIMER,
        processing_time_seconds=round(total_time, 3),
        ocr_time_seconds=round(ocr_time, 3),
        risk_detection_time_seconds=round(risk_time, 3),
    )


@app.get("/history")
def get_history(session_id: str):
    """
    Returns this session's analysis summaries from the last hour only
    (NFR-06 layer 1 - see history_store.py's docstring for the full
    two-layer design). No file content, no full extracted text - just
    the same summary counts already shown in the AnalyzeResponse.
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")
    try:
        records = get_session_history(session_id)
    except Exception as e:
        logger.exception(f"Failed to fetch history for session {session_id}")
        raise HTTPException(status_code=500, detail="Could not load history right now.")
    return {"session_id": session_id, "records": records}

    return AnalyzeResponse(
        ocr_source=ocr_result.source,
        ocr_warnings=ocr_result.warnings,
        clause_count=len(analyzed),
        risk_summary=summary,
        term_summary={"total": total_terms, "by_category": term_category_counts},  # FR-10
        clauses=analyzed,
        disclaimer=DISCLAIMER,
        processing_time_seconds=round(total_time, 3),
        ocr_time_seconds=round(ocr_time, 3),
        risk_detection_time_seconds=round(risk_time, 3),
    )