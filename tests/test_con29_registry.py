"""
Tests for src/con29_registry.py, rebuilt 2026-08-02 against the real St
Albans CON29R/LLC1 exemplar (search ref A/2025/00248). These lock in the
real-form fidelity so a future edit can't silently drift back toward
paraphrased/guessed text without a test failing.
"""
from src.con29_registry import (
    CON29_REGISTRY,
    UNCONFIRMED_NUMBERING,
    by_bucket,
    by_id,
    get_registry,
    top_level_groups,
)


def test_confirmed_top_level_groups_match_the_real_document():
    """19 top-level groups, each independently confirmed by an explicit
    printed question number in the real exemplar — see module docstring."""
    assert top_level_groups() == {
        "1.1", "1.2", "2.1", "2.2", "2.3", "2.4", "2.5",
        "3.1", "3.5", "3.6", "3.7", "3.8", "3.9", "3.10",
        "3.11", "3.12", "3.13", "3.14", "3.15",
    }


def test_unevidenced_previous_group_ids_are_gone():
    """Whole top-level groups the real form doesn't support under any
    number ("3.2 Roadworks / traffic schemes", "3.4 Traffic management
    schemes") must not silently reappear."""
    present_ids = {q.question_id for q in CON29_REGISTRY}
    assert "3.2" not in present_ids
    assert "3.4" not in present_ids

    # 3.8 must exist but with its REAL meaning, not the old "noise
    # abatement zones" guess.
    q38 = by_id("3.8")
    assert q38 is not None
    assert "noise" not in q38.question_text.lower()
    assert "building regulations" in q38.question_text.lower()


def test_1_1_g_h_i_carry_corrected_real_meaning_not_the_old_guess():
    """1.1g/h/i still exist as IDs — the real form's own 1.1 does run a-l —
    but their MEANING is now corrected: real (g) is a heritage partnership
    agreement, not 'planning enforcement'; real (h)/(i) are listed building
    consent orders, not 'Article 4 directions'."""
    q1g = by_id("1.1g")
    q1h = by_id("1.1h")
    q1i = by_id("1.1i")
    assert q1g is not None and "heritage partnership" in q1g.question_text.lower()
    assert q1h is not None and "listed building consent order" in q1h.question_text.lower()
    assert q1i is not None and "local listed building consent order" in q1i.question_text.lower()
    for q in (q1g, q1h, q1i):
        assert "enforcement" not in q.question_text.lower()
        assert "article 4" not in q.question_text.lower()


def test_tpo_moved_to_3_9m_not_3_7():
    """Real-form discovery: tree preservation orders are 3.9(m), not a
    standalone 3.7. 3.7 is real-form 'Outstanding Notices' instead."""
    q39m = by_id("3.9m")
    assert q39m is not None
    assert "tree preservation order" in q39m.question_text.lower()

    q37a = by_id("3.7a")
    assert q37a is not None
    assert "building works" in q37a.question_text.lower()

    # No standalone "3.7" (unlettered) TPO entry should exist any more.
    assert by_id("3.7") is None


def test_each_expanded_letter_has_distinct_real_text():
    """Regression guard for the previous registry's biggest fidelity gap:
    every letter in a lettered group must have its OWN text, not a single
    string repeated across the whole group."""
    for prefix in ("1.1", "3.6", "3.7", "3.9"):
        letters_present = [q for q in CON29_REGISTRY if q.question_id.startswith(prefix)
                            and q.question_id[len(prefix):].isalpha()]
        texts = {q.question_text for q in letters_present}
        assert len(texts) == len(letters_present), (
            f"Expected {len(letters_present)} distinct texts for {prefix}, "
            f"got {len(texts)} — a shared/generic string has crept back in."
        )


def test_unconfirmed_numbering_is_kept_separate_from_the_registry():
    """Real questions found in the document but without a legible printed
    number must NOT be given a guessed numeric id, and must not appear in
    CON29_REGISTRY itself (only in UNCONFIRMED_NUMBERING)."""
    assert len(UNCONFIRMED_NUMBERING) == 3
    unconfirmed_ids = {q.question_id for q in UNCONFIRMED_NUMBERING}
    assert all(qid.startswith("3.?-") for qid in unconfirmed_ids)

    registry_ids = {q.question_id for q in CON29_REGISTRY}
    assert unconfirmed_ids.isdisjoint(registry_ids)
    for qid in unconfirmed_ids:
        assert by_id(qid) is None  # by_id only searches CON29_REGISTRY


def test_get_registry_returns_the_module_level_list():
    assert get_registry() is CON29_REGISTRY


def test_no_manual_bucket_entries_in_the_confirmed_registry():
    """All 63 confirmed entries are auto or agent_navigated today — the
    three genuinely manual (Bucket 3) real questions found this session
    live in UNCONFIRMED_NUMBERING, not CON29_REGISTRY, pending a real
    question id."""
    assert by_bucket("manual") == []
    assert all(q.bucket == "manual" for q in UNCONFIRMED_NUMBERING)
