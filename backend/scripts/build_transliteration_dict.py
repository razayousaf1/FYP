# -*- coding: utf-8 -*-
"""
Builds shared/transliteration_dict.json from the dataset's Clause Text (Urdu)
and Clause Text (Roman Urdu) columns, via positional word-alignment: for
clause pairs where the Urdu and Roman versions have the same word count,
zip them together word-by-word. Not every row aligns cleanly (word counts
differ, transliteration isn't always 1:1), so this only uses the subset
that does - still yields hundreds of high-quality entries.

Run with: python scripts/build_transliteration_dict.py
Re-run this any time the dataset changes to regenerate the dictionary.
"""
import json
import os
import re
from collections import Counter, defaultdict

import openpyxl

DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ContractAI_Dataset_EXPANDED.xlsx")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "transliteration_dict.json")


def _urdu_tokens(s):
    s = re.sub(r"[۔،؟!.,]", "", s)
    return s.split()


def _roman_tokens(s):
    s = re.sub(r"[.,!?]", "", s)
    return s.split()


def main():
    wb = openpyxl.load_workbook(DATASET_PATH, data_only=True)
    ws = wb["Dataset"]
    rows = list(ws.iter_rows(min_row=4, values_only=True))
    pairs = [(r[3], r[4]) for r in rows if r[3] and r[4]]

    word_map = defaultdict(Counter)
    matched, mismatched = 0, 0
    for urdu, roman in pairs:
        ut, rt = _urdu_tokens(urdu), _roman_tokens(roman)
        if len(ut) == len(rt) and ut:
            matched += 1
            for u, r in zip(ut, rt):
                word_map[u][r.lower()] += 1
        else:
            mismatched += 1

    final_dict = {u: counter.most_common(1)[0][0] for u, counter in word_map.items()}

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(final_dict, f, ensure_ascii=False, indent=1)

    print(f"Processed {len(pairs)} clause pairs ({matched} aligned, {mismatched} skipped - word count mismatch).")
    print(f"Saved {len(final_dict)} dictionary entries to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
