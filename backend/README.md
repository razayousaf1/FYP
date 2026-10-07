# Contract.AI Backend

## Status: fully wired, running locally (not yet deployed to Cloud Functions)

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000/docs` to test `/ocr` and `/analyze` interactively.

## Pipeline

```
Upload → OCR → Preprocess/Segment → Risk Detection → Explanation → JSON response
```

| Module | What it does | Trained? |
|---|---|---|
| `shared/ocr_engine.py` | Extracts text from PDF/PNG/JPG/JPEG/DOCX. Default: Google Vision API (`OCR_ENGINE=vision`, needs `GOOGLE_APPLICATION_CREDENTIALS`). Alternatives: `OCR_ENGINE=qwen2vl` (local GPU, no cloud cost) or `OCR_ENGINE=mock` (instant fake output for testing). pdfplumber/python-docx handle digital text without needing OCR at all. | No (pretrained) |
| `shared/preprocessing.py` | Unicode normalization + clause segmentation on Urdu sentence terminators. | No (deterministic) |
| `shared/transliteration.py` | Urdu → Roman Urdu. Two-tier: 661-word dictionary bootstrapped from your dataset (`shared/transliteration_dict.json`, regenerate with `scripts/build_transliteration_dict.py`), character-map fallback for unknown words. | No (lookup, not learned) |
| `shared/risk_detection.py` | Risk Label (Warning/Safe/High Risk) via **trained** TF-IDF + Logistic Regression classifier. Risk Category + Explanation via nearest-neighbor retrieval against the dataset (not a classifier - see below for why). | **Yes** - `scripts/train_risk_model.py` |
| `shared/explanation.py` | Formats risk_detection's output into the frontend's expected shape, with number-substitution to keep quoted figures accurate (see Testing findings below) and a graceful fallback for low-confidence matches. | No |

## IMPORTANT — read before your defense

**Why Risk Category isn't a trained classifier:** the dataset has 112 distinct risk categories, and many have only 1-2 examples. No classifier can learn 112 classes reliably from that little data per class. Nearest-neighbor retrieval (find the most similar clause in the dataset, reuse its category/explanation) is the statistically honest choice here, not a shortcut.

**Risk Label accuracy - the real number:** a naive random train/test split gives ~0.996 macro F1, which looks great but is misleading. Many synthetic dataset rows are parameter variants of the same template (e.g. 9 rows = same clause, 9 different rent amounts) - a random split scatters variants of the same template across train and test, so the model partly memorizes template fingerprints instead of learning genuine risk signal.

Re-evaluating with a **group-aware split** (same document_type+risk_category never split across train/test) gives a more honest **0.71 macro F1** — just under your NFR-04 target of 0.75. Testing purely on the 32 real hand-collected rows (never templated, held out completely) gives **0.36** — a stark reminder that the model doesn't yet generalize well beyond the synthetic templates.

**Full numbers:** see `models_trained/training_metrics.json` after running the training script.

**What this means practically:**
- Report the 0.71 group-aware number if asked in your defense, not the 0.996 random-split number - it will not hold up to scrutiny if a panel member asks about your split methodology.
- The real fix isn't more synthetic data - it's more **real, hand-collected documents**. If you have time before your defense, collecting even 30-50 more real clauses (not templated) and re-running `scripts/train_risk_model.py` would meaningfully improve both the honest metric and actual real-world performance.
- This is a legitimate, defensible research finding to include in your report, not something to hide - "we identified and corrected an evaluation methodology flaw" is a stronger thing to say to a panel than presenting an inflated number.

## Retraining after dataset changes

```bash
python scripts/build_transliteration_dict.py   # regenerate transliteration_dict.json
python scripts/train_risk_model.py              # regenerate models_trained/*
```

## Running tests

```bash
python -m pytest tests/ -v
```

## Testing findings (found and fixed during manual end-to-end testing)

**Bug found:** explanations retrieved via nearest-neighbor sometimes quoted the WRONG specific numbers (days/amounts/percentages) - because retrieval finds the textually closest training clause, but that clause may have different figures than the one actually being analyzed. Example caught during testing: a clause stating "30 din" notice got an explanation saying "97 din" instead, because the retrieved template came from a different training row.

**Fix applied:** `shared/explanation.py` now extracts numbers from the matched reference clause and the actual query clause, and substitutes the query's real numbers into the retrieved explanation when the counts line up. When they don't line up cleanly, it does NOT guess - it adds a `confidence_note` telling the user to verify the figures themselves against the highlighted clause, rather than risk stating a wrong number confidently. See `tests/test_explanation.py` for the regression tests covering both cases.

**Remaining known gap:** explanations that cite a *derived* number not literally present in the clause (e.g. "penalty = amount / 10 per day") won't have a matching reference number to substitute against, and may still show an approximate figure. This is inherent to retrieval-based generation and would need per-category custom logic to fully close - flagged here rather than hidden.



- Deployment to Google Cloud Functions (currently local-only - see main.py docstring)
- Firebase Storage/Firestore wiring (Phase 1 of the original roadmap)
- Frontend integration (Home.js currently has a mocked fake analyze - needs to call `/analyze` for real)
- OCR module has not been tested by me with real Vision API or Qwen2-VL credentials/GPU (this was built in a sandbox with neither) - test both yourself before relying on them. Routing logic, error handling, and all non-Vision paths (DOCX, PDF text-layer, mock) ARE tested. `GOOGLE_APPLICATION_CREDENTIALS` and `OCR_ENGINE=vision` error handling was verified to fail cleanly with the right message when credentials are missing - just not verified against a real successful Vision API call yet.
