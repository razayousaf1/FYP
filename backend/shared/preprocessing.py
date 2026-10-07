# -*- coding: utf-8 -*-
"""
Contract.AI - Text Preprocessing
==================================
Cleans and segments raw OCR output before it goes to transliteration and
risk detection. No model here - this is deterministic text processing.
"""
import re
import unicodedata
from typing import List

# Urdu sentence-ending punctuation. ۔ (U+06D4) is the standard Urdu full stop;
# Western punctuation sometimes appears too in mixed-typed documents.
CLAUSE_TERMINATORS = ["۔", "؟", "!", "."]

MIN_CLAUSE_LENGTH = 8  # characters - shorter fragments are usually OCR noise, not real clauses


def normalize_text(text: str) -> str:
    """
    Cleans raw OCR/extraction output:
      - NFKC Unicode normalization (fixes Arabic Presentation Forms glyphs
        that some PDF generators / OCR engines produce - see ocr_engine.py's
        _normalize_urdu_text for background on this issue)
      - Collapses repeated whitespace
      - Strips leading/trailing whitespace per line
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def segment_clauses(text: str) -> List[str]:
    """
    Splits normalized text into individual clauses for per-clause risk
    detection. Splits on Urdu/Western sentence terminators, then filters
    out fragments too short to be a real clause (usually OCR noise or
    stray headers/page numbers).
    """
    if not text:
        return []

    pattern = "(" + "|".join(re.escape(t) for t in CLAUSE_TERMINATORS) + ")"
    parts = re.split(pattern, text)

    clauses = []
    buffer = ""
    for part in parts:
        buffer += part
        if part in CLAUSE_TERMINATORS:
            clause = buffer.strip()
            if len(clause) >= MIN_CLAUSE_LENGTH:
                clauses.append(clause)
            buffer = ""

    trailing = buffer.strip()
    if len(trailing) >= MIN_CLAUSE_LENGTH:
        clauses.append(trailing)

    return clauses


def preprocess(raw_text: str) -> List[str]:
    """Convenience wrapper: normalize then segment in one call."""
    normalized = normalize_text(raw_text)
    return segment_clauses(normalized)
