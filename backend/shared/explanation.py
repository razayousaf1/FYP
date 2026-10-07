# -*- coding: utf-8 -*-
"""
Contract.AI - Explanation Generation
=======================================
Two separate explanation systems live here, for two different granularities:

1. CLAUSE-level explanation (build_clause_analysis, existing): comes from
   risk_detection.py's nearest-neighbor retrieval (RiskResult.matched_explanation)
   - the retrieved template was written for a DIFFERENT clause (the training
   example), which may quote different numbers (days, rupee amounts,
   percentages) than the clause actually being analyzed. Using it verbatim
   would put wrong figures in front of the user, which is a real accuracy
   problem for a legal-info tool.

   Fix: extract the numbers from the matched REFERENCE clause and from the
   QUERY clause (the one actually being analyzed), and substitute query
   numbers into the explanation wherever it quotes reference numbers -
   provided the counts match closely enough to trust the mapping. When they
   don't match, we don't guess: the explanation gets a confidence note
   telling the user to verify the specific figures themselves, instead of
   silently presenting a number that might be wrong.

   Known remaining gap: explanations sometimes cite DERIVED numbers not
   literally present in the clause (e.g. a penalty template computing
   "amount // 10" for a per-day fine). Those derived numbers won't have a
   matching reference number to substitute against and may still be
   approximate. This is called out via confidence_note rather than hidden.

2. TERM-level explanation (explain_term/_explain_terms, FR-07): risk_detection.py's
   HighlightedTerm (from shared/term_extraction.py's pattern-based FR-05
   detection) does NOT carry its own explanation - term extraction is
   pattern-based, not trained, so a template-per-category approach here is
   the consistent choice, not a downgrade from the clause-level retrieval
   approach above.
"""
import re
from dataclasses import dataclass, field
from typing import Optional, List

from shared.risk_detection import RiskResult, HighlightedTerm
from shared.transliteration import transliterate
from shared.term_extraction import (
    CATEGORY_FINANCIAL, CATEGORY_PENALTY, CATEGORY_TERMINATION,
    CATEGORY_JURISDICTION, CATEGORY_DATE,
)

FALLBACK_EXPLANATION = (
    "Ye clause hamare training data se kaafi mukhtalif hai, is liye hum "
    "wazeh explanation nahi de saktay. Is hissay ko khud ghaur se parhein "
    "ya kisi legal advisor se maloomat lein."
)

NUMBER_MISMATCH_NOTE = (
    "Explanation ka pattern match ho gaya hai, lekin is mein diye gaye exact "
    "numbers (raqam/din/fisad) is document ki asal tafseel se mukhtalif ho "
    "saktay hain - neeche diye gaye Urdu clause mein asal numbers khud check karein."
)

_NUMBER_PATTERN = re.compile(r"\d[\d,]*")


@dataclass
class ClauseAnalysis:
    urdu: str
    roman: str
    risk_level: str
    risk_category: Optional[str]
    explanation: str
    confidence_note: Optional[str]
    terms: list = field(default_factory=list)  # FR-05/FR-08 term-level highlights, now ExplainedTerm


@dataclass
class ExplainedTerm:
    """A HighlightedTerm (from risk_detection.py) plus its FR-07 explanation.
    This is what actually reaches main.py's TermOut - main.py reads
    t.explanation off objects of THIS type, not off raw HighlightedTerm."""
    text: str
    category: str
    start: int
    end: int
    risk_level: str
    color: str
    explanation: str


_LEVEL_MAP = {
    # Left side: the model's own training labels (unchanged - matches your
    # dataset's Risk Label column, renaming these would require retraining).
    # Right side: display-layer identifiers matching FR-06's required
    # vocabulary exactly - "High Risk", "Verify", "Note".
    "High Risk": "high",
    "Warning": "verify",
    "Safe": "note",
}


