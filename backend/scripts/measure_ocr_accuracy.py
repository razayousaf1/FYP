# -*- coding: utf-8 -*-
"""
NFR-03: OCR character recognition accuracy measurement.

I (Claude) can't run this myself - it needs real scanned/photographed
documents with known-correct Urdu text, which only you can supply.

Setup:
    Create a folder backend/data/ocr_ground_truth/ containing PAIRS of files:
        rent_agreement_1.jpg   <- the actual scanned/photographed document
        rent_agreement_1.txt   <- the EXACT correct Urdu text, typed by hand
        affidavit_2.png
        affidavit_2.txt
        ... etc

    Every image needs a matching .txt file with the SAME name (before the
    extension). The .txt file must be UTF-8 and contain exactly what the
    document actually says - this is the ground truth everything else is
    measured against, so it needs to be correct, not approximate.

Usage:
    Make sure OCR_ENGINE=vision (or qwen2vl) in your .env - NOT mock, since
    mock always returns the same fixed text and would give a meaningless
    100% or 0% depending on what you compare it to.

    python3 scripts/measure_ocr_accuracy.py

What it measures:
    Character Error Rate (CER) via Levenshtein edit distance between the
    real OCR output and your ground truth, after normalizing whitespace
    (NFR-03 is about CHARACTER recognition, not layout/spacing, so trivial
    whitespace differences shouldn't be counted as errors). Reports
    per-document and overall average accuracy against the 85% target.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()  # must run BEFORE importing shared.ocr_engine, which reads
                # OCR_ENGINE/GOOGLE_APPLICATION_CREDENTIALS from os.environ
                # at import time - same fix main.py needed earlier.

from shared.ocr_engine import extract_text
from shared.preprocessing import normalize_text

GROUND_TRUTH_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ocr_ground_truth"
)
NFR03_TARGET = 0.85
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}


def levenshtein_distance(a: str, b: str) -> int:
    """Standard DP edit distance - no external dependency needed."""
    if len(a) < len(b):
        a, b = b, a
    if len(b) == 0:
        return len(a)

    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a):
        current_row = [i + 1]
        for j, char_b in enumerate(b):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (char_a != char_b)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def normalize_arabic_to_urdu(text: str) -> str:
    """
    Arabic and Urdu share the same base script, but use DIFFERENT Unicode
    codepoints for some letters that look nearly identical to a human
    reader. Vision API correctly outputs Urdu-specific codepoints (since
    language_hints=['ur'] is set - see ocr_engine.py), but text
    copy-pasted from another source (a different OCR tool, a document
    typed on an Arabic keyboard layout, etc.) may use Arabic-variant
    codepoints for the same visual letter. Without this normalization,
    exact character comparison would count these as errors even though
    the text is correct - this maps the most common Arabic variants to
    their Urdu-specific equivalents before comparing.
    """
    mapping = {
        "\u0643": "\u06A9",  # Arabic Kaf -> Urdu Keheh (ك -> ک)
        "\u064A": "\u06CC",  # Arabic Yeh -> Urdu Yeh (ي -> ی)
        "\u0647": "\u06C1",  # Arabic Heh -> Urdu Heh Goal (ه -> ہ)
    }
    for arabic_ch, urdu_ch in mapping.items():
        text = text.replace(arabic_ch, urdu_ch)
    return text


def character_accuracy(extracted: str, ground_truth: str) -> float:
    """
    Returns accuracy as a fraction (0.0-1.0). Both texts are normalized
    (NFKC + whitespace collapse + Arabic/Urdu character variants) before
    comparing, so this measures actual character recognition, not
    incidental spacing/line-break/script-variant differences.
    """
    extracted_norm = normalize_arabic_to_urdu(normalize_text(extracted).replace("\n", " "))
    ground_truth_norm = normalize_arabic_to_urdu(normalize_text(ground_truth).replace("\n", " "))

    if not ground_truth_norm:
        return 0.0

    distance = levenshtein_distance(extracted_norm, ground_truth_norm)
    cer = distance / len(ground_truth_norm)
    return max(0.0, 1.0 - cer)  # clamp - a very bad OCR result shouldn't go negative


def find_pairs():
    """Finds every (image, ground_truth.txt) pair in GROUND_TRUTH_DIR."""
    if not os.path.isdir(GROUND_TRUTH_DIR):
        return []

    pairs = []
    for filename in sorted(os.listdir(GROUND_TRUTH_DIR)):
        name, ext = os.path.splitext(filename)
        if ext.lower() not in IMAGE_EXTENSIONS:
            continue
        txt_path = os.path.join(GROUND_TRUTH_DIR, name + ".txt")
        if os.path.exists(txt_path):
            pairs.append((os.path.join(GROUND_TRUTH_DIR, filename), txt_path))
    return pairs


def main():
    pairs = find_pairs()

    if not pairs:
        print(f"No image+ground-truth pairs found in {GROUND_TRUTH_DIR}")
        print("Create that folder and add paired files - see this script's docstring.")
        sys.exit(1)

    print(f"Found {len(pairs)} document(s) to test.\n")
    print("=" * 70)
    print(f"NFR-03: OCR character accuracy (target: >= {NFR03_TARGET:.0%})")
    print("=" * 70)

    accuracies = []
    for image_path, txt_path in pairs:
        filename = os.path.basename(image_path)
        with open(txt_path, "r", encoding="utf-8") as f:
            ground_truth = f.read()
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        try:
            result = extract_text(image_bytes, filename)
        except Exception as e:
            print(f"{filename}: FAILED to extract text - {e}")
            continue

        accuracy = character_accuracy(result.full_text, ground_truth)
        accuracies.append(accuracy)
        verdict = "PASS" if accuracy >= NFR03_TARGET else "FAIL"
        print(f"{filename:35s} accuracy: {accuracy:.1%}  [{verdict}]  (source: {result.source})")

        # DIAGNOSTIC: when accuracy is unexpectedly low, print both texts
        # side by side so the actual cause (wrong OCR, ground truth typo,
        # reversed text order, etc.) can be seen instead of guessed at.
        if accuracy < 0.85:
            print(f"  --- OCR extracted (what Vision API read) ---")
            print(f"  {result.full_text!r}")
            print(f"  --- Ground truth (what you typed) ---")
            print(f"  {ground_truth!r}")
            print()

    if not accuracies:
        print("\nNo documents were successfully measured.")
        sys.exit(1)

    overall = sum(accuracies) / len(accuracies)
    print()
    print("=" * 70)
    print(f"Overall average accuracy: {overall:.1%}  across {len(accuracies)} document(s)")
    verdict = "PASS" if overall >= NFR03_TARGET else "FAIL"
    print(f"NFR-03 verdict: {verdict} (target: >= {NFR03_TARGET:.0%})")
    print("=" * 70)


if __name__ == "__main__":
    main()