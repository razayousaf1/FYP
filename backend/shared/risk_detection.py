# -*- coding: utf-8 -*-
"""
Contract.AI - Risk Detection
===============================
Loads the artifacts trained by scripts/train_risk_model.py and predicts,
for a single Urdu clause:
  - risk_label: Warning / Safe / High Risk -> from the TRAINED classifier
  - risk_category + explanation seed: from NEAREST-NEIGHBOR RETRIEVAL
    against the dataset (not a classifier - see train_risk_model.py for
    why: 112 categories, many with only 1-2 examples, too sparse to
    classify reliably).

KNOWN LIMITATION (be upfront about this in your defense):
    Group-aware evaluation gives macro F1 ~0.71 (just under the NFR-04
    target of 0.75), and a stricter test using only the 32 real
    hand-collected rows (never templated) gives F1 ~0.36. The gap shows
    the model doesn't yet generalize well to real-world phrasing outside
    the synthetic templates it was mostly trained on. See
    models_trained/training_metrics.json for exact numbers. The fix isn't
    more synthetic rows - it's more REAL collected documents.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Optional, List

import joblib
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from shared.term_extraction import extract_terms, CATEGORY_FINANCIAL, CATEGORY_DATE, CATEGORY_JURISDICTION

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models_trained")

_vectorizer = None
_label_classifier = None
_retrieval_matrix = None
_retrieval_metadata = None

# Below this cosine-similarity score, the retrieval match is too weak to
# trust the retrieved category/explanation - surfaced as low_confidence
# rather than silently returning a poor match.
MIN_RETRIEVAL_SIMILARITY = 0.15


@dataclass
class HighlightedTerm:
    """A single FR-05 risk term found within a clause, with its FR-06 level and FR-08 color."""
    text: str
    category: str      # financial_amount | penalty | termination | jurisdiction | date
    start: int          # character offset within the clause text
    end: int
    risk_level: str      # High Risk | Verify | Note - FR-06, inherited from the clause's
                          # trained-classifier prediction (no term-level training data exists
                          # to model this independently per term - documented here)
    color: str          # red | yellow | blue - FR-08, see category_to_color() below


@dataclass
class RiskResult:
    clause_text: str
    risk_label: str                    # from trained classifier
    risk_label_confidence: float       # classifier's own probability for the predicted class
    risk_category: Optional[str]       # from nearest-neighbor retrieval
    matched_reference_clause: Optional[str]
    matched_explanation: Optional[str]
    retrieval_similarity: Optional[float]
    low_confidence: bool               # True if retrieval match was weak
    terms: List[HighlightedTerm] = field(default_factory=list)  # FR-05/FR-08


def category_to_color(category: str, clause_risk_label: str) -> str:
    """
    Implements FR-08's color rule exactly: "red for high risk, yellow for
    financial amounts, blue for dates and jurisdictional references".

    FR-08's own wording mixes a SEVERITY-based rule (red = high risk) with
    CATEGORY-based rules (yellow = financial, blue = date/jurisdiction) in
    one 3-color system - it doesn't specify what happens when a term is
    BOTH high-risk AND e.g. a financial amount. This function's priority
    order (severity first, then category) is a judgment call, not
    something the spec resolves - documented here rather than hidden.
    """
    if clause_risk_label == "High Risk":
        return "red"
    if category == CATEGORY_FINANCIAL:
        return "yellow"
    if category in (CATEGORY_DATE, CATEGORY_JURISDICTION):
        return "blue"
    # penalty / termination categories in a non-high-risk clause: no color
    # is specified by FR-08 for this case. Defaulting to yellow ("worth a
    # second look") rather than inventing an unspecified 4th color.
    return "yellow"


# Same High Risk/Verify/Note translation used in explanation.py's
# _LEVEL_MAP - kept local here too (not imported) to avoid a circular
# import, since explanation.py imports FROM this module.
_LEVEL_DISPLAY_NAMES = {"High Risk": "High Risk", "Warning": "Verify", "Safe": "Note"}

def _load_artifacts():
    global _vectorizer, _label_classifier, _retrieval_matrix, _retrieval_metadata
    if _vectorizer is None:
        required = [
            "vectorizer.joblib", "risk_label_classifier.joblib",
            "retrieval_matrix.joblib", "retrieval_metadata.json",
        ]
        missing = [f for f in required if not os.path.exists(os.path.join(MODELS_DIR, f))]
        if missing:
            raise FileNotFoundError(
                f"Missing model artifacts: {missing}. "
                f"Run 'python scripts/train_risk_model.py' first."
            )
        _vectorizer = joblib.load(os.path.join(MODELS_DIR, "vectorizer.joblib"))
        _label_classifier = joblib.load(os.path.join(MODELS_DIR, "risk_label_classifier.joblib"))
        _retrieval_matrix = joblib.load(os.path.join(MODELS_DIR, "retrieval_matrix.joblib"))
        with open(os.path.join(MODELS_DIR, "retrieval_metadata.json"), "r", encoding="utf-8") as f:
            _retrieval_metadata = json.load(f)
    return _vectorizer, _label_classifier, _retrieval_matrix, _retrieval_metadata


def analyze_clause(clause_text: str) -> RiskResult:
    """
    Runs both stages on a single clause: trained classifier for risk_label,
    nearest-neighbor retrieval for risk_category + explanation.
    """
    vectorizer, classifier, retrieval_matrix, metadata = _load_artifacts()

    vec = vectorizer.transform([clause_text])

    # --- Stage 1: trained classifier ---
    pred_label = classifier.predict(vec)[0]
    proba = classifier.predict_proba(vec)[0]
    class_index = list(classifier.classes_).index(pred_label)
    confidence = float(proba[class_index])

    # --- Stage 2: nearest-neighbor retrieval ---
    similarities = cosine_similarity(vec, retrieval_matrix)[0]
    best_idx = int(np.argmax(similarities))
    best_score = float(similarities[best_idx])
    best_match = metadata[best_idx]

    low_confidence = best_score < MIN_RETRIEVAL_SIMILARITY

    # --- Stage 3: FR-05 term extraction + FR-06 level + FR-08 color ---
    raw_terms = extract_terms(clause_text)
    terms = [
        HighlightedTerm(
            text=t.text, category=t.category, start=t.start, end=t.end,
            risk_level=_LEVEL_DISPLAY_NAMES.get(pred_label, pred_label),
            color=category_to_color(t.category, pred_label),
        )
        for t in raw_terms
    ]

    return RiskResult(
        clause_text=clause_text,
        risk_label=pred_label,
        risk_label_confidence=confidence,
        risk_category=None if low_confidence else best_match["risk_category"],
        matched_reference_clause=best_match["urdu_text"],
        matched_explanation=None if low_confidence else best_match["explanation"],
        retrieval_similarity=best_score,
        low_confidence=low_confidence,
        terms=terms,
    )