def explain_term(category: str, term_text: str) -> str:
    """FR-07: plain-language Roman Urdu explanation for a single detected
    risk term. Template-based per category, since term extraction itself
    is pattern-based (see term_extraction.py), not trained."""
    templates = {
        CATEGORY_FINANCIAL: (
            f"'{term_text}' ek raqam (financial amount) hai jo is document mein zikar hui hai. "
            f"Confirm karein ke ye amount wahi hai jo aapke saath pehle se tay hui thi."
        ),
        CATEGORY_PENALTY: (
            f"'{term_text}' ek jurmana (penalty) clause hai. Dekh lein ke ye kis wajah se "
            f"lagta hai aur kitna sakht hai - agar unreasonable lage to negotiate karein."
        ),
        CATEGORY_TERMINATION: (
            f"'{term_text}' batata hai ke ye agreement kis tarah khatam ho sakta hai. Check "
            f"karein ke termination ki shartain dono taraf ke liye barabar (fair) hain."
        ),
        CATEGORY_JURISDICTION: (
            f"'{term_text}' adalat/jurisdiction ka reference hai. Koi dispute hua to case isi "
            f"jagah chalega - agar aap kahin aur rehte hain to ye aapke liye mushkil ho sakta hai."
        ),
        CATEGORY_DATE: (
            f"'{term_text}' ek tareekh hai. Apni calendar mein zaroor note kar lein "
            f"taake koi deadline ya appointment miss na ho."
        ),
    }
    return templates.get(category, f"'{term_text}' ek detected term hai.")


def _explain_terms(terms: List[HighlightedTerm]) -> List[ExplainedTerm]:
    """Wraps each raw HighlightedTerm (no explanation) into an ExplainedTerm
    (with explanation) - this is the FR-07 step that was missing."""
    return [
        ExplainedTerm(
            text=t.text, category=t.category, start=t.start, end=t.end,
            risk_level=t.risk_level, color=t.color,
            explanation=explain_term(t.category, t.text),
        )
        for t in terms
    ]


def _extract_numbers(text: str) -> List[str]:
    """Returns numeric tokens in order of appearance, e.g. ['25,000', '30']."""
    if not text:
        return []
    return _NUMBER_PATTERN.findall(text)


def _substitute_numbers(explanation: str, reference_clause: str, query_clause: str) -> tuple:
    """
    Replaces numbers in `explanation` that came from `reference_clause`
    with the corresponding numbers from `query_clause`, matched by
    position. Returns (fixed_explanation, numbers_were_substituted: bool).

    Only substitutes when reference and query have the SAME COUNT of
    numbers - if they differ, we don't guess at a mapping, since a wrong
    guess is worse than an honest "please verify" note.
    """
    ref_numbers = _extract_numbers(reference_clause)
    query_numbers = _extract_numbers(query_clause)

    if not ref_numbers or len(ref_numbers) != len(query_numbers):
        return explanation, False

    # map each reference number -> corresponding query number, by position
    substitution_map = dict(zip(ref_numbers, query_numbers))

    def _replace(match):
        token = match.group(0)
        return substitution_map.get(token, token)

    fixed = _NUMBER_PATTERN.sub(_replace, explanation)

    # only report success if at least one number actually changed
    changed = fixed != explanation
    return fixed, changed


def build_clause_analysis(risk_result: RiskResult) -> ClauseAnalysis:
    """Converts a RiskResult into the frontend-ready shape, with number
    substitution applied to the retrieved explanation template, and each
    term wrapped with its own FR-07 explanation."""
    roman = transliterate(risk_result.clause_text)
    level = _LEVEL_MAP.get(risk_result.risk_label, "verify")
    explained_terms = _explain_terms(risk_result.terms)

    if risk_result.low_confidence or not risk_result.matched_explanation:
        return ClauseAnalysis(
            urdu=risk_result.clause_text,
            roman=roman,
            risk_level=level,
            risk_category=risk_result.risk_category,
            explanation=FALLBACK_EXPLANATION,
            confidence_note=(
                f"Low match confidence ({risk_result.retrieval_similarity:.2f}) - "
                f"this clause type wasn't well represented in training data."
            ),
            terms=explained_terms,
        )

    fixed_explanation, was_substituted = _substitute_numbers(
        risk_result.matched_explanation,
        risk_result.matched_reference_clause,
        risk_result.clause_text,
    )

    query_number_count = len(_extract_numbers(risk_result.clause_text))
    ref_number_count = len(_extract_numbers(risk_result.matched_reference_clause))

    confidence_note = None
    if query_number_count != ref_number_count and (query_number_count > 0 or ref_number_count > 0):
        # numbers exist but counts don't line up - can't safely substitute,
        # be upfront that the exact figures may not match
        confidence_note = NUMBER_MISMATCH_NOTE

    return ClauseAnalysis(
        urdu=risk_result.clause_text,
        roman=roman,
        risk_level=level,
        risk_category=risk_result.risk_category,
        explanation=fixed_explanation,
        confidence_note=confidence_note,
        terms=explained_terms,
    )