import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.preprocessing import normalize_text, segment_clauses, preprocess


def test_normalize_collapses_whitespace():
    assert normalize_text("کرایہ   دار") == "کرایہ دار"


def test_segment_splits_on_urdu_terminator():
    text = "پہلا جملہ۔ دوسرا جملہ۔"
    clauses = segment_clauses(text)
    assert len(clauses) == 2


def test_segment_drops_short_noise_fragments():
    text = "ok۔ یہ ایک طویل جملہ ہے جو رہنا چاہیے۔"
    clauses = segment_clauses(text)
    assert all(len(c) >= 8 for c in clauses)


def test_preprocess_end_to_end():
    text = "کرایہ دار مبلغ پچیس ہزار روپے ماہانہ کرایہ ادا کرے گا۔"
    result = preprocess(text)
    assert len(result) == 1
