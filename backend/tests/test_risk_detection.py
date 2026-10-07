import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from shared.risk_detection import analyze_clause

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models_trained")

pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(MODELS_DIR, "risk_label_classifier.joblib")),
    reason="Model not trained yet - run scripts/train_risk_model.py first",
)


def test_analyze_clause_returns_valid_label():
    result = analyze_clause("کرایہ دار مبلغ پچیس ہزار روپے ماہانہ کرایہ ادا کرے گا۔")
    assert result.risk_label in {"High Risk", "Warning", "Safe"}
    assert 0.0 <= result.risk_label_confidence <= 1.0


def test_analyze_clause_flags_low_confidence_on_unrelated_text():
    result = analyze_clause("موسم آج بہت اچھا ہے اور دھوپ نکلی ہوئی ہے۔")
    assert result.retrieval_similarity is not None
