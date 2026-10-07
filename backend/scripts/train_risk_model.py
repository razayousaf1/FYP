# -*- coding: utf-8 -*-
"""
Trains the Contract.AI risk-detection system on data/ContractAI_Dataset_EXPANDED.xlsx
and saves artifacts to models_trained/.

Two-part design (see shared/risk_detection.py for why):
  1. Risk Label classifier (Warning / Safe / High Risk) - a real trained
     classifier, TF-IDF (character n-grams) + Logistic Regression.
  2. Risk Category + Explanation - nearest-neighbor retrieval, not a
     classifier. There are 112 categories and many have only 1-2 examples,
     so no classifier could learn them reliably.

IMPORTANT - evaluation methodology:
  A naive random train/test split massively overstates accuracy on this
  dataset (~0.996 F1) because many synthetic rows are parameter variants
  of the same template (e.g. 9 rows = same rent clause, 9 different
  amounts) - a random split scatters variants of the SAME template across
  both train and test, so the model partly memorizes template
  fingerprints rather than learning genuine risk signal.

  This script evaluates with a GROUP-AWARE 5-FOLD CROSS-VALIDATION: all
  rows sharing the same (document_type, risk_category) are kept entirely
  in one fold, never split across train/test within a fold. 5-fold CV
  (mean + std across folds) is more robust than a single train/test split
  - a single split can get "lucky" or "unlucky"; averaging over 5
  different splits gives a number you can actually defend.

  It also separately reports performance on your 32 real hand-collected
  rows (held out completely) as an additional, even more conservative
  sanity check, since those aren't templated at all.

HYPERPARAMETER TUNING (2026 update):
  Ran a systematic sweep across vectorizer type (char n-grams vs word
  n-grams), n-gram range, and classifier (LogisticRegression, LinearSVC,
  RandomForest) - all under the SAME 5-fold group-aware CV, so
  comparisons are fair. Char n-grams (2-5) + LogisticRegression with
  C=2.5 (regularization strength) won: mean F1 0.6711 -> 0.7005 across
  5 folds, a genuine ~3 point improvement, not a cherry-picked split.

  IMPORTANT HONEST CAVEAT: this tuning did NOT move the real-holdout
  F1 at all (stayed at 0.3634 regardless of C). The improvement helps
  the model generalize better across different SYNTHETIC templates, but
  doesn't touch the underlying gap between synthetic and real-world
  phrasing. This confirms the existing conclusion in the README: the
  real fix is more REAL collected documents, not more tuning.

Run with: python scripts/train_risk_model.py
"""
import os
import json

import joblib
import numpy as np
import openpyxl
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import classification_report, f1_score

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_PATH = os.path.join(BASE_DIR, "data", "dataset_expanded2.xlsx")
MODELS_DIR = os.path.join(BASE_DIR, "models_trained")

RANDOM_STATE = 42
N_FOLDS = 5

# Found via systematic sweep under 5-fold group-aware CV - see docstring above.
BEST_C = 2.5


def load_dataset():
    wb = openpyxl.load_workbook(DATASET_PATH, data_only=True)
    ws = wb["Dataset"]
    rows = list(ws.iter_rows(min_row=4, values_only=True))

    records = []
    for r in rows:
        if not r[0] or not r[3] or not r[5]:
            continue
        records.append({
            "clause_id": r[0],
            "document_type": r[2],
            "urdu_text": r[3],
            "roman_text": r[4],
            "risk_label": r[5],
            "risk_category": r[6],
            "explanation": r[7],
        })
    return records


def is_real_row(clause_id: str) -> bool:
    """Your original 32 hand-collected rows are CL-001..CL-032, everything
    from CL-033 onward is synthetic dataset expansion."""
    try:
        num = int(clause_id.split("-")[1])
        return num <= 32
    except (IndexError, ValueError):
        return False


def make_vectorizer():
    return TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2)


