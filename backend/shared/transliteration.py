# -*- coding: utf-8 -*-
"""
Contract.AI - Urdu -> Roman Urdu Transliteration
===================================================
No model training involved - this is a deterministic lookup, not a
learned model.

Two-tier approach:
  1. Word dictionary lookup (transliteration_dict.json) - bootstrapped
     automatically from your dataset's Clause Text (Urdu) / Clause Text
     (Roman Urdu) columns via positional word-alignment (see
     scripts/build_transliteration_dict.py). Covers common legal/contract
     vocabulary with human-quality transliterations.
  2. Character-level fallback for any word not in the dictionary. This is
     approximate - Urdu doesn't write short vowels, so a pure character
     map can't always guess the right pronunciation (e.g. "کرایہ" needs
     to become "kiraya", not "kraya"). Good enough to keep the pipeline
     working end-to-end on unfamiliar words; not linguistically perfect.
     Widening the dictionary (tier 1) is the real fix, not the fallback.
"""
import json
import os
import re
from typing import Dict

_DICT_PATH = os.path.join(os.path.dirname(__file__), "transliteration_dict.json")
_word_dict: Dict[str, str] = None  # loaded lazily


def _load_dict() -> Dict[str, str]:
    global _word_dict
    if _word_dict is None:
        if os.path.exists(_DICT_PATH):
            with open(_DICT_PATH, "r", encoding="utf-8") as f:
                _word_dict = json.load(f)
        else:
            _word_dict = {}
    return _word_dict


# Character-level fallback map. Isolated-form approximations - not
# phonetically perfect, but functional for words outside the dictionary.
_CHAR_MAP = {
    "ا": "a", "آ": "aa", "ب": "b", "پ": "p", "ت": "t", "ٹ": "t", "ث": "s",
    "ج": "j", "چ": "ch", "ح": "h", "خ": "kh", "د": "d", "ڈ": "d", "ذ": "z",
    "ر": "r", "ڑ": "r", "ز": "z", "ژ": "zh", "س": "s", "ش": "sh", "ص": "s",
    "ض": "z", "ط": "t", "ظ": "z", "ع": "a", "غ": "gh", "ف": "f", "ق": "q",
    "ک": "k", "گ": "g", "ل": "l", "م": "m", "ن": "n", "ں": "n", "و": "o",
    "ہ": "h", "ھ": "h", "ء": "", "ی": "i", "ے": "e", "أ": "a", "ؤ": "o",
    "ئ": "i", "۔": ".", "،": ",", "؟": "?",
}


def _transliterate_word_charwise(word: str) -> str:
    return "".join(_CHAR_MAP.get(ch, ch) for ch in word)


def transliterate_word(word: str) -> str:
    """Transliterates a single Urdu word: dictionary first, char-map fallback."""
    word_dict = _load_dict()
    clean = re.sub(r"[۔،؟!.,]", "", word)
    if clean in word_dict:
        return word_dict[clean]
    return _transliterate_word_charwise(word)


def transliterate(text: str) -> str:
    """
    Transliterates a full Urdu string (clause or paragraph) word by word,
    preserving whitespace and punctuation structure.
    """
    if not text:
        return ""

    words = text.split(" ")
    return " ".join(transliterate_word(w) if w.strip() else w for w in words)


def dictionary_coverage(text: str) -> float:
    """
    Returns the fraction (0.0-1.0) of words in `text` that were found in
    the dictionary (tier 1) rather than falling back to the character map
    (tier 2). Useful for surfacing transliteration confidence to the
    frontend - low coverage means more approximate output.
    """
    word_dict = _load_dict()
    words = [re.sub(r"[۔،؟!.,]", "", w) for w in text.split(" ") if w.strip()]
    if not words:
        return 1.0
    found = sum(1 for w in words if w in word_dict)
    return found / len(words)
