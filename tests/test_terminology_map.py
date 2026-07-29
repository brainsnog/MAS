from src.normalisation import terminology_map as tm


def test_normalise_grade_recognised_aliases():
    assert tm.normalise_grade("II") == "II"
    assert tm.normalise_grade("Grade II") == "II"
    assert tm.normalise_grade("grade 2") == "II"
    assert tm.normalise_grade("Grade II*") == "II*"
    assert tm.normalise_grade("grade two star") == "II*"
    assert tm.normalise_grade("Grade I") == "I"
    assert tm.normalise_grade("grade 1") == "I"


def test_normalise_grade_none_input():
    assert tm.normalise_grade(None) is None
    assert tm.normalise_grade("") is None


def test_normalise_grade_unrecognised_value_falls_back_to_raw():
    """
    An unrecognised grade string is kept (stripped), not silently dropped —
    a human should still be able to see it even if this module can't
    canonicalise it.
    """
    assert tm.normalise_grade("  Some Unusual Designation  ") == "Some Unusual Designation"


def test_mentions_article_4():
    assert tm.mentions_article_4("Article 4(1) Direction restricting permitted development") is True
    assert tm.mentions_article_4("ARTICLE4 restriction") is True
    assert tm.mentions_article_4("Ordinary planning permission") is False
    assert tm.mentions_article_4(None) is False


def test_mentions_conservation_area():
    assert tm.mentions_conservation_area("Within the Clifton Conservation Area") is True
    assert tm.mentions_conservation_area("Not designated") is False
    assert tm.mentions_conservation_area(None) is False
