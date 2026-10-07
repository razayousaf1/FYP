import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.explanation import _substitute_numbers


def test_substitutes_matching_number_counts():
    explanation = "Agreement khatam karne se pehle dono taraf ko 30 din ka notice dena hoga."
    reference_clause = "کوئی بھی فریق معاہدہ ختم کرنا چاہے تو 30 دن پہلے تحریری نوٹس دینے کا پابند ہوگا۔"
    query_clause = "کوئی بھی فریق معاہدہ ختم کرنا چاہے تو 45 دن پہلے تحریری نوٹس دینے کا پابند ہوگا۔"

    fixed, changed = _substitute_numbers(explanation, reference_clause, query_clause)
    assert changed is True
    assert "45 din" in fixed
    assert "30 din" not in fixed


def test_does_not_guess_when_counts_mismatch():
    explanation = "24,000 rupaye mahana kiraya hai."
    reference_clause = "مبلغ 24,000 روپے ماہانہ کرایہ۔"
    query_clause = "کوئی نمبر نہیں ہے یہاں۔"  # no digits at all

    fixed, changed = _substitute_numbers(explanation, reference_clause, query_clause)
    assert changed is False
    assert fixed == explanation  # left untouched, not guessed at
