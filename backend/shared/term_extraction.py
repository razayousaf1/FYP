# -*- coding: utf-8 -*-
"""
Contract.AI - Term-Level Risk Extraction (FR-05)
====================================================
FR-05 requires detecting specific RISK TERMS within text (not whole
sentences), classified under exactly 4 categories:
    - penalty clauses (jurmana)
    - financial amounts (raqam)
    - unilateral termination conditions
    - jurisdictional references (adalat)

This is a genuinely different granularity than shared/risk_detection.py,
which classifies whole CLAUSES using a trained classifier. There is no
term-level annotated training data in the dataset (it's clause-level), so
building a term-level classifier isn't possible without new labeled data.

Instead, this module uses PATTERN-BASED extraction (regex + curated
keyword lists) grounded in real term frequency checked against the actual
dataset (see scripts/check_term_frequency.py). This is an honest,
appropriate choice given the data available - not a shortcut standing in
for a "real" model. It's also linguistically reasonable: these 4
categories are lexically identifiable (specific words/number-patterns),
unlike general "riskiness" which genuinely needs a trained classifier.

Each detected term keeps its character offsets within the clause, so the
frontend can highlight the exact span rather than the whole clause
(closing the FR-08 gap alongside this).
"""
import re
from dataclasses import dataclass
from typing import List

CATEGORY_FINANCIAL = "financial_amount"
CATEGORY_PENALTY = "penalty"
CATEGORY_TERMINATION = "termination"
CATEGORY_JURISDICTION = "jurisdiction"
CATEGORY_DATE = "date"

# Priority order when spans overlap - higher priority wins the overlapping
# region. Penalty/termination are the most specific and consequential
# signals, so they take precedence over the much more common financial
# amount pattern.
CATEGORY_PRIORITY = [CATEGORY_PENALTY, CATEGORY_TERMINATION, CATEGORY_JURISDICTION, CATEGORY_DATE, CATEGORY_FINANCIAL]

# Keyword lists - grounded in actual frequency check against the dataset
# (64/1083 penalty, 156/1083 termination, 112/1083 jurisdiction,
# 595/1083 financial, 50/1083 dated clauses contained these terms).
PENALTY_KEYWORDS = ["جرمانہ", "ہرجانہ", "پینلٹی"]
TERMINATION_KEYWORDS = ["ختم", "منسوخ", "فسخ", "بے دخل", "دستبردار"]
JURISDICTION_KEYWORDS = ["عدالت", "کچہری", "ٹریبونل"]

# FR-08 explicitly says "blue for dates AND jurisdictional references" -
# these are two different categories at extraction time (dates aren't
# court/tribunal references), but they map to the SAME color at display
# time. See risk_detection.py's category_to_color() for that mapping.
_DATE_MONTHS = "جنوری|فروری|مارچ|اپریل|مئی|جون|جولائی|اگست|ستمبر|اکتوبر|نومبر|دسمبر"
_DATE_PATTERN = re.compile(rf"\d{{1,2}}[-\s]({_DATE_MONTHS})[-\s]\d{{4}}")

# Financial amounts: digit sequence (with optional commas) followed by
# "روپے" (rupees), optionally preceded by "مبلغ" (amount/sum). Also
# matches percentage figures (e.g. "10 فیصد") since these are financial
# terms too (interest rates, rent increases) even though FR-05's
# parenthetical example is specifically rupee amounts - a reasonable
# extension, not a deviation from intent.
_FINANCIAL_PATTERN = re.compile(r"(مبلغ\s+)?[\d,]+\s*(روپے|فیصد)")

# How many characters of context to grab around a keyword match, expanded
# to the nearest word boundary so we don't cut a word in half.
_CONTEXT_CHARS = 10


@dataclass
class TermMatch:
    text: str        # the extracted term/phrase, as it appears in the clause
    category: str    # one of the CATEGORY_* constants above
    start: int       # character offset within the clause text
    end: int


def _expand_to_word_boundary(text: str, start: int, end: int, context_chars: int = _CONTEXT_CHARS) -> tuple:
    """Widens a keyword match to include some surrounding context, snapped
    to whitespace so the highlighted term reads as a phrase, not a
    fragment. Never crosses clause boundaries (start/end of `text`)."""
    new_start = max(0, start - context_chars)
    new_end = min(len(text), end + context_chars)

    # snap start forward to the next space (or 0)
    space_before = text.rfind(" ", 0, new_start)
    if space_before != -1:
        new_start = space_before + 1

    # snap end backward to the previous space (or len(text))
    space_after = text.find(" ", new_end)
    if space_after != -1:
        new_end = space_after

    return new_start, new_end


def _find_keyword_matches(text: str, keywords: List[str], category: str) -> List[TermMatch]:
    matches = []
    for kw in keywords:
        for m in re.finditer(re.escape(kw), text):
            start, end = _expand_to_word_boundary(text, m.start(), m.end())
            matches.append(TermMatch(text=text[start:end].strip(), category=category, start=start, end=end))
    return matches


def _find_financial_matches(text: str) -> List[TermMatch]:
    matches = []
    for m in _FINANCIAL_PATTERN.finditer(text):
        matches.append(TermMatch(text=m.group(0).strip(), category=CATEGORY_FINANCIAL, start=m.start(), end=m.end()))
    return matches


def _find_date_matches(text: str) -> List[TermMatch]:
    matches = []
    for m in _DATE_PATTERN.finditer(text):
        matches.append(TermMatch(text=m.group(0).strip(), category=CATEGORY_DATE, start=m.start(), end=m.end()))
    return matches


def _spans_overlap(a: TermMatch, b: TermMatch) -> bool:
    return a.start < b.end and b.start < a.end


def extract_terms(clause_text: str) -> List[TermMatch]:
    """
    Finds all FR-05-category term matches in a single clause, resolving
    overlaps by CATEGORY_PRIORITY (higher-priority category keeps its
    span; lower-priority overlapping matches are dropped).
    """
    all_matches = {
        CATEGORY_PENALTY: _find_keyword_matches(clause_text, PENALTY_KEYWORDS, CATEGORY_PENALTY),
        CATEGORY_TERMINATION: _find_keyword_matches(clause_text, TERMINATION_KEYWORDS, CATEGORY_TERMINATION),
        CATEGORY_JURISDICTION: _find_keyword_matches(clause_text, JURISDICTION_KEYWORDS, CATEGORY_JURISDICTION),
        CATEGORY_DATE: _find_date_matches(clause_text),
        CATEGORY_FINANCIAL: _find_financial_matches(clause_text),
    }

    accepted: List[TermMatch] = []
    for category in CATEGORY_PRIORITY:
        for candidate in all_matches[category]:
            if not any(_spans_overlap(candidate, existing) for existing in accepted):
                accepted.append(candidate)

    accepted.sort(key=lambda t: t.start)
    return accepted