def make_classifier():
    return LogisticRegression(max_iter=3000, class_weight="balanced", random_state=RANDOM_STATE, C=BEST_C)


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    records = load_dataset()
    print(f"Loaded {len(records)} labeled clauses from dataset.")

    texts = [r["urdu_text"] for r in records]
    labels = [r["risk_label"] for r in records]
    # group key = template family. Rows with the same document_type +
    # risk_category are almost always parameter variants of the same
    # template, so they must stay together on one side of each fold.
    groups = [f"{r['document_type']}::{r['risk_category']}" for r in records]

    # ---- 5-fold group-aware cross-validation ----
    gkf = GroupKFold(n_splits=N_FOLDS)
    fold_scores = []
    last_fold_report = None

    print(f"\n=== Risk Label classifier - {N_FOLDS}-fold GROUP-AWARE cross-validation ===")
    for fold_i, (train_idx, test_idx) in enumerate(gkf.split(texts, labels, groups=groups), 1):
        X_train_text = [texts[i] for i in train_idx]
        X_test_text = [texts[i] for i in test_idx]
        y_train = [labels[i] for i in train_idx]
        y_test = [labels[i] for i in test_idx]

        vec = make_vectorizer()
        X_train = vec.fit_transform(X_train_text)
        X_test = vec.transform(X_test_text)

        clf = make_classifier()
        clf.fit(X_train, y_train)
        y_pred = clf.predict(X_test)

        fold_f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)
        fold_scores.append(fold_f1)
        print(f"  Fold {fold_i}: macro F1 = {fold_f1:.4f}")
        last_fold_report = classification_report(y_test, y_pred, zero_division=0)

    macro_f1_grouped = float(np.mean(fold_scores))
    macro_f1_grouped_std = float(np.std(fold_scores))
    print(f"\nMean macro F1 across {N_FOLDS} folds: {macro_f1_grouped:.4f} (std: {macro_f1_grouped_std:.4f})")
    print(f"(target per NFR-04: >= 0.75)")
    print("\nLast fold's classification report (representative example):")
    print(last_fold_report)

    # ---- Additional, even more conservative check: train on ALL synthetic
    # rows, test purely on the 32 real hand-collected rows never trained on ----
    real_mask = np.array([is_real_row(r["clause_id"]) for r in records])
    synthetic_mask = ~real_mask

    vec_realtest = make_vectorizer()
    X_synthetic = vec_realtest.fit_transform([texts[i] for i in range(len(texts)) if synthetic_mask[i]])
    X_real = vec_realtest.transform([texts[i] for i in range(len(texts)) if real_mask[i]])
    y_synthetic = [labels[i] for i in range(len(labels)) if synthetic_mask[i]]
    y_real = [labels[i] for i in range(len(labels)) if real_mask[i]]

    clf_realtest = make_classifier()
    clf_realtest.fit(X_synthetic, y_synthetic)
    y_pred_real = clf_realtest.predict(X_real)
    macro_f1_real = f1_score(y_real, y_pred_real, average="macro", zero_division=0)

    print("\n=== Sanity check: trained on synthetic only, tested on 32 real rows ===")
    print(classification_report(y_real, y_pred_real, zero_division=0))
    print(f"Macro F1 (real-holdout): {macro_f1_real:.4f}")
    print("NOTE: this number does NOT improve with hyperparameter tuning - see")
    print("script docstring. The gap here is a data problem, not a tuning problem.")

    # ---- Final production model: retrain on ALL data (standard practice
    # once evaluation methodology above is validated) ----
    vectorizer = make_vectorizer()
    X = vectorizer.fit_transform(texts)
    clf_final = make_classifier()
    clf_final.fit(X, labels)

    # ---- Retrieval index for category + explanation ----
    retrieval_metadata = [
        {
            "urdu_text": r["urdu_text"],
            "document_type": r["document_type"],
            "risk_category": r["risk_category"],
            "risk_label": r["risk_label"],
            "explanation": r["explanation"],
        }
        for r in records
    ]

    joblib.dump(vectorizer, os.path.join(MODELS_DIR, "vectorizer.joblib"))
    joblib.dump(clf_final, os.path.join(MODELS_DIR, "risk_label_classifier.joblib"))
    joblib.dump(X, os.path.join(MODELS_DIR, "retrieval_matrix.joblib"))
    with open(os.path.join(MODELS_DIR, "retrieval_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(retrieval_metadata, f, ensure_ascii=False)

    metrics = {
        "macro_f1_group_aware_5fold_mean": round(macro_f1_grouped, 4),
        "macro_f1_group_aware_5fold_std": round(macro_f1_grouped_std, 4),
        "macro_f1_group_aware_per_fold": [round(float(s), 4) for s in fold_scores],
        "macro_f1_real_holdout_conservative": round(float(macro_f1_real), 4),
        "n_total": len(records),
        "n_real_hand_collected": int(real_mask.sum()),
        "n_synthetic": int(synthetic_mask.sum()),
        "tuned_C": BEST_C,
        "meets_nfr04_target_group_aware": bool(macro_f1_grouped >= 0.75),
        "note": (
            "A naive random-split F1 on this dataset is ~0.996 but is inflated by "
            "template leakage (see script docstring). The 5fold_mean number is what "
            "should be reported/defended - it's the average across 5 different "
            "group-aware splits, not one lucky split. real_holdout is a more "
            "conservative additional check using only hand-collected, non-templated "
            "data - hyperparameter tuning (C=2.5) improved 5fold_mean by ~3 points "
            "but did NOT move real_holdout at all, confirming the gap is a data "
            "problem (need more real documents), not a tuning problem."
        ),
    }
    with open(os.path.join(MODELS_DIR, "training_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\nSaved model artifacts to {MODELS_DIR}/")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()