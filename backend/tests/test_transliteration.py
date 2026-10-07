import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.transliteration import transliterate, transliterate_word, dictionary_coverage


def test_dictionary_hit_for_common_word():
    assert transliterate_word("کرایہ") == "kiraya"


def test_transliterate_full_sentence_returns_nonempty():
    result = transliterate("کرایہ دار مبلغ پچیس ہزار روپے ماہانہ کرایہ ادا کرے گا۔")
    assert len(result) > 0
    assert "kiraya" in result


def test_coverage_is_between_zero_and_one():
    cov = dictionary_coverage("کرایہ دار معاہدہ")
    assert 0.0 <= cov <= 1.0